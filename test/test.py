class x:
    def __init__(self) -> None:
        self.rows = 4
        self.cols = 6
        self.grid = [['.' for _ in range(self.cols)] for _ in range(self.rows)]
        k = 0
        for i in range(self.rows):
            for j in range(self.cols):
                self.grid[i][j] = k
                k += 1

    def print2(self):
        for i in range(self.rows):
            for j in range(self.cols):
                print(self.grid[i][j], end=", ")
            print()

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
    
tmp = x()
tmp.print2()
print(tmp.get_all_diagonals())