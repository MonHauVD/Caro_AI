from caro import Caro

TWO = 10
TWO_OBSTACLE = 5
THREE = 1000
THREE_OBSTACLE = 500
FOUR = 10000000
FOUR_OBSTACLE = 2000
WINNING = 500000000

TWO_OPPONENT = -20
TWO_OBSTACLE_OPPONENT = -3
THREE_OPPONENT = -5000
THREE_OBSTACLE_OPPONENT = -750
FOUR_OPPONENT = -30000000
FOUR_OBSTACLE_OPPONENT = -50000
LOSING = -1000000000


class Agent:

    def __init__(self, max_depth: int) -> None:
        self.max_depth = max_depth
        pass

    def get_heuristic(self, grid: list[list[str]], current: str) -> int:
        '''
            Parameters
            ----------
            grid: The XO game board 

            current: 'X' or 'O', depend on which character player is playing with

            Return
            --------------
            The heuristic corresponding to the current board and current player.
        '''

        pass

    def get_move():
        pass

    def minimax(self, game: Caro, depth: int, alpha: int, beta: int, maximizing_player: int = 1) -> list[list[int]]:
        '''
            Implementing minimax algorithm for agent

            Parameters
            ------------
            game: The Caro object, represent the current state of the game.

            depth: The current depth in minimax tree.

            alpha: maximum heuristic for alpha-beta pruning optimization.

            beta: minimum heuristic for alpha-beta pruning optimization.

            maximizing_player: 1 if we need to maximize heuristic, 0 otherwise.

            Return
            ------------
            The heuristic for current node of the minimax tree.

        '''
        if depth == 0 or game.get_winner() != -1:
            return self.get_heuristic(game.grid, game.XO)

        possible_moves = game.get_possible_moves()

        if maximizing_player:
            max_eval = -99999999999999

            for possible_move in possible_moves:
                x = possible_move[0]
                y = possible_move[1]

                new_game = game
                new_game.make_move(x, y)

                eval = self.minimax(new_game, depth - 1,
                                    alpha, beta, maximizing_player ^ 1)
                max_eval = max(max_eval, eval)
                alpha = max(alpha, eval)
                if beta <= alpha:
                    break
            return max_eval
        else:
            min_eval = 99999999999999

            for possible_move in possible_moves:
                x = possible_move[0]
                y = possible_move[1]

                new_game = game
                new_game.make_move(x, y)

                eval = self.minimax(new_game, depth - 1,
                                    alpha, beta, maximizing_player ^ 1)
                min_eval = min(min_eval, beta)
                beta = min(beta, eval)
                if beta <= alpha:
                    break
            return min_eval


if __name__ == '__main__':
    agent = Agent()
