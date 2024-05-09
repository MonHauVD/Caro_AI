from turtle import Screen
import Buttons as button
import pygame
import sys
import caro
import os

# -------------------------Setup----------------------------
# Định nghĩa màu

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (77, 199, 61)
RED = (199, 36, 55)
BLUE = (68, 132, 222)   

# Kí hiệu lúc ban đầu
XO = 'X'
FPS = 120
# Số hàng, cột
ROWNUM = 25
COLNUM = 30
# Số dòng thắng
winning_condition = 5

my_game = caro.Caro(ROWNUM, COLNUM, winning_condition, XO)

Window_size = [1280, 720]


my_len_min = min(900/COLNUM, (Window_size[1])/ ROWNUM)
# Độ dày đường kẻ
MARGIN = my_len_min/15
my_len_min = min((900 - MARGIN*3)/COLNUM, (Window_size[1]- MARGIN*3)/ ROWNUM)
my_len_min - my_len_min - MARGIN
# Chiều dài, rộng mỗi ô
WIDTH = my_len_min
HEIGHT = my_len_min

Screen = pygame.display.set_mode(Window_size)
# path = "Caro/asset"
path = os.getcwd()
path = os.path.join(path, './asset')

# ------------------------------Load asset----------------------------------------
x_img = pygame.transform.smoothscale(pygame.image.load(path + "/X_caro.png").convert_alpha(),(my_len_min,my_len_min))
o_img = pygame.transform.smoothscale(pygame.image.load(path + "/O_caro.png").convert_alpha(),(my_len_min,my_len_min))
#load button images
start_img = pygame.transform.smoothscale(pygame.image.load(path + '/start_btn.png').convert_alpha(), (240, 105))
exit_img = pygame.transform.smoothscale(pygame.image.load(path + '/exit_btn.png').convert_alpha(), (240, 105))
replay_img = pygame.transform.smoothscale(pygame.image.load(path + '/replay_btn.png').convert_alpha(), (240, 105))
undo_img = pygame.transform.smoothscale(pygame.image.load(path + '/undo_btn.png').convert_alpha(), (240, 105))
ai_img = pygame.transform.smoothscale(pygame.image.load(path + '/ai_btn.png').convert_alpha(), (105, 105))
person_img = pygame.transform.smoothscale(pygame.image.load(path + '/person_btn.png').convert_alpha(), (105, 105))
ai_img_gray = pygame.transform.smoothscale(pygame.image.load(path + '/ai_btn_gray.jpg').convert_alpha(), (105, 105))
person_img_gray = pygame.transform.smoothscale(pygame.image.load(path + '/person_btn_gray.jpg').convert_alpha(), (105, 105))
h_img = pygame.transform.smoothscale(pygame.image.load(path + '/h_btn.png').convert_alpha(), (80, 80))
h_img_gray = pygame.transform.smoothscale(pygame.image.load(path + '/h_btn_gray.png').convert_alpha(), (80, 80))
m_img = pygame.transform.smoothscale(pygame.image.load(path + '/m_btn.png').convert_alpha(), (80, 80))
m_img_gray = pygame.transform.smoothscale(pygame.image.load(path + '/m_btn_gray.png').convert_alpha(), (80, 80))
e_img = pygame.transform.smoothscale(pygame.image.load(path + '/e_btn.png').convert_alpha(), (80, 80))
e_img_gray = pygame.transform.smoothscale(pygame.image.load(path + '/e_btn_gray.png').convert_alpha(), (80, 80))
pvp_img = pygame.transform.smoothscale(pygame.image.load(path + '/player_vs_player.jpg').convert_alpha(), (105, 105))
pvp_img_gray = pygame.transform.smoothscale(pygame.image.load(path + '/player_vs_player_gray.jpg').convert_alpha(), (105, 105))
aivp_img = pygame.transform.smoothscale(pygame.image.load(path + '/ai_vs_player.jpg').convert_alpha(), (105, 105))
aivp_img_gray = pygame.transform.smoothscale(pygame.image.load(path + '/ai_vs_player_gray.jpg').convert_alpha(), (105, 105))
ai_thinking_img = pygame.transform.smoothscale(pygame.image.load(path + '/ai_thinking.png').convert_alpha(), (105, 105))
ai_thinking_img_gray = pygame.transform.smoothscale(pygame.image.load(path + '/ai_thinking_gray.png').convert_alpha(), (105, 105))
#create button instances
# start_button = button.Button(1000, 200, start_img, 0.8)
replay_button = button.Button(970, 575, replay_img, replay_img, 0.8)
exit_button = button.Button(970, 485, exit_img, exit_img, 0.8)
undo_button =  button.Button(970, 395, undo_img, undo_img, 0.8)
ai_btn = button.Button(970, 305, ai_img, ai_img_gray, 0.8)
person_btn = button.Button(1075, 305, person_img, person_img_gray, 0.8)
h_btn = button.Button(1100, 235, h_img, h_img_gray, 0.8)
m_btn = button.Button(1035, 235, m_img, m_img_gray, 0.8)
e_btn = button.Button(970, 235, e_img, e_img_gray, 0.8)
ai_thinking_btn = button.Button(1020, 30, ai_thinking_img, ai_thinking_img_gray, 0.8)
pvp_btn = button.Button(1075, 145, pvp_img, pvp_img_gray, 0.8)
aivp_btn = button.Button(970, 145, aivp_img, aivp_img_gray, 0.8)

person_btn.disable_button()
m_btn.disable_button()
pvp_btn.disable_button()
ai_thinking_btn.disable_button()
pygame.init()





# Loop until the user clicks the close button.
done = False
status = None
# Used to manage how fast the screen updates
clock = pygame.time.Clock()

def logo():
    font = pygame.font.Font('freesansbold.ttf', 36)
    text = font.render('By nhóm 2', True, WHITE, BLACK)
    textRect = text.get_rect()
    textRect.center = (1100, 700)
    Screen.blit(text,textRect)

def draw(this_game : caro.Caro, this_screen):
    logo()
    for row in range(ROWNUM):
        for column in range(COLNUM):
            color = WHITE
            if len(this_game.lastMove) > 0:
                lastmove_row, lastmove_col = this_game.lastMove[-1][0], this_game.lastMove[-1][1]
                if row == lastmove_row and column == lastmove_col:
                    color = GREEN
            pygame.draw.rect(this_screen,
                             color,
                              [(MARGIN + WIDTH) * column + MARGIN,
                              (MARGIN + HEIGHT) * row + MARGIN,
                              WIDTH,
                              HEIGHT])
            if this_game.grid[row][column] == 'X': 
                this_screen.blit(x_img,((WIDTH + MARGIN)*column + MARGIN,(HEIGHT + MARGIN)*row + MARGIN))
            if this_game.grid[row][column] == 'O':
                this_screen.blit(o_img,((WIDTH + MARGIN)*column + MARGIN,(HEIGHT + MARGIN)*row + MARGIN))

def re_draw():
    logo()
    Screen.fill(BLACK)
    for row in range(ROWNUM):
        for column in range(COLNUM):
            color = WHITE
            pygame.draw.rect(Screen,
                             color,
                              [(MARGIN + WIDTH) * column + MARGIN,
                              (MARGIN + HEIGHT) * row + MARGIN,
                              WIDTH,
                              HEIGHT])



def Undo(self : caro.Caro):
    if self.is_use_ai:
        if len(self.lastMove) > 2:
                last_move = self.lastMove[-1]
                last_move_2 = self.lastMove[-2]
                self.lastMove.pop()
                self.lastMove.pop()  
                # print(self.lastMove)
                # print(last_move, type(last_move), type(last_move[0]))
                row = int(last_move[0])
                col = int(last_move[1])
                row2 = int(last_move_2[0])
                col2 = int(last_move_2[1])
                self.grid[row][col] = '.'
                self.grid[row2][col2] = '.'
                draw(my_game, Screen)
    else:
        if len(self.lastMove) > 0:
            last_move = self.lastMove[-1]
            self.lastMove.pop()
            # print(self.lastMove)
            # print(last_move, type(last_move), type(last_move[0]))
            row = int(last_move[0])
            col = int(last_move[1])
            self.grid[row][col] = '.'
            if self.XO == 'X':
                    self.XO = 'O'
            else:
                self.XO = 'X'
            if self.turn == 1:
                self.turn = 2
            else:
                self.turn = 1
            draw(my_game, Screen)
    pass


# -------- Main Program Loop -----------
while not done:
    for event in pygame.event.get():  # User did something
        # if start_button.draw(Screen):
        #     print('START')
        if len(my_game.lastMove) > 0:
            person_btn.disable_button()
            ai_btn.disable_button()
            h_btn.disable_button()
            m_btn.disable_button()
            e_btn.disable_button()
        if not my_game.is_use_ai:   
            person_btn.disable_button()
            ai_btn.disable_button()
            h_btn.disable_button()
            m_btn.disable_button()
            e_btn.disable_button()
        else:
            if my_game.turn == my_game.ai_turn:
                ai_thinking_btn.enable_button()
                ai_thinking_btn.re_draw(Screen)
                my_game.random_ai()
                draw(my_game, Screen)
                ai_thinking_btn.re_draw(Screen)
                pygame.time.delay(500)
                # ai_thinking_btn.disable_button()
            else:
                ai_thinking_btn.disable_button()
                pass

        if undo_button.draw(Screen): # Ấn nút Undo
            Undo(my_game)
            pass
        if pvp_btn.draw(Screen):
            my_game.use_ai(False)
            pvp_btn.disable_button()
            aivp_btn.enable_button()
            person_btn.disable_button()
            ai_btn.disable_button()
            h_btn.disable_button()
            m_btn.disable_button()
            e_btn.disable_button()
            pass
        if aivp_btn.draw(Screen):
            my_game.use_ai(True)
            aivp_btn.disable_button()
            pvp_btn.enable_button()
            ai_btn.enable_button()
            h_btn.enable_button()
            e_btn.enable_button()
            pass
        if ai_thinking_btn.draw(Screen):
            pass
        if h_btn.draw(Screen):
            h_btn.disable_button()
            m_btn.enable_button()
            e_btn.enable_button()
            my_game.change_hard_ai("hard")
            pass
        if m_btn.draw(Screen):
            h_btn.enable_button()
            m_btn.disable_button()
            e_btn.enable_button()
            my_game.change_hard_ai("medium")
            pass
        if e_btn.draw(Screen):
            h_btn.enable_button()
            m_btn.enable_button()
            e_btn.disable_button()
            my_game.change_hard_ai("easy")
            pass
        if person_btn.draw(Screen):  # Ấn nút Chọn người đi trước
            if my_game.is_use_ai:
                person_btn.disable_button()
                ai_btn.enable_button()
                my_game.set_ai_turn(2)
                print("Human")
            else:
                person_btn.disable_button()
                ai_btn.disable_button()
            pass
        if ai_btn.draw(Screen): # Ấn nút Chọn AI đi trước
            if my_game.is_use_ai:
                ai_btn.disable_button()
                person_btn.enable_button()
                my_game.set_ai_turn(1)
                print("AI")
            else:
                person_btn.disable_button()
                ai_btn.disable_button()
            pass
        if exit_button.draw(Screen): # Ấn nút Thoát
            print('EXIT')
            #quit game
            done = True
        if replay_button.draw(Screen): # Ấn nút Chơi lại
            print('Replay')
            my_game.reset()
            re_draw()
            ai_btn.enable_button()
            h_btn.enable_button()
            e_btn.enable_button()

        if event.type == pygame.QUIT:  # If user clicked close
            done = True  # Flag that we are done so we exit this loop
            # Set the screen background
        if event.type == pygame.MOUSEBUTTONDOWN:
            pos = pygame.mouse.get_pos()
            col = int(pos[0] // (WIDTH + MARGIN))
            row =  int(pos[1] // (HEIGHT + MARGIN))
            # print(pos, col, row)
            if col < COLNUM and row < ROWNUM:
                my_game.make_move(row, col)
            status = my_game.get_winner()

    draw(my_game, Screen)


    if status == 2:
        font = pygame.font.Font('freesansbold.ttf', 100)
        text = font.render('Draw', True, GREEN, BLUE)
        textRect = text.get_rect()
        textRect.center = (int(Window_size[0]/2), int(Window_size[1]/2))
        Screen.blit(text,textRect)
        # done = True
    if status == 0:
        font = pygame.font.Font('freesansbold.ttf', 100)
        text = font.render('X wins', True, RED, GREEN)
        textRect = text.get_rect()
        textRect.center = (int(Window_size[0]/2), int(Window_size[1]/2))
        Screen.blit(text,textRect)
        # done = True
    if status == 1:
        font = pygame.font.Font('freesansbold.ttf', 100)
        text = font.render('O wins', True, BLUE, GREEN)
        textRect = text.get_rect()
        textRect.center = (int(Window_size[0]/2), int(Window_size[1]/2))
        Screen.blit(text,textRect)
        # done = True
# Limit to 999999999 frames per second
    clock.tick(FPS)
 
    # Go ahead and update the screen with what we've drawn.
    pygame.display.update()

pygame.time.delay(50)
quit()
pygame.quit()
sys.exit()