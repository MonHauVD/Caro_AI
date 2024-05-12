from caro import Caro
import copy

TWO = 10
TWO_OBSTACLE = 5
THREE = 1000
THREE_OBSTACLE = 500
FOUR = 10000000
FOUR_OBSTACLE = 2000
WINNING = 2000000000

TWO_OPPONENT = -20
TWO_OBSTACLE_OPPONENT = -3
THREE_OPPONENT = -5000
THREE_OBSTACLE_OPPONENT = -750
FOUR_OPPONENT = -30000000
FOUR_OBSTACLE_OPPONENT = -50000
LOSING = -1000000000


class Agent:

    def __init__(self, max_depth: int, XO: str) -> None:
        self.max_depth = max_depth
        self.XO = XO

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

        player = 0
        opponent = 0
        obstacle = 1

        result = 0

        for sequence in sequences:
            for c in sequence:
                if c == self.XO:
                    player += 1
                    obstacle = 1

                    if opponent != 0:
                        if opponent == 2 and obstacle == 0:
                            result += TWO_OBSTACLE_OPPONENT
                        elif opponent == 3 and obstacle == 0:
                            result += THREE_OBSTACLE_OPPONENT
                        elif opponent == 4 and obstacle == 0:
                            result += FOUR_OBSTACLE_OPPONENT
                        elif opponent == 5:
                            result += LOSING

                    opponent = 0

                elif c != '.':
                    opponent += 1
                    obstacle = 1

                    if player != 0:
                        if player == 2 and obstacle == 0:
                            result += TWO_OBSTACLE
                        elif player == 3 and obstacle == 0:
                            result += THREE_OBSTACLE
                        elif player == 4 and obstacle == 0:
                            result += FOUR_OBSTACLE
                        elif player == 5:
                            result += WINNING
                        player = 0

                else:
                    obstacle = 0
                    if player != 0:
                        if player == 2:
                            if obstacle == 1:
                                result += TWO_OBSTACLE
                            else:
                                result += TWO
                        elif player == 3:
                            if obstacle == 1:
                                result += THREE_OBSTACLE
                            else:
                                result += THREE
                        elif player == 4:
                            if obstacle == 1:
                                result += FOUR_OBSTACLE
                            else:
                                result += FOUR
                        elif player == 5:
                            result += WINNING
                    player = 0

                    if opponent != 0:
                        if opponent == 2:
                            if obstacle == 1:
                                result += TWO_OBSTACLE_OPPONENT
                            else:
                                result += TWO_OPPONENT
                        elif opponent == 3:
                            if obstacle == 1:
                                result += THREE_OBSTACLE_OPPONENT
                            else:
                                result += THREE_OPPONENT
                        elif opponent == 4:
                            if obstacle == 1:
                                result += FOUR_OBSTACLE_OPPONENT
                            else:
                                result += FOUR_OPPONENT
                        elif opponent == 5:
                            result += LOSING

                        opponent = 0

        if opponent != 0:
            if opponent == 2 and obstacle == 0:
                result += TWO_OBSTACLE_OPPONENT
            elif opponent == 3 and obstacle == 0:
                result += THREE_OBSTACLE_OPPONENT
            elif opponent == 4 and obstacle == 0:
                result += FOUR_OBSTACLE_OPPONENT
            elif opponent == 5:
                result += LOSING

        if player != 0:
            if player == 2 and obstacle == 0:
                result += TWO_OBSTACLE
            elif player == 3 and obstacle == 0:
                result += THREE_OBSTACLE
            elif player == 4 and obstacle == 0:
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

        return self.compute(game.get_all_rows()) + self.compute(game.get_all_diagonals()) + self.compute(game.get_all_colummns)

    def get_move(self, game: Caro) -> list[list[int]]:
        '''
            Parameters
            ----------

            game: Caro object, represent current game state

            Return
            --------------
            The best move of the current position
        '''

        best_score, best_move = self.minimax(
            game, self.max_depth, -999999999999999, 999999999999999)
        return best_move

    def minimax(self, game: Caro, depth: int, alpha: int, beta: int, maximizing_player: int = 1) -> tuple[int, list[int]]:
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

        if depth == 0 or game.get_winner() != -1:
            return self.get_heuristic(game), None

        possible_moves = game.get_possible_moves()

        if maximizing_player:
            max_eval = -99999999999999
            best_move = possible_moves[0]

            for possible_move in possible_moves:
                x = possible_move[0]
                y = possible_move[1]

                new_game = copy.deepcopy(game)
                new_game.make_move(x, y)

                eval = self.minimax(new_game, depth - 1,
                                    alpha, beta, maximizing_player ^ 1)
                max_eval = max(max_eval, eval)
                if eval > max_eval:
                    max_eval = eval
                    best_move = [x, y]
                alpha = max(alpha, eval)
                if beta <= alpha:
                    break
            return max_eval, best_move
        else:
            min_eval = 99999999999999
            best_move = possible_moves[0]

            for possible_move in possible_moves:
                x = possible_move[0]
                y = possible_move[1]

                new_game = copy.deepcopy(game)
                new_game.make_move(x, y)

                eval = self.minimax(new_game, depth - 1,
                                    alpha, beta, maximizing_player ^ 1)
                if eval < min_eval:
                    min_eval = eval
                    best_move = [x, y]

                beta = min(beta, eval)
                if beta <= alpha:
                    break
            return min_eval, best_move


if __name__ == '__main__':
    agent = Agent(max_depth=2)
