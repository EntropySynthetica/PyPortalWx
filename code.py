import sys
import time
import board
import adafruit_adt7410
import busio
from adafruit_pyportal import PyPortal
from adafruit_display_text.label import Label

cwd = ("/"+__file__).rsplit('/', 1)[0] # the current working directory (where this file is)

# Get wifi details and more from a secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

print("Hello Pyportal")

i2c_bus = busio.I2C(board.SCL, board.SDA)
adt = adafruit_adt7410.ADT7410(i2c_bus, address=0x48)
adt.high_resolution = True

temperature = adt.temperature

print(temperature)

