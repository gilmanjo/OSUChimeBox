from PIL import Image
import Adafruit_ILI9341 as TFT
import Adafruit_GPIO as AGPIO
import RPi.GPIO as GPIO
import Adafruit_GPIO.SPI as SPI
import sys
from enum import Enum
import pygame as pg
import os
import subprocess
import threading
import time

PIN_PWR_BTN = 3
PIN_S0 = 4
PIN_S1 = 17
PIN_S2 = 27
PIN_TFT_DC = 22
PIN_TFT_RESET = 23
PIN_BR0 = 24
PIN_BR1 = 25
PIN_BR2 = 5
PIN_BC0 = 6
PIN_BC1 = 12

LIGHT_0_MUX = (0, 0, 0)
LIGHT_1_MUX = (0, 0, 1)
LIGHT_2_MUX = (0, 1, 0)
LIGHT_3_MUX = (0, 1, 1)
LIGHT_4_MUX = (1, 0, 0)
LIGHT_5_MUX = (1, 0, 1)
LIGHT_PWR_MUX = (1, 1, 0)
LIGHT_NONE = (1, 1, 1)

SPI_PORT = 0
SPI_DEVICE = 0

SONG_END = pg.USEREVENT + 1

CHIME_FN_CHAINSAW = "chainsaw.mp3"
CHIME_FN_FIGHT_SONG = "fight_song.mp3"
CHIME_FN_FIRST_DOWN = "first_down.mp3"
CHIME_FN_HYPE = "hype.mp3"
CHIME_FN_OSU = "osu.mp3"
CHIME_FN_TOUCHDOWN = "touchdown.mp3"

AY_LIGHT = (LIGHT_0_MUX, LIGHT_1_MUX,
	LIGHT_2_MUX, LIGHT_3_MUX,
	LIGHT_4_MUX, LIGHT_5_MUX)
AY_CHIME = (CHIME_FN_CHAINSAW, CHIME_FN_FIGHT_SONG,
	CHIME_FN_FIRST_DOWN, CHIME_FN_HYPE,
	CHIME_FN_OSU, CHIME_FN_TOUCHDOWN)

class LightState(Enum):
	IDLE = 1
	PULSE = 2

class MusicPlayer(object):
	def __init__(self):
		super(MusicPlayer, self).__init__()
		self.freq = 44100
		self.bitsize = -16
		self.channels = 2
		self.buffer = 2048
		pg.mixer.init(self.freq, self.bitsize, self.channels, self.buffer)

	def play_audio(self, audio_file):
		print("MUSIC PLAYER:: Playing audio file: " + audio_file)
		clock = pg.time.Clock()
		pg.mixer.music.set_endevent(SONG_END)
		pg.mixer.music.set_volume(0.25)
		pg.mixer.music.load(audio_file)
		pg.mixer.music.play()

	def playing(self):
		return pg.mixer.music.get_busy()

class LightController(object):
	def __init__(self, lock):
		super(LightController, self).__init__()
		self.state = LightState.IDLE
		self.pulser = 0
		self.lock = lock

	def _set_light(self, light_num):
		GPIO.output(PIN_S0, AY_LIGHT[light_num][0])
		GPIO.output(PIN_S0, AY_LIGHT[light_num][1])
		GPIO.output(PIN_S0, AY_LIGHT[light_num][2])

	def reset(self):
		pass

	def pulse(self, num):
		pass

	def run(self):
		while True:
			time.sleep(0.02)
			self._set_light(0)
			time.sleep(0.02)
			self._set_light(1)
			time.sleep(0.02)
			self._set_light(2)
			time.sleep(0.02)
			self._set_light(3)
			time.sleep(0.02)
			self._set_light(4)
			time.sleep(0.02)
			self._set_light(5)

class ButtonController(object):
	def __init__(self):
		super(ButtonController, self).__init__()
		GPIO.output(PIN_BR0, 1)
		GPIO.output(PIN_BR1, 1)
		GPIO.output(PIN_BR2, 1)

	def check_button_matrix(self):
		GPIO.output(PIN_BR0, 0)
		if GPIO.input(PIN_BC0) == 0:
			print("BUTTON CONTROLLER:: Button 0 pressed")
			return 0
		elif GPIO.input(PIN_BC1) == 0:
			print("BUTTON CONTROLLER:: Button 1 pressed")
			return 1

		GPIO.output(PIN_BR0, 1)
		GPIO.output(PIN_BR1, 0)
		if GPIO.input(PIN_BC0) == 0:
			print("BUTTON CONTROLLER:: Button 2 pressed")
			return 2
		elif GPIO.input(PIN_BC1) == 0:
			print("BUTTON CONTROLLER:: Button 3 pressed")
			return 3

		GPIO.output(PIN_BR1, 1)
		GPIO.output(PIN_BR2, 0)
		if GPIO.input(PIN_BC0) == 0:
			print("BUTTON CONTROLLER:: Button 4 pressed")
			return 4
		elif GPIO.input(PIN_BC1) == 0:
			print("BUTTON CONTROLLER:: Button 5 pressed")
			return 5

		GPIO.output(PIN_BR2, 1)
		return -1

	def check_pwr_button(self):
		return not GPIO.input(PIN_PWR_BTN)
		
class Display(object):
	def __init__(self):
		super(Display, self).__init__()

	def reset(self):
		pass

	def show_img(self, img_num):
		pass
		
class ChimeBox(object):
	def __init__(self):
		super(ChimeBox, self).__init__()

		print("CHIME BOX:: Initializing...")
		GPIO.setwarnings(False)
		GPIO.setmode(GPIO.BCM)
		GPIO.setup(PIN_PWR_BTN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
		GPIO.setup(PIN_BR0, GPIO.OUT)
		GPIO.setup(PIN_BR1, GPIO.OUT)
		GPIO.setup(PIN_BR2, GPIO.OUT)
		GPIO.setup(PIN_BC0, GPIO.IN, pull_up_down=GPIO.PUD_UP)
		GPIO.setup(PIN_BC1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
		GPIO.setup(PIN_S0, GPIO.OUT)
		GPIO.setup(PIN_S1, GPIO.OUT)
		GPIO.setup(PIN_S2, GPIO.OUT)

		self.lock = threading.Lock()
		self.music_player = MusicPlayer()
		self.lights = LightController(self.lock)
		self.buttons = ButtonController()
		self.display = Display()

	def run(self):
		print("CHIME BOX:: Starting...")
		light_thread = threading.Thread(target=self.lights.run)
		light_thread.start()
		while True:
			try:
				time.sleep(0.02)
				pressed_button = self.buttons.check_button_matrix()
				self.button_pressed(pressed_button)
				
				if self.buttons.check_pwr_button():
					print("CHIME BOX:: Powering off...")
					GPIO.cleanup()
					subprocess.call(["shutdown", "-h", "now"], shell=False)
					quit()

			except KeyboardInterrupt:
				print("\nCHIME BOX:: Exiting...")
				GPIO.cleanup()
				quit()

	def button_pressed(self, button_num):
		
		if button_num == -1:
			return

		self.music_player.play_audio(AY_CHIME[button_num])
		self.display.show_img(button_num)

		while self.music_player.playing() and self.buttons.check_button_matrix() != button_num:
			time.sleep(0.02)
			self.lights.pulse(button_num)

		self.lights.reset()
		self.display.reset()

if __name__ == '__main__':
	chimebox = ChimeBox()
	chimebox.run()