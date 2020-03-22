import sys
import time
import board
import busio
import neopixel
import rtc # For interfacing with the Real Time Clock
import displayio # Library for writing text / graphics to the screen
import adafruit_adt7410  # For polling the onboard 7410 Temp Sensor
from adafruit_display_shapes.rect import Rect # Library to draw rectangles
from digitalio import DigitalInOut # Enabling DigitalIO so we can talk to the ESP32 Wifi chip.
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text import label
from adafruit_esp32spi import adafruit_esp32spi, adafruit_esp32spi_wifimanager

# Get wifi and api secrets
try:
    from secrets import secrets
except ImportError:
    print("Error: Could not load secrets from secrets.py")
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
internal_rtc = rtc.RTC()

# Initialize the Display
display = board.DISPLAY

# Set some Global variables
font = bitmap_font.load_font("/fonts/Arial-ItalicMT-17.bdf")
color_blue = 0x0000FF
color_white = 0xFFFFFF
color_darkpurple = 0x2e0142
color_purple = 0x8323ad
color_darkblue = 0x00004a

print("Initializing")
wifi.connect()

def sync_rtc():
    # Get the time from the time api server. 
    poll_URL = "http://worldtimeapi.org/api/ip"

    response = None
    while True:
        try:
            print("Fetching time from", poll_URL)
            response = wifi.get(poll_URL)
            break
        except (ValueError, RuntimeError) as e:
            print("Failed to get data, retrying\n", e)
            continue

    # Parse the time out of the API Response
    time_json = response.json()
    current_time = time_json['datetime']
    the_date, the_time = current_time.split('T')
    year, month, mday = [int(x) for x in the_date.split('-')]
    the_time = the_time.split('.')[0]
    hours, minutes, seconds = [int(x) for x in the_time.split(':')]

    # Update the RTC
    now = time.struct_time((year, month, mday, hours, minutes, seconds, time_json['day_of_week'], time_json['day_of_year'], time_json['dst']))
    internal_rtc.datetime = now

def get_current_wx(cityid, api_key):
    # Get the current condtions from the weather API server
    poll_URL = "https://api.openweathermap.org/data/2.5/weather?id=" + cityid + "&units=imperial&appid=" + api_key 

    response = None
    while True:
        try:
            print("Fetching weather")
            response = wifi.get(poll_URL)
            break
        except (ValueError, RuntimeError) as e:
            print("Failed to get weather, retrying\n", e)
            continue

    weather_json = response.json()
    return weather_json

def get_forecast_wx(cityid, api_key):
    # Get the weather forecast from the weather API server
    poll_URL = "https://api.openweathermap.org/data/2.5/forecast?id=" + cityid + "&units=imperial&appid=" + api_key 

    response = None
    while True:
        try:
            print("Fetching forecast")
            response = wifi.get(poll_URL)
            break
        except (ValueError, RuntimeError) as e:
            print("Failed to get forecast, retrying\n", e)
            continue

    forecast_json = response.json()
    return forecast_json

def get_temp_in():
    temperature = adt.temperature
    temperature = round((temperature * 1.8 +32),1)
    return temperature

def degree_to_cardinal(wind_degrees):
    # Wind Degrees to Cardinal solution from https://stackoverflow.com/questions/7490660/converting-wind-direction-in-angles-to-text-words
    val=int((wind_degrees/22.5)+.5)
    compass=["N","NNE","NE","ENE","E","ESE", "SE", "SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return compass[(val % 16)]

def get_forecast_for_day(forecast_data, day_num):
    forecast_temps = []
    for item in forecast_data['list']:
        forecast_time = time.localtime(item['dt'])

        if forecast_time[6] == day_num:
            forecast_temps.append(item['main']['temp'])
    forecast_for_day = {'forecast_temps' : forecast_temps}
    forecast_for_day.update({'forecast_high' : max(forecast_temps)})
    forecast_for_day.update({'forecast_low' : min(forecast_temps)})
    return forecast_for_day

sync_rtc()
temp_in = get_temp_in()
current_wx = get_current_wx(secrets['owm_cityid'], secrets['owm_apikey'])
forecast_wx = get_forecast_wx(secrets['owm_cityid'], secrets['owm_apikey'])

now = time.localtime()
forecast = get_forecast_for_day(forecast_wx, 2)
print(forecast['forecast_temps'])
print(forecast['forecast_high'])
print(forecast['forecast_low'])

time.sleep(10)

while True:
    # Load the current time from the RTC
    now = time.localtime()

    # Update the internal temp only once per min at 10 seconds past. 
    if (now[5] == 10):
        temp_in = get_temp_in()

    # Resync the clock at 11 min past the hour.  
    if ((now[4] == 11) and (now[5] == 0)):
        sync_rtc()

    # Resync the current weather conditions every 10 min.
    if (now[4] % 10 == 0) and (now[5] == 0):
        current_wx = get_current_wx(secrets['owm_cityid'], secrets['owm_apikey'])
    
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
    time_text_area = label.Label(font, text=time_text, color=color_white)
    time_text_area.x = 220
    time_text_area.y = 10
    time_text_group = displayio.Group()
    time_text_group.append(time_text_area)

    # Display Date
    day_name = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat','Sun']
    month_name = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    day_name = day_name[now[6]]
    month_name = month_name[now[1] - 1]
    datenow = day_name + " " + month_name + " " + str(now[2])
    date_text = datenow
    date_text_area = label.Label(font, text=date_text, color=color_white)
    date_text_area.x = 220
    date_text_area.y = 30
    date_text_group = displayio.Group()
    date_text_group.append(date_text_area)

    # Display Outdoor Temp
    temp_out_text = "Temp Out: " + str(round(current_wx['main']['temp'],1))
    temp_out_text_area = label.Label(font, text=temp_out_text, color=color_white)
    temp_out_text_area.x = 180
    temp_out_text_area.y = 90
    temp_out_text_group = displayio.Group()
    temp_out_text_group.append(temp_out_text_area)

    # Display Wind
    wind_dir = degree_to_cardinal(current_wx['wind']['deg'])
    wind_text = "Wind: " + str(round(current_wx['wind']['speed'],0)) + " " + wind_dir
    wind_text_area = label.Label(font, text=wind_text, color=color_white)
    wind_text_area.x = 180
    wind_text_area.y = 110
    wind_text_group = displayio.Group()
    wind_text_group.append(wind_text_area)

    # Display Humidity
    hum_text = "Hum: " + str(round(current_wx['main']['humidity'],1)) + "%"
    hum_text_area = label.Label(font, text=hum_text, color=color_white)
    hum_text_area.x = 180
    hum_text_area.y = 130
    hum_text_group = displayio.Group()
    hum_text_group.append(hum_text_area)

    # Display Baro
    baro_text = "Baro: " + str(round((current_wx['main']['pressure'] * 0.02961),2))
    baro_text_area = label.Label(font, text=baro_text, color=color_white)
    baro_text_area.x = 180
    baro_text_area.y = 150
    baro_text_group = displayio.Group()
    baro_text_group.append(baro_text_area)

    # Display City Name
    city_text = "Conditions at " + current_wx['name']
    city_text_area = label.Label(font, text=city_text, color=color_white)
    city_text_area.x = 10
    city_text_area.y = 10
    city_text_group = displayio.Group()
    city_text_group.append(city_text_area)

    # Display Current Conditions
    cur_conditions_text = current_wx['weather'][0]['description']
    cur_conditions_text_area = label.Label(font, text=cur_conditions_text, color=color_white)
    cur_conditions_text_area.x = 10
    cur_conditions_text_area.y = 30
    cur_conditions_text_group = displayio.Group()
    cur_conditions_text_group.append(cur_conditions_text_area)

    # Set Background Colors
    background1 = Rect(0, 0, 340, 45, fill=color_purple)
    background2 = Rect(0, 45, 340, 300, fill=color_darkblue)

    # Weather Conditions Icon
    icon_path = "/icons/" + current_wx['weather'][0]['icon'] + ".bmp"
    icon_bitmap = displayio.OnDiskBitmap(open(icon_path, "rb"))
    icon_tilegrid = displayio.TileGrid(icon_bitmap, pixel_shader=displayio.ColorConverter())
    icon_tilegrid.x = 20
    icon_tilegrid.y = 45

    # Package up all the groups to pass to the display.
    group = displayio.Group(max_size=11)
    group.append(background1)
    group.append(background2)
    group.append(icon_tilegrid)
    group.append(wind_text_group)
    group.append(time_text_group)
    group.append(hum_text_group)
    group.append(baro_text_group)
    group.append(date_text_group)
    group.append(temp_out_text_group)
    group.append(city_text_group)
    group.append(cur_conditions_text_group)

    # Output to Screen
    display.show(group)

    # Our Screen Refresh Rate
    time.sleep(0.5)
