from caro import Caro
import copy
import random
import time
import os
import threading
from array import array
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

try:
    from agent_accel import compute_sequences as cython_compute_sequences
except ImportError:
    cython_compute_sequences = None

try:
    from search_accel import search_best_move as cython_search_best_move
except ImportError:
    cython_search_best_move = None

TWO = 10
TWO_OBSTACLE = 5
THREE = 1000
THREE_OBSTACLE = 500
FOUR = 30000000
FOUR_OBSTACLE = 2000000
WINNING = 2000000000

TWO_OPPONENT = -20
TWO_OBSTACLE_OPPONENT = -3
THREE_OPPONENT = -2000
THREE_OBSTACLE_OPPONENT = -750
FOUR_OPPONENT = -40000000
FOUR_OBSTACLE_OPPONENT = -5000000
LOSING = -1000000000

INF = 999999999999
VERY_LARGE_SCORE = 10**15

dx = [1, 1, 1, -1, -1, -1, 0, 0]
dy = [1, -1, 0, 1, -1, 0, 1, -1]
directions = [(1, 0), (0, 1), (1, 1), (1, -1)]


@dataclass
class TTEntry:
    depth: int
    score: int
    flag: str
    best_move: list[int] | None


class Agent:

    def __init__(self, max_depth: int, XO: str, config: dict | None = None, log_init: bool = True) -> None:
        '''
            Parameters
            ----------------
            max_depth: Maximum depth for the Minimax tree 
            XO: 'X' or 'O', depend on the agent's turn

        '''
        self.max_depth = max_depth
        self.XO = XO
        self.beam_width_root = 15
        self.beam_width_inner = 10
        self.use_iterative_deepening = True
        self.use_tss = False
        self.tss_max_ply = 10
        self.tss_branch_limit = 3
        self.tss_win_bonus = 800000000
        self.move_time_budget_sec = 10
        self.min_depth_guarantee = 2
        self.use_lazy_smp = False
        self.lazy_smp_min_depth = 3
        self.lazy_smp_max_workers = max(2, min(8, (os.cpu_count() or 4) - 1))
        self.use_cython_search = False
        self.cython_search_min_depth = 5
        self.transposition_table: dict[int, TTEntry] = {}
        self.eval_cache: dict[int, int] = {}
        self.vcf_cache: dict[tuple[int, str, int, int], bool] = {}
        self.cache_lock = threading.RLock()
        self.zobrist_table = None
        self.zobrist_turn_key = None

        if config:
            self._apply_config(config)

        if log_init:
            print(
                "[Agent Init]",
                {
                    "XO": self.XO,
                    "max_depth": self.max_depth,
                    "beam_width_root": self.beam_width_root,
                    "beam_width_inner": self.beam_width_inner,
                    "use_iterative_deepening": self.use_iterative_deepening,
                    "use_tss": self.use_tss,
                    "tss_max_ply": self.tss_max_ply,
                    "tss_branch_limit": self.tss_branch_limit,
                    "tss_win_bonus": self.tss_win_bonus,
                    "move_time_budget_sec": self.move_time_budget_sec,
                    "min_depth_guarantee": self.min_depth_guarantee,
                    "use_lazy_smp": self.use_lazy_smp,
                    "lazy_smp_min_depth": self.lazy_smp_min_depth,
                    "lazy_smp_max_workers": self.lazy_smp_max_workers,
                    "use_cython_search": self.use_cython_search,
                    "cython_search_min_depth": self.cython_search_min_depth,
                },
            )

    def _apply_config(self, config: dict) -> None:
        allowed_keys = {
            "beam_width_root",
            "beam_width_inner",
            "use_iterative_deepening",
            "use_tss",
            "tss_max_ply",
            "tss_branch_limit",
            "tss_win_bonus",
            "move_time_budget_sec",
            "min_depth_guarantee",
            "use_lazy_smp",
            "lazy_smp_min_depth",
            "lazy_smp_max_workers",
            "use_cython_search",
            "cython_search_min_depth",
        }
        for key, value in config.items():
            if key in allowed_keys:
                setattr(self, key, value)

    def get_runtime_config(self) -> dict:
        return {
            "beam_width_root": self.beam_width_root,
            "beam_width_inner": self.beam_width_inner,
            "use_iterative_deepening": self.use_iterative_deepening,
            "use_tss": self.use_tss,
            "tss_max_ply": self.tss_max_ply,
            "tss_branch_limit": self.tss_branch_limit,
            "tss_win_bonus": self.tss_win_bonus,
            "move_time_budget_sec": self.move_time_budget_sec,
            "min_depth_guarantee": self.min_depth_guarantee,
            "use_lazy_smp": self.use_lazy_smp,
            "lazy_smp_min_depth": self.lazy_smp_min_depth,
            "lazy_smp_max_workers": self.lazy_smp_max_workers,
            "use_cython_search": self.use_cython_search,
            "cython_search_min_depth": self.cython_search_min_depth,
        }

    def _ensure_zobrist(self, game: Caro) -> None:
        if self.zobrist_table is not None:
            return
        rng = random.Random(20260407)
        self.zobrist_table = [
            [[rng.getrandbits(64), rng.getrandbits(64)] for _ in range(game.cols)]
            for _ in range(game.rows)
        ]
        self.zobrist_turn_key = rng.getrandbits(64)

    def _compute_hash(self, game: Caro) -> int:
        self._ensure_zobrist(game)
        h = 0
        for x in range(game.rows):
            for y in range(game.cols):
                cell = game.grid[x][y]
                if cell == 'X':
                    h ^= self.zobrist_table[x][y][0]
                elif cell == 'O':
                    h ^= self.zobrist_table[x][y][1]
        if game.XO == 'X':
            h ^= self.zobrist_turn_key
        return h

    def get_possible_moves_optimized(self, game: Caro) -> list[list[int]]:
        visited = [[0 for _ in range(game.cols)] for _ in range(game.rows)]
        result = []
        for x in range(game.rows):
            for y in range(game.cols):
                if game.grid[x][y] == '.':
                    continue
                for k in range(8):
                    nx = x + dx[k]
                    ny = y + dy[k]

                    if nx >= 0 and ny >= 0 and nx < game.rows and ny < game.cols and game.grid[nx][ny] == '.' and visited[nx][ny] == 0:
                        visited[nx][ny] = 1
                        result.append([nx, ny])

        return result

    def compute(self, sequences: list[list[str]]) -> int:
        '''
            Parameters
            ----------------
            sequences: consecutive cells from the board (rows, columns or diagonals)

            current: 'X' or 'O', depend on current player move

            Return
            ---------------- 
            Heuristic with the given sequences

        '''

        if cython_compute_sequences is not None:
            return cython_compute_sequences(
                sequences,
                self.XO,
                TWO,
                TWO_OBSTACLE,
                THREE,
                THREE_OBSTACLE,
                FOUR,
                FOUR_OBSTACLE,
                WINNING,
                TWO_OPPONENT,
                TWO_OBSTACLE_OPPONENT,
                THREE_OPPONENT,
                THREE_OBSTACLE_OPPONENT,
                FOUR_OPPONENT,
                FOUR_OBSTACLE_OPPONENT,
                LOSING,
            )

        result = 0

        for sequence in sequences:
            player = 0
            opponent = 0
            obstacle = 1
            obstacle_player = 0
            obstacle_opponent = 0
            for c in sequence:
                if c == self.XO:
                    player += 1

                    if opponent != 0:
                        if opponent == 2 and obstacle_player == 0 and obstacle == 0:
                            result += TWO_OBSTACLE_OPPONENT
                        elif opponent == 3 and obstacle_player == 0 and obstacle == 0:
                            result += THREE_OBSTACLE_OPPONENT
                        elif opponent == 4 and obstacle_player == 0 and obstacle == 0:
                            result += FOUR_OBSTACLE_OPPONENT
                        elif opponent == 5:
                            result += LOSING

                    opponent = 0
                    obstacle_player = 1
                    # obstacle = 0

                elif c != '.':
                    opponent += 1

                    if player != 0:
                        if player == 2 and obstacle_opponent == 0 and obstacle == 0:
                            result += TWO_OBSTACLE
                        elif player == 3 and obstacle_opponent == 0 and obstacle == 0:
                            result += THREE_OBSTACLE
                        elif player == 4 and obstacle_opponent == 0 and obstacle == 0:
                            result += FOUR_OBSTACLE
                        elif player == 5:
                            result += WINNING

                    player = 0
                    # obstacle = 0
                    obstacle_opponent = 1

                else:
                    if player != 0:
                        if player == 2:
                            if obstacle_opponent == 1 or obstacle == 1:
                                result += TWO_OBSTACLE
                            else:
                                result += TWO
                        elif player == 3:
                            if obstacle_opponent == 1 or obstacle == 1:
                                result += THREE_OBSTACLE
                            else:
                                result += THREE
                        elif player == 4:
                            if obstacle_opponent == 1 or obstacle == 1:
                                result += FOUR_OBSTACLE
                            else:
                                result += FOUR
                        elif player == 5:
                            result += WINNING
                    player = 0

                    if opponent != 0:
                        if opponent == 2:
                            if obstacle_player == 1 or obstacle == 1:
                                result += TWO_OBSTACLE_OPPONENT
                            else:
                                result += TWO_OPPONENT
                        elif opponent == 3:
                            if obstacle_player == 1 or obstacle == 1:
                                result += THREE_OBSTACLE_OPPONENT
                            else:
                                result += THREE_OPPONENT
                        elif opponent == 4:
                            if obstacle_player == 1 or obstacle == 1:
                                result += FOUR_OBSTACLE_OPPONENT
                            else:
                                result += FOUR_OPPONENT
                        elif opponent == 5:
                            result += LOSING

                        opponent = 0

                    obstacle = 0
                    obstacle_player = 0
                    obstacle_opponent = 0

            if opponent != 0:
                if opponent == 2 and obstacle_player == 0 and obstacle == 0:
                    result += TWO_OBSTACLE_OPPONENT
                elif opponent == 3 and obstacle_player == 0 and obstacle == 0:
                    result += THREE_OBSTACLE_OPPONENT
                elif opponent == 4 and obstacle_player == 0 and obstacle == 0:
                    result += FOUR_OBSTACLE_OPPONENT
                elif opponent == 5:
                    result += LOSING

            if player != 0:
                if player == 2 and obstacle_opponent == 0 and obstacle == 0:
                    result += TWO_OBSTACLE
                elif player == 3 and obstacle_opponent == 0 and obstacle == 0:
                    result += THREE_OBSTACLE
                elif player == 4 and obstacle_opponent == 0 and obstacle == 0:
                    result += FOUR_OBSTACLE
                elif player == 5:
                    result += WINNING

        return result

    def get_heuristic(self, game: Caro) -> int:
        '''
            Parameters
            ----------

            game: Caro object, represent current game state

            Return
            --------------
            The heuristic corresponding to the current board and current player.
        '''

        board_hash = self._compute_hash(game)
        with self.cache_lock:
            if board_hash in self.eval_cache:
                return self.eval_cache[board_hash]

        score = self.compute(game.get_all_rows()) + \
            self.compute(game.get_all_diagonals()) + \
            self.compute(game.get_all_colummns())
        with self.cache_lock:
            self.eval_cache[board_hash] = score
        return score

    def _line_metrics(self, game: Caro, x: int, y: int, piece: str, dir_x: int, dir_y: int) -> tuple[int, int]:
        total = 1
        open_ends = 0

        nx, ny = x + dir_x, y + dir_y
        while 0 <= nx < game.rows and 0 <= ny < game.cols and game.grid[nx][ny] == piece:
            total += 1
            nx += dir_x
            ny += dir_y
        if 0 <= nx < game.rows and 0 <= ny < game.cols and game.grid[nx][ny] == '.':
            open_ends += 1

        nx, ny = x - dir_x, y - dir_y
        while 0 <= nx < game.rows and 0 <= ny < game.cols and game.grid[nx][ny] == piece:
            total += 1
            nx -= dir_x
            ny -= dir_y
        if 0 <= nx < game.rows and 0 <= ny < game.cols and game.grid[nx][ny] == '.':
            open_ends += 1

        return total, open_ends

    def _local_pattern_score(self, game: Caro, x: int, y: int, piece: str) -> int:
        # Local tactical scoring for move ordering, avoids full-board evaluation.
        score = 0
        for dir_x, dir_y in directions:
            total, open_ends = self._line_metrics(game, x, y, piece, dir_x, dir_y)
            if total >= 5:
                score += VERY_LARGE_SCORE
            elif total == 4 and open_ends == 2:
                score += 200000000
            elif total == 4 and open_ends == 1:
                score += 60000000
            elif total == 3 and open_ends == 2:
                score += 1000000
            elif total == 3 and open_ends == 1:
                score += 150000
            elif total == 2 and open_ends == 2:
                score += 2000
        return score

    def _quick_move_score(self, game: Caro, x: int, y: int) -> int:
        current_piece = game.XO
        opponent_piece = 'O' if current_piece == 'X' else 'X'
        attack_score = self._local_pattern_score(game, x, y, current_piece)
        block_score = self._local_pattern_score(game, x, y, opponent_piece)

        # Prioritize immediate win, then urgent defense, then strong positional gains.
        if attack_score >= VERY_LARGE_SCORE:
            return VERY_LARGE_SCORE * 2
        if block_score >= VERY_LARGE_SCORE:
            return VERY_LARGE_SCORE + 1
        return attack_score * 2 + block_score

    def _sort_moves(self, game: Caro, possible_moves: list[list[int]]) -> list[list[int]]:
        scored_moves = []
        for x, y in possible_moves:
            scored_moves.append((self._quick_move_score(game, x, y), [x, y]))
        scored_moves.sort(key=lambda item: item[0], reverse=True)
        return [move for _, move in scored_moves]

    def _limit_moves(self, ordered_moves: list[list[int]], depth: int) -> list[list[int]]:
        width = self.beam_width_root if depth == self.max_depth else self.beam_width_inner
        if width <= 0 or len(ordered_moves) <= width:
            return ordered_moves
        return ordered_moves[:width]

    def _prioritize_moves(self, moves: list[list[int]], priority_moves: list[list[int] | None]) -> list[list[int]]:
        if not moves:
            return moves
        promoted = []
        for p in priority_moves:
            if p is None:
                continue
            if p in moves and p not in promoted:
                promoted.append(p)
        for m in moves:
            if m not in promoted:
                promoted.append(m)
        return promoted

    def _threat_level(self, game: Caro, x: int, y: int, piece: str) -> int:
        max_total = 1
        max_open = 0
        for dir_x, dir_y in directions:
            total, open_ends = self._line_metrics(game, x, y, piece, dir_x, dir_y)
            if total > max_total:
                max_total = total
                max_open = open_ends
            elif total == max_total and open_ends > max_open:
                max_open = open_ends

        if max_total >= 5:
            return 4
        if max_total == 4 and max_open >= 1:
            return 3
        if max_total == 3 and max_open == 2:
            return 2
        if max_total == 3 and max_open == 1:
            return 1
        return 0

    def _get_threat_moves(self, game: Caro, piece: str, min_level: int = 2) -> list[list[int]]:
        candidates = self.get_possible_moves_optimized(game)
        if not candidates:
            return []
        moves = []
        for x, y in candidates:
            level = self._threat_level(game, x, y, piece)
            if level >= min_level:
                # Higher threat level first, then quick local score.
                moves.append((level, self._quick_move_score(game, x, y), [x, y]))
        moves.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [m for _, __, m in moves]

    def _has_immediate_threat(self, game: Caro, piece: str) -> bool:
        return len(self._get_threat_moves(game, piece, min_level=3)) > 0

    def _get_vcf_attack_moves(self, game: Caro, piece: str) -> list[list[int]]:
        # VCF: only forcing attacks (create four or immediate five).
        return self._get_threat_moves(game, piece, min_level=3)[:self.tss_branch_limit]

    def _get_vcf_defenses(self, game: Caro, attacker_piece: str) -> list[list[int]]:
        defender_piece = game.XO
        defender_wins = self._get_threat_moves(game, defender_piece, min_level=4)
        if defender_wins:
            return defender_wins[:self.tss_branch_limit]

        # Must block attacker's immediate winning points first.
        attacker_wins = self._get_threat_moves(game, attacker_piece, min_level=4)
        if attacker_wins:
            return attacker_wins[:self.tss_branch_limit]

        # Then block attacker's forcing-four continuation.
        return self._get_threat_moves(game, attacker_piece, min_level=3)[:self.tss_branch_limit]

    def _has_forced_vcf_win(self, game: Caro, attacker_piece: str, ply_left: int) -> bool:
        winner = game.get_winner()
        if winner != -1:
            if winner == 0 and attacker_piece == 'X':
                return True
            if winner == 1 and attacker_piece == 'O':
                return True
            return False
        if ply_left <= 0:
            return False

        cache_key = (self._compute_hash(game), attacker_piece, ply_left, 1 if game.XO == attacker_piece else 0)
        with self.cache_lock:
            cached = self.vcf_cache.get(cache_key)
        if cached is not None:
            return cached

        if game.XO == attacker_piece:
            attack_moves = self._get_vcf_attack_moves(game, attacker_piece)
            if not attack_moves:
                with self.cache_lock:
                    self.vcf_cache[cache_key] = False
                return False
            for move in attack_moves:
                new_game = copy.deepcopy(game)
                new_game.make_move(move[0], move[1])
                if self._has_forced_vcf_win(new_game, attacker_piece, ply_left - 1):
                    with self.cache_lock:
                        self.vcf_cache[cache_key] = True
                    return True
            with self.cache_lock:
                self.vcf_cache[cache_key] = False
            return False

        responses = self._get_vcf_defenses(game, attacker_piece)
        if not responses:
            with self.cache_lock:
                self.vcf_cache[cache_key] = True
            return True
        for response in responses:
            new_game = copy.deepcopy(game)
            new_game.make_move(response[0], response[1])
            if not self._has_forced_vcf_win(new_game, attacker_piece, ply_left - 1):
                with self.cache_lock:
                    self.vcf_cache[cache_key] = False
                return False
        with self.cache_lock:
            self.vcf_cache[cache_key] = True
        return True

    def _tss_leaf_bonus(self, game: Caro) -> int:
        if not self.use_tss or self.tss_max_ply <= 0:
            return 0
        side_to_move = game.XO
        # Gate expensive search: only if there is already a strong threat shape.
        if not self._has_immediate_threat(game, side_to_move):
            return 0
        if self._has_forced_vcf_win(game, side_to_move, self.tss_max_ply):
            return self.tss_win_bonus if side_to_move == self.XO else -self.tss_win_bonus
        return 0

    def _effective_depth(self, game: Caro) -> int:
        # move_count = len(game.last_move)
        # if move_count <= 4:
        #     return min(self.max_depth, 4)
        # if move_count <= 8:
        #     return min(self.max_depth, 6)
        return self.max_depth

    def _configure_beam_for_stage(self, game: Caro) -> None:
        move_count = len(game.last_move)
        if move_count <= 4:
            self.beam_width_root = 10
            self.beam_width_inner = 8
        elif move_count <= 8:
            self.beam_width_root = 12
            self.beam_width_inner = 9
        else:
            self.beam_width_root = 15
            self.beam_width_inner = 10

    def _search_depth_lazy_smp(
        self,
        game: Caro,
        depth: int,
        pv_move: list[int] | None,
        deadline: float | None,
    ) -> tuple[int, list[int] | None, bool]:
        possible_moves = self.get_possible_moves_optimized(game)
        if not possible_moves:
            return self.get_heuristic(game), None, True

        ordered_moves = self._sort_moves(game, possible_moves)
        ordered_moves = self._prioritize_moves(ordered_moves, [pv_move])
        ordered_moves = self._limit_moves(ordered_moves, depth)
        if not ordered_moves:
            return self.get_heuristic(game), None, True

        best_score = -INF
        best_move = ordered_moves[0]
        max_workers = min(self.lazy_smp_max_workers, len(ordered_moves))
        completed = True

        def evaluate_root_move(move: list[int]) -> tuple[int, list[int], bool]:
            if deadline is not None and time.perf_counter() >= deadline:
                return -INF, move, False
            new_game = copy.deepcopy(game)
            new_game.make_move(move[0], move[1])
            score, _, child_completed = self.minimax(new_game, depth - 1, -INF * 10, INF * 10, 0, None, deadline)
            return score, move, child_completed

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(evaluate_root_move, move) for move in ordered_moves]
            for future in as_completed(futures):
                if deadline is not None and time.perf_counter() >= deadline:
                    completed = False
                    break
                score, move, child_completed = future.result()
                if not child_completed:
                    completed = False
                if score > best_score:
                    best_score = score
                    best_move = move

        return best_score, best_move, completed

    def _to_flat_board(self, game: Caro) -> list[int]:
        mapped = {'.': 0, 'X': 1, 'O': 2}
        flat = []
        for x in range(game.rows):
            for y in range(game.cols):
                flat.append(mapped[game.grid[x][y]])
        return flat

    def _search_with_cython_engine(self, game: Caro, depth: int) -> list[int] | None:
        if cython_search_best_move is None:
            return None
        current_player = 1 if game.XO == 'X' else 2
        board_data = array('i', self._to_flat_board(game))
        result = cython_search_best_move(
            board_data,
            game.rows,
            game.cols,
            current_player,
            depth,
            self.beam_width_root,
        )
        if result is None:
            return None
        x, y, _ = result
        return [x, y]

    def _find_immediate_win_move(self, game: Caro, piece: str) -> list[int] | None:
        winning_candidates = self._get_threat_moves(game, piece, min_level=4)
        for x, y in winning_candidates:
            trial = copy.deepcopy(game)
            # We may test either side's tactical win, so force the simulated side.
            trial.XO = piece
            trial.make_move(x, y)
            winner = trial.get_winner()
            if (piece == 'X' and winner == 0) or (piece == 'O' and winner == 1):
                return [x, y]
        return None

    def _find_tactical_forced_move(self, game: Caro) -> list[int] | None:
        current_piece = game.XO
        opponent_piece = 'O' if current_piece == 'X' else 'X'

        # 1) If we can win now, always do it.
        my_win = self._find_immediate_win_move(game, current_piece)
        if my_win is not None:
            return my_win

        # 2) If opponent can win next move, block that point.
        opponent_win = self._find_immediate_win_move(game, opponent_piece)
        if opponent_win is not None:
            return opponent_win

        return None

    def get_move(self, game: Caro) -> list[list[int]]:
        '''
            Parameters
            ----------

            game: Caro object, represent current game state

            Return
            --------------
            The best move of the current position
        '''
        if len(game.last_move) < 1:
            possible_moves = game.get_possible_moves()
            if not possible_moves:
                return None
            center_x = (game.rows - 1) / 2.0
            center_y = (game.cols - 1) / 2.0

            weighted_moves = []
            weights = []
            for x, y in possible_moves:
                # Prefer center area for opening instead of edges/corners.
                dx = x - center_x
                dy = y - center_y
                dist2 = dx * dx + dy * dy
                weight = 1.0 / (1.0 + dist2)
                weighted_moves.append([x, y])
                weights.append(weight)

            return random.choices(weighted_moves, weights=weights, k=1)[0]
        elif len(game.last_move) == 1:
            possible_moves = self.get_possible_moves_optimized(game)
            move = random.choice(possible_moves)
            return move

        self.transposition_table.clear()
        self.eval_cache.clear()
        self.vcf_cache.clear()
        self._configure_beam_for_stage(game)
        target_depth = self._effective_depth(game)
        deadline = time.perf_counter() + self.move_time_budget_sec

        forced_move = self._find_tactical_forced_move(game)
        if forced_move is not None:
            return forced_move

        if self.use_cython_search and target_depth >= self.cython_search_min_depth:
            cy_move = self._search_with_cython_engine(game, target_depth)
            if cy_move is not None:
                return cy_move

        if not self.use_iterative_deepening:
            best_score, best_move, completed = self.minimax(
                game, target_depth, -INF * 10, INF * 10, 1, None, deadline)
            if completed and best_move is not None:
                return best_move
            fallback = self._sort_moves(game, self.get_possible_moves_optimized(game))
            return fallback[0] if fallback else None

        best_move = None
        pv_move = None
        for depth in range(1, target_depth + 1):
            if depth > self.min_depth_guarantee and time.perf_counter() >= deadline:
                break
            if self.use_lazy_smp and depth >= self.lazy_smp_min_depth:
                best_score, current_best, completed = self._search_depth_lazy_smp(
                    game, depth, pv_move, deadline
                )
            else:
                best_score, current_best, completed = self.minimax(
                    game, depth, -INF * 10, INF * 10, 1, pv_move, deadline
                )
            # Only commit the move when this depth is fully completed.
            if completed and current_best is not None:
                best_move = current_best
                pv_move = current_best

        if best_move is None:
            fallback = self._sort_moves(game, self.get_possible_moves_optimized(game))
            if fallback:
                return fallback[0]
        return best_move

    def minimax(
        self,
        game: Caro,
        depth: int,
        alpha: int,
        beta: int,
        maximizing_player: int = 1,
        pv_move: list[int] | None = None,
        deadline: float | None = None,
    ) -> tuple[int, list[int], bool]:
        '''
            Implement the Minimax algorithm.

            Parameters
            ------------
            game: The Caro object, represent the current state of the game.

            depth: The current depth in minimax tree.

            alpha: maximum heuristic for alpha-beta pruning optimization.

            beta: minimum heuristic for alpha-beta pruning optimization.

            maximizing_player: 1 if we need to maximize heuristic, 0 otherwise.

            Return
            ------------
            The score of the best move and the best move coordinate.

        '''

        if deadline is not None and time.perf_counter() >= deadline:
            return self.get_heuristic(game), None, False

        winner = game.get_winner()
        if depth == 0 or winner != -1:
            return self.get_heuristic(game) + self._tss_leaf_bonus(game), None, True

        board_hash = self._compute_hash(game)
        alpha_original = alpha
        beta_original = beta

        with self.cache_lock:
            tt_entry = self.transposition_table.get(board_hash)
        if tt_entry is not None and tt_entry.depth >= depth:
            if tt_entry.flag == 'EXACT':
                return tt_entry.score, tt_entry.best_move, True
            if tt_entry.flag == 'LOWERBOUND':
                alpha = max(alpha, tt_entry.score)
            elif tt_entry.flag == 'UPPERBOUND':
                beta = min(beta, tt_entry.score)
            if alpha >= beta:
                return tt_entry.score, tt_entry.best_move, True

        possible_moves = self.get_possible_moves_optimized(game)
        if not possible_moves:
            return self.get_heuristic(game), None, True
        ordered_moves = self._sort_moves(game, possible_moves)
        ordered_moves = self._prioritize_moves(ordered_moves, [pv_move, tt_entry.best_move if tt_entry else None])
        ordered_moves = self._limit_moves(ordered_moves, depth)

        if maximizing_player:
            max_eval = -INF
            best_move = ordered_moves[0]
            completed = True

            for possible_move in ordered_moves:
                x = possible_move[0]
                y = possible_move[1]

                new_game = copy.deepcopy(game)
                new_game.make_move(x, y)

                eval, move, child_completed = self.minimax(new_game, depth - 1,
                                          alpha, beta, maximizing_player ^ 1, None, deadline)
                if not child_completed:
                    completed = False
                    return max_eval if max_eval != -INF else eval, best_move, False

                if eval > max_eval:
                    max_eval = eval
                    best_move = [x, y]

                alpha = max(alpha, max_eval)
                if beta <= alpha:
                    break
            flag = 'EXACT'
            if max_eval <= alpha_original:
                flag = 'UPPERBOUND'
            elif max_eval >= beta_original:
                flag = 'LOWERBOUND'
            with self.cache_lock:
                self.transposition_table[board_hash] = TTEntry(depth, max_eval, flag, best_move)
            return max_eval, best_move, completed
        else:
            min_eval = INF
            best_move = ordered_moves[0]
            completed = True

            for possible_move in ordered_moves:
                x = possible_move[0]
                y = possible_move[1]

                new_game = copy.deepcopy(game)
                new_game.make_move(x, y)

                eval, move, child_completed = self.minimax(new_game, depth - 1,
                                          alpha, beta, maximizing_player ^ 1, None, deadline)
                if not child_completed:
                    completed = False
                    return min_eval if min_eval != INF else eval, best_move, False

                if eval < min_eval:
                    min_eval = eval
                    best_move = [x, y]

                beta = min(beta, min_eval)
                if beta <= alpha:
                    break
            flag = 'EXACT'
            if min_eval <= alpha_original:
                flag = 'UPPERBOUND'
            elif min_eval >= beta_original:
                flag = 'LOWERBOUND'
            with self.cache_lock:
                self.transposition_table[board_hash] = TTEntry(depth, min_eval, flag, best_move)
            return min_eval, best_move, completed


# Testing

if __name__ == '__main__':
    game = Caro(rows=5, cols=5)
    game.grid = [
        ['.', '.', '.', '.', '.'],
        ['.', '.', 'O', '.', '.'],
        ['.', '.', 'O', '.', '.'],
        ['.', '.', 'O', '.', '.'],
        ['.', '.', '.', '.', '.'],
    ]

    agent = Agent(max_depth=2, XO='X')
    possible_moves = agent.get_possible_moves_optimized(game)
    print(f'possible_moves: {possible_moves}')
    best_move = agent.get_move(game)

    print(best_move)
    game.make_move(best_move[0], best_move[1])

    print(game.grid)
