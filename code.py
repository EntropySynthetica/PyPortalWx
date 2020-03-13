import sys
import time
import board
import busio
import terminalio  # For using the terminal basic font
import adafruit_adt7410  # For polling the onboard 7410 Temp Sensor
from adafruit_pyportal import PyPortal
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text import label

cwd = ("/"+__file__).rsplit('/', 1)[0] # the current working directory (where this file is)

# Get wifi details and more from a secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

print("Hello Pyportal")

# Initialize the ADT7410 Temp Sensor
i2c_bus = busio.I2C(board.SCL, board.SDA)
adt = adafruit_adt7410.ADT7410(i2c_bus, address=0x48)
adt.high_resolution = True

temperature = adt.temperature
temperature = (temperature * 1.8 +32)
print(temperature)

display = board.DISPLAY

while True:
    print("Temp:")
    temperature = adt.temperature
    temperature = (temperature * 1.8 +32)
    print(temperature)

    # Set text, font, and color
    temp_in_text = "Temp In: " + str(temperature)
    #font = bitmap_font.load_font("/fonts/Helvetica-Bold-16.bdf")
    font = bitmap_font.load_font("/fonts/Arial-ItalicMT-17.bdf")
    color = 0x0000FF
    
    # Create the test label
    temp_in_text_area = label.Label(font, text=temp_in_text, color=color)
    
    # Set the location
    temp_in_text_area.x = 90
    temp_in_text_area.y = 100
    
    # Show it
    display.show(temp_in_text_area)

    time.sleep(1)
