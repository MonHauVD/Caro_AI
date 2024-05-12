import random
import pygame

class Caro:
    '''Tic Tac Toe game simulator'''
    def __init__(self, rows: int, cols: int, winning_condition: int = 5, XO: str = "X") -> None:
        '''
            Parameters
            ------------
            rows (int): Number of rows of the board.

            cols (int): Number of columns of the board.

            winning_condition (int): Number of consecutive cells that a player need to have in order to win the game. Default: 5

        '''
        self.originXO = XO
        self.rows = rows
        self.cols = cols
        self.grid = [['.' for _ in range(cols)] for _ in range(rows)]
        self.winning_condition = winning_condition
        self.XO = XO
        self.last_move = []
        self.hard_ai = 2 # thay đổi trong hàm change_hard_ai()
        self.turn = 1
        self.ai_turn = 2
        self.is_use_ai = False

    def reset(self):
        '''
            Reset the game board.
        '''
        self.grid = [['.' for _ in range(self.cols)] for _ in range(self.rows)]
        self.last_move = []
        self.turn = 1
        self.XO = self.originXO

    def get_possible_moves(self) -> list[list[int]]:
        '''
            Get all possible moves of the current board, represents by a list of 2d arrays.
        '''
        possible_moves = []
        for x in range(self.rows):
            for y in range(self.cols):
                if self.grid[x][y] == '.':
                    possible_moves.append([x, y])
        return possible_moves
    
    def get_all_rows(self) -> list[list[str]]:
        '''
            Return all rows of the current grid 
        '''

        return self.grid

    def get_all_colummns(self) -> list[list[str]]:
        '''
            Return all columns of the current grid
        '''

        columns = []
        for y in range(self.cols):
            col = []
            for x in range(self.rows):
                col.append(self.grid[x][y]) 
            columns.append(col)

        return columns
    
    def get_all_diagonals(self) -> list[list[str]]:
            '''
                Return all diagonals of the current grid 
            '''
            diagonals = []
            for y in range(self.cols):
                diagonal = []
                x = 0
                while x < self.rows and y < self.cols:  
                    diagonal.append(self.grid[x][y])

                    x += 1
                    y += 1

                diagonals.append(diagonal)
            for x in range(1, self.rows):
                diagonal = []
                y = 0
                while x < self.rows and y < self.cols: 
                    diagonal.append(self.grid[x][y])

                    x += 1
                    y += 1

                diagonals.append(diagonal)

            for y in range(self.cols):
                diagonal = []
                x = self.rows - 1
                while x >= 0 and y < self.cols:  
                    diagonal.append(self.grid[x][y])

                    x -= 1
                    y += 1

                diagonals.append(diagonal)

            for x in range(0, self.rows - 1):
                diagonal = []
                y = 0
                while x >= 0 and y < self.cols: 
                    diagonal.append(self.grid[x][y])

                    x -= 1
                    y += 1

                diagonals.append(diagonal)

            return diagonals
    
    
    def is_terminate(self) -> bool:
        '''
            Check if the game is terminate (all cells are played).
        '''
        for x in range(self.rows):
            for y in range(self.cols):
                if self.grid[x][y] == '.':
                    return False
        return True
    
    def get_winner(self) -> int:
        '''
            Return the winner of the current board state:
            - 0 if the winner plays 'X'.
            - 1 if the winner plays 'O'.
            - -1 if no player is winning.
            - 2 if draw
        '''

        def check_consecutive(cons: list[list[str]]) -> int:
            for con in cons:
                count_x = 0
                count_y = 0
                for c in con:
                    if c == 'X':
                        count_x += 1    
                        count_y = 0
                    elif c == 'O':
                        count_y += 1
                        count_x = 0
                    else:
                        count_x = 0
                        count_y = 0
                    
                    if count_x == self.winning_condition:
                        return 0

                    if count_y == self.winning_condition: 
                        return 1
            return -1

        rows = self.get_all_rows()
        cols = self.get_all_colummns()
        diagonals = self.get_all_diagonals()

        winner = -1
        winner = check_consecutive(rows)
        if winner != -1:
            return winner

        winner = check_consecutive(cols)
        if winner != -1:
            return winner
        
        winner = check_consecutive(diagonals)
        if winner != -1:
            return winner
        
        if (self.is_terminate()):
            if winner == -1:
                return 2
        
        return winner
                

    
    def make_move(self, x: int, y: int) -> None:
        '''
            Making a move to the board. The value of self.char will be automatically switched after this turn.

            Parameter
            -----------
            x (int): The x-coordinate of the move.

            y (int): The y-coordinate of the move.
        '''
        if self.grid[x][y] != '.':
            return

        self.grid[x][y] = self.XO
        move = (x, y)
        self.last_move.append(move)
        # print(self.last_move)
        if self.XO == 'X':
            self.XO = 'O'
        else:
            self.XO = 'X'
        
        if self.turn == 1:
            self.turn = 2
        else:
            self.turn = 1

    def change_hard_ai(self, hard: str):
        if hard == 'easy':
            self.hard_ai = 1
        elif hard == 'hard':
            self.hard_ai = 3
        elif hard == 'medium':
            self.hard_ai = 2
        else:
            self.hard_ai = 2
    
    def use_ai(self, is_true: bool):
        if is_true == False:
            self.is_use_ai = False
        else:
            self.is_use_ai = True
    
    def set_ai_turn(self, turn: int):
        if turn == 1:
            self.ai_turn = 1
        else:
            self.ai_turn = 2

    def random_ai(self):
        if self.ai_turn == self.turn:
            posible_move = self.get_possible_moves()
            move = random.choice(posible_move)
            self.make_move(move[0], move[1])
            return True
        return False
    
    def get_current_XO_for_AI(self) -> str:
        if self.originXO == "X":
            if self.ai_turn == 2:
                return 'O'
            else:
                return 'X'
        else:
            if self.ai_turn == 1:
                return 'O'
            else:
                return 'X'
        



# Test
if __name__ == '__main__':
    game = Caro()

