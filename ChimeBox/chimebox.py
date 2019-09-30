import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setup(16, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(16, GPIO.RISING)
GPIO.setup(24, GPIO.OUT)

while True:
	
	time.sleep(0.03)

	if GPIO.event_detected(16):
		GPIO.output(24, GPIO.input(24))