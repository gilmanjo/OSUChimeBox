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
from timeit import default_timer as timer

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
LIGHT_1_MUX = (1, 0, 0)
LIGHT_2_MUX = (0, 1, 0)
LIGHT_3_MUX = (1, 1, 0)
LIGHT_4_MUX = (0, 0, 1)
LIGHT_5_MUX = (1, 0, 1)
LIGHT_PWR_MUX = (0, 1, 1)
LIGHT_NONE = (1, 1, 1)

SPI_PORT = 0
SPI_DEVICE = 0

FULL_PATH = "/home/pi/OSUChimeBox/ChimeBox/"
CHIME_FN_CHAINSAW = FULL_PATH + "chainsaw.mp3"
CHIME_FN_FIGHT_SONG = FULL_PATH + "fight_song.mp3"
CHIME_FN_FIRST_DOWN = FULL_PATH + "first_down.mp3"
CHIME_FN_HYPE = FULL_PATH + "hype.mp3"
CHIME_FN_OSU = FULL_PATH + "osu.mp3"
CHIME_FN_TOUCHDOWN = FULL_PATH + "touchdown.mp3"

AY_LIGHT = (LIGHT_0_MUX, LIGHT_1_MUX,
	LIGHT_2_MUX, LIGHT_3_MUX,
	LIGHT_4_MUX, LIGHT_5_MUX)
AY_CHIME = (CHIME_FN_CHAINSAW, CHIME_FN_FIGHT_SONG,
	CHIME_FN_FIRST_DOWN, CHIME_FN_HYPE,
	CHIME_FN_OSU, CHIME_FN_TOUCHDOWN)

class LightState(Enum):
	IDLE = 1
	PULSE = 2
	QUIT = 3

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
		pg.mixer.music.set_volume(0.2)
		pg.mixer.music.load(audio_file)
		pg.mixer.music.play()

	def stop_audio(self):
		pg.mixer.music.stop()

	def playing(self):
		return pg.mixer.music.get_busy()

class LightController(object):
	def __init__(self, lock):
		super(LightController, self).__init__()
		self.state = LightState.IDLE
		self.pulser = 0
		self.lock = lock
		self.pulse_timer = timer()
		self.pulse_active = True

	def _set_light(self, light_num):
		GPIO.output((PIN_S0, PIN_S1, PIN_S2), AY_LIGHT[light_num])

	def _set_pwr_light(self):
		GPIO.output((PIN_S0, PIN_S1, PIN_S2), LIGHT_PWR_MUX)

	def _set_lights_off(self):
		GPIO.output((PIN_S0, PIN_S1, PIN_S2), LIGHT_NONE)

	def reset(self):
		pass

	def idle(self):
		self._set_light(0)
		self._set_light(1)
		self._set_light(2)
		self._set_light(3)
		self._set_light(4)
		self._set_light(5)
		self._set_pwr_light()

	def pulse(self, num):
		if timer() - self.pulse_timer > 0.3:
			self.pulse_timer = timer()
			self.pulse_active = not self.pulse_active

		if self.pulse_active:
			self._set_light(num)

		self._set_pwr_light()
		self._set_lights_off()

	def run(self):
		while True:
			self._set_lights_off()
			self.lock.acquire()
			state = self.state
			self.lock.release()
			if state == LightState.QUIT:
				quit()
			elif state == LightState.IDLE:
				self.idle()
			elif state == LightState.PULSE:
				self.lock.acquire()
				light_num = self.pulser
				self.lock.release() 
				self.pulse(light_num)
			
class ButtonController(object):
	def __init__(self):
		super(ButtonController, self).__init__()
		GPIO.output(PIN_BR0, 0)
		GPIO.output(PIN_BR1, 0)
		GPIO.output(PIN_BR2, 0)
		self.selected_button = -1

		GPIO.add_event_detect(PIN_BC0, GPIO.FALLING, callback=self.check_button_matrix, bouncetime=200)
		GPIO.add_event_detect(PIN_BC1, GPIO.FALLING, callback=self.check_button_matrix, bouncetime=200)

	def _update_selection(self, num):
		self.selected_button = num
		GPIO.output(PIN_BR0, 0)
		GPIO.output(PIN_BR1, 0)
		GPIO.output(PIN_BR2, 0)

	def check_button_matrix(self, channel):
		GPIO.output(PIN_BR0, 1)
		GPIO.output(PIN_BR1, 1)
		GPIO.output(PIN_BR2, 1)

		GPIO.output(PIN_BR0, 0)
		if GPIO.input(PIN_BC0) == 0:
			self._update_selection(0)
			return
		elif GPIO.input(PIN_BC1) == 0:
			self._update_selection(1)
			return

		GPIO.output(PIN_BR0, 1)
		GPIO.output(PIN_BR1, 0)
		if GPIO.input(PIN_BC0) == 0:
			self._update_selection(2)
			return
		elif GPIO.input(PIN_BC1) == 0:
			self._update_selection(3)
			return

		GPIO.output(PIN_BR1, 1)
		GPIO.output(PIN_BR2, 0)
		if GPIO.input(PIN_BC0) == 0:
			self._update_selection(4)
			return
		elif GPIO.input(PIN_BC1) == 0:
			self._update_selection(5)
			return

		self._update_selection(-1)

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

	def _deinit(self, light_thread):
		self.lock.acquire()
		self.lights.state = LightState.QUIT
		self.lock.release()
		light_thread.join()
		GPIO.cleanup()

	def run(self):
		print("CHIME BOX:: Starting...")
		light_thread = threading.Thread(target=self.lights.run)
		light_thread.start()
		while True:
			try:
				time.sleep(0.02)

				if self.buttons.selected_button != -1:
					self.button_pressed(self.buttons.selected_button)
				
				if self.buttons.check_pwr_button():
					print("CHIME BOX:: Powering off...")
					self._deinit(light_thread)
					subprocess.call(["sudo shutdown", "-h", "now"], shell=False)
					quit()

			except KeyboardInterrupt:
				print("\nCHIME BOX:: Exiting...")
				self._deinit(light_thread)
				quit()

	def button_pressed(self, button_num):
		
		if button_num == -1:
			return

		self.buttons.selected_button = -1

		self.music_player.play_audio(AY_CHIME[button_num])
		self.display.show_img(button_num)
		self.lock.acquire()
		self.lights.pulser = button_num
		self.lights.state = LightState.PULSE
		self.lock.release()

		while self.music_player.playing() and self.buttons.selected_button != button_num:
			time.sleep(0.01)

		self.music_player.stop_audio()
		self.lock.acquire()
		self.lights.state = LightState.IDLE
		self.lock.release()
		self.lights.reset()
		self.display.reset()

		self.buttons.selected_button = -1

if __name__ == '__main__':
	chimebox = ChimeBox()
	chimebox.run()