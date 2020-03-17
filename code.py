import sys
import time
import board
import busio
import neopixel
import rtc # For interfacing with the Real Time Clock
import terminalio  # For using the terminal basic font
import displayio # Library for writing text / graphics to the screen
import adafruit_imageload # Library to load our background
import adafruit_adt7410  # For polling the onboard 7410 Temp Sensor
from digitalio import DigitalInOut # Enabling DigitalIO so we can talk to the ESP32 Wifi chip.
#from adafruit_pyportal import PyPortal
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text import label
from adafruit_esp32spi import adafruit_esp32spi, adafruit_esp32spi_wifimanager

cwd = ("/"+__file__).rsplit('/', 1)[0] # the current working directory (where this file is)

# Get wifi details and more from a secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

# PyPortal ESP32 Setup
esp32_cs = DigitalInOut(board.ESP_CS)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)
status_light = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.2)
wifi = adafruit_esp32spi_wifimanager.ESPSPI_WiFiManager(esp, secrets, status_light)

# Initialize the ADT7410 Temp Sensor
i2c_bus = busio.I2C(board.SCL, board.SDA)
adt = adafruit_adt7410.ADT7410(i2c_bus, address=0x48)
adt.high_resolution = True

# Initialize the Real Time Clock
the_rtc = rtc.RTC()

# Initialize the Display
display = board.DISPLAY

# Set some Global variables
time_api = "http://worldtimeapi.org/api/ip"
font = bitmap_font.load_font("/fonts/Arial-ItalicMT-17.bdf")
color = 0x0000FF

print("Initializing")
wifi.connect()

def sync_rtc(time_api):
    # Get the time from the time api server. 
    response = None
    while True:
        try:
            print("Fetching time from", time_api)
            response = wifi.get(time_api)
            break
        except (ValueError, RuntimeError) as e:
            print("Failed to get data, retrying\n", e)
            continue

    # Parse the time out of the API Response
    json = response.json()
    current_time = json['datetime']
    the_date, the_time = current_time.split('T')
    year, month, mday = [int(x) for x in the_date.split('-')]
    the_time = the_time.split('.')[0]
    hours, minutes, seconds = [int(x) for x in the_time.split(':')]
    year_day = json['day_of_year']
    week_day = json['day_of_week']
    is_dst = json['dst']

    # Update the RTC
    now = time.struct_time((year, month, mday, hours, minutes, seconds, week_day, year_day, is_dst))
    print(now)
    the_rtc.datetime = now

def get_current_wx(cityid, api_key):
    poll_URL = "https://api.openweathermap.org/data/2.5/weather?id=" + cityid + "&units=imperial&appid=" + api_key 

    response = None
    while True:
        try:
            print("Fetching weather from", poll_URL)
            response = wifi.get(poll_URL)
            break
        except (ValueError, RuntimeError) as e:
            print("Failed to get data, retrying\n", e)
            continue

    json = response.json()
    return json

def get_temp_in():
    temperature = adt.temperature
    temperature = round((temperature * 1.8 +32),1)
    return temperature

sync_rtc(time_api)
temp_in = get_temp_in()
current_wx = get_current_wx(secrets['owm_cityid'], secrets['owm_apikey'])

time.sleep(10)

while True:
    # Load the current time from the RTC
    now = time.localtime()

    # Update the internal temp only once per min at 10 seconds past. 
    if (now[5] == 10):
        temp_in = get_temp_in()

    # Resync the clock at 11 min past the hour.  
    if ((now[4] == 11) and (now[5] == 0)):
        sync_rtc(time_api)

    # Resync the weather every 10 min.
    if (now[4] % 10 == 0) and (now[5] == 0):
        current_wx = get_current_wx(secrets['owm_cityid'], secrets['owm_apikey'])

    # Display Indoor Temp
    temp_in_text = "Temp In: " + str(temp_in)
    temp_in_text_area = label.Label(font, text=temp_in_text, color=color)
    temp_in_text_area.x = 190
    temp_in_text_area.y = 90
    text1_group = displayio.Group()
    text1_group.append(temp_in_text_area)
    
    # Figure out if we are AM or PM and convert the clock to 12 hour.
    if (now[3] >= 12):
        time_tag = "PM"
    else:
        time_tag = "AM"

    if (now[3] >= 13):
        time_hour = str(now[3] - 12)
    elif (now[3] == 0):
        time_hour = "12"
    else:
        time_hour = str(now[3])

    # Display Time
    timenow = time_hour + ":" + str("{:02d}".format(now[4])) + ":" + str("{:02d}".format(now[5])) + " " + time_tag
    time_text = timenow
    time_text_area = label.Label(font, text=time_text, color=color)
    time_text_area.x = 220
    time_text_area.y = 10
    text2_group = displayio.Group()
    text2_group.append(time_text_area)

    # Display Date
    day_name = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat','Sun']
    month_name = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    day_name = day_name[now[6]]
    month_name = month_name[now[1] - 1]
    datenow = day_name + " " + month_name + " " + str(now[2])
    date_text = datenow
    date_text_area = label.Label(font, text=date_text, color=color)
    date_text_area.x = 220
    date_text_area.y = 30
    text3_group = displayio.Group()
    text3_group.append(date_text_area)

    # Display Outdoor Temp
    temp_out_text = "Temp Out: " + str(round(current_wx['main']['temp'],1))
    temp_out_text_area = label.Label(font, text=temp_out_text, color=color)
    temp_out_text_area.x = 190
    temp_out_text_area.y = 110
    text4_group = displayio.Group()
    text4_group.append(temp_out_text_area)

    # Current Conditions
    city_out_text = "Conditions in " + current_wx['name']
    city_out_text_area = label.Label(font, text=city_out_text, color=color)
    city_out_text_area.x = 10
    city_out_text_area.y = 10
    text5_group = displayio.Group()
    text5_group.append(city_out_text_area)

    # Display Conditions
    conditions_out_text = current_wx['weather'][0]['description']
    conditions_out_text_area = label.Label(font, text=conditions_out_text, color=color)
    conditions_out_text_area.x = 10
    conditions_out_text_area.y = 30
    text6_group = displayio.Group()
    text6_group.append(conditions_out_text_area)

    # Show everything on screen.
    group = displayio.Group(max_size=6)
    group.append(text1_group)
    group.append(text2_group)
    group.append(text3_group)
    group.append(text4_group)
    group.append(text5_group)
    group.append(text6_group)

    display.show(group)

    # Our Screen Refresh Rate
    time.sleep(0.5)
