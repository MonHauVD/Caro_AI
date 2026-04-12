import pygame

#button class
class Button():
	def __init__(self, x, y, image, gray_image, scale):
		self.width = image.get_width()
		self.height = image.get_height()
		self.x = x
		self.y = y
		self.image = pygame.transform.scale(image, (int(self.width * scale), int(self.height * scale)))
		self.gray_image = pygame.transform.scale(gray_image, (int(self.width * scale), int(self.height * scale)))
		self.rect = self.image.get_rect()
		self.rect.topleft = (x, y)
		self.clicked = False
		self.is_disable = False

	#draw button

	def draw(self, surface):
		action = False
		#get mouse position
		pos = pygame.mouse.get_pos()

		#check mouseover and clicked conditions
		if self.rect.collidepoint(pos):
			if pygame.mouse.get_pressed()[0] == 1 and self.clicked == False:
				self.clicked = True
				action = True

		if pygame.mouse.get_pressed()[0] == 0:
			self.clicked = False

		#draw button on screen
		if (self.is_disable == False):
			surface.blit(self.image, (self.rect.x, self.rect.y))
		else:
			surface.blit(self.gray_image, (self.rect.x, self.rect.y))

		if self.is_disable == True:
			action = False

		return action
	
	def disable_button(self):
		self.is_disable = True
	def enable_button(self):
		self.is_disable = False

	def re_draw(self, surface):
		if (self.is_disable == False):
			surface.blit(self.image, (self.rect.x, self.rect.y))
		else:
			surface.blit(self.gray_image, (self.rect.x, self.rect.y))