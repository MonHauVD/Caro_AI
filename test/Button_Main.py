import pygame
import Buttons as button

#create display window
SCREEN_HEIGHT = 500
SCREEN_WIDTH = 800

screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption('Button Demo')

#load button images
start_img = pygame.image.load('Caro/asset/start_btn.png').convert_alpha()
# exit_img = pygame.image.load('Caro/asset/X_caro.png').convert_alpha()
exit_img = pygame.transform.smoothscale(pygame.image.load('Caro/asset/exit_btn.png').convert_alpha(), (240, 105))
#create button instances
start_button = button.Button(100, 200, start_img, 0.8)
exit_button = button.Button(450, 200, exit_img, 0.8)

#game loop
run = True
while run:

	screen.fill((202, 228, 241))

	if start_button.draw(screen):
		print('START')
	if exit_button.draw(screen):
		print('EXIT')
		#quit game
		run = False

	#event handler
	for event in pygame.event.get():
		#quit game
		if event.type == pygame.QUIT:
			run = False

	pygame.display.update()

pygame.quit()