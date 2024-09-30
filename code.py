import sys
import time
import board # type: ignore
import busio # type: ignore
import neopixel # type: ignore
import gc # type: ignore
import rtc # type: ignore # For interfacing with the Real Time Clock
import displayio # type: ignore # Library for writing text / graphics to the screen
from adafruit_display_shapes.rect import Rect # type: ignore # Library to draw rectangles
from digitalio import DigitalInOut # type: ignore # Enabling DigitalIO so we can talk to the ESP32 Wifi chip.
from adafruit_bitmap_font import bitmap_font # type: ignore
from adafruit_display_text import label # type: ignore
from adafruit_esp32spi import adafruit_esp32spi, adafruit_esp32spi_wifimanager # type: ignore

# Get wifi and api secrets
try:
    from secrets import secrets # type: ignore
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

# Initialize the Real Time Clock
internal_rtc = rtc.RTC()

# Initialize the Display
display = board.DISPLAY

# Set some Global variables
#font = bitmap_font.load_font("/fonts/Arial-ItalicMT-17.bdf")
font = bitmap_font.load_font("/fonts/Helvetica-Bold-16.bdf")
color_blue = 0x0000FF
color_white = 0xFFFFFF
color_darkpurple = 0x2e0142
color_purple = 0x8323ad
color_darkblue = 0x00004a

print("Initializing")
wifi.connect()

def sync_rtc(time_api):
    # Get the time from the time api server. 
    poll_URL = time_api

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

    # Sometimes the openweathermap API does not return a wind direction at all.  Assume a North wind if this happens. 
    if "deg" not in weather_json['wind']:
        weather_json['wind']['deg'] = 0

    return weather_json

def get_forecast_wx(lat, lon, api_key):
    # Get the weather forecast from the weather API server
    poll_URL = "https://api.openweathermap.org/data/3.0/onecall?units=imperial&exclude=minutely,hourly,alerts,current&lat=" + lat + "&lon=" + lon  + "&appid=" + api_key 

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

def degree_to_cardinal(wind_degrees):
    # Wind Degrees to Cardinal solution from https://stackoverflow.com/questions/7490660/converting-wind-direction-in-angles-to-text-words
    val=int((wind_degrees/22.5)+.5)
    compass=["N","NNE","NE","ENE","E","ESE", "SE", "SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return compass[(val % 16)]

def get_forecast_for_day(forecast_data, day_num):
    forecast_for_day = {}
    if day_num == 7:
        day_num = 0
    elif day_num == 8:
        day_num = 1
    elif day_num == 9:
        day_num = 2
    
    for item in forecast_data['daily']:
        forecast_time = time.localtime(item['dt'])

        if forecast_time[6] == day_num:

            forecast_for_day.update({'forecast_high' : round(item['temp']['max'])})
            forecast_for_day.update({'forecast_low' : round(item['temp']['min'])})
            forecast_for_day.update({'forecast_icon' : item['weather'][0]['icon']})
    return forecast_for_day

print("Mem Free: " + str(gc.mem_free()))
sync_rtc(secrets['time_api'])
current_wx = get_current_wx(secrets['owm_cityid'], secrets['owm_apikey'])
forecast_wx = get_forecast_wx(str(current_wx['coord']['lat']), str(current_wx['coord']['lon']), secrets['owm_apikey'])

now = time.localtime()
day1_forecast = get_forecast_for_day(forecast_wx, now[6] + 1)
day2_forecast = get_forecast_for_day(forecast_wx, now[6] + 2)
day3_forecast = get_forecast_for_day(forecast_wx, now[6] + 3)
forecast_wx = None

print("Mem Free: " + str(gc.mem_free()))

time.sleep(10)

while True:
    # Load the current time from the RTC
    now = time.localtime()

    # Resync the clock at 11 min past the hour.  
    if ((now[4] == 11) and (now[5] == 0)):
        sync_rtc(secrets['time_api'])

    # Resync the forecast at 15 min past the hour.  
    if ((now[4] == 15) and (now[5] == 30)):
        forecast_wx = get_forecast_wx(str(current_wx['coord']['lat']), str(current_wx['coord']['lon']), secrets['owm_apikey'])
        day1_forecast = get_forecast_for_day(forecast_wx, now[6] + 1)
        day2_forecast = get_forecast_for_day(forecast_wx, now[6] + 2)
        day3_forecast = get_forecast_for_day(forecast_wx, now[6] + 3)
        forecast_wx = None

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

    # Display Time and Date
    timenow = time_hour + ":" + str("{:02d}".format(now[4])) + ":" + str("{:02d}".format(now[5])) + " " + time_tag
    day_name = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat','Sun']
    month_name = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    day_name = day_name[now[6]]
    month_name = month_name[now[1] - 1]
    datenow = day_name + " " + month_name + " " + str(now[2])
    time_text = timenow + "\n" + datenow
    time_text_area = label.Label(font, text=time_text, color=color_white, line_spacing=0.9)
    time_text_area.x = 220
    time_text_area.y = 15
    time_text_group = displayio.Group()
    time_text_group.append(time_text_area)

    # Display Current Conditions
    temp_out = "Temp: " + str(round(current_wx['main']['temp'])) + "°"
    wind_dir = "Wind: " + str(round(current_wx['wind']['speed'])) + " " + degree_to_cardinal(current_wx['wind']['deg'])
    hum_out = "Hum: " + str(round(current_wx['main']['humidity'],1)) + "%"
    baro_out = "Baro: " + str(round((current_wx['main']['pressure'] * 0.02961),2))

    cur_conditions_text = temp_out + "\n" + wind_dir +"\n" + hum_out + "\n" + baro_out
    cur_conditions_text_area = label.Label(font, text=cur_conditions_text, color=color_white, line_spacing=0.9)
    cur_conditions_text_area.x = 190
    cur_conditions_text_area.y = 85
    cur_conditions_text_group = displayio.Group()
    cur_conditions_text_group.append(cur_conditions_text_area)

    # Display City Name and Current Conditions
    city_text = "Conditions at " + current_wx['name'] + "\n" + current_wx['weather'][0]['description']
    city_text_area = label.Label(font, text=city_text, color=color_white, line_spacing=0.9)
    city_text_area.x = 10
    city_text_area.y = 15
    city_text_group = displayio.Group()
    city_text_group.append(city_text_area)

    # Day1 Conditions Icon
    icon_day1_path = "/icons/small/" + day1_forecast['forecast_icon'] + ".bmp"
    icon_day1_bitmap = displayio.OnDiskBitmap(open(icon_day1_path, "rb"))
    icon_day1_tilegrid = displayio.TileGrid(icon_day1_bitmap, pixel_shader=displayio.ColorConverter())
    icon_day1_tilegrid.x = 5
    icon_day1_tilegrid.y = 175

    # Display Day 1 Forecast
    day_name_forecast = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun', 'Mon', 'Tue', 'Wed']
    day1_forecast_text = day_name_forecast[now[6] + 1] + "\r\nH: " + str(day1_forecast['forecast_high']) + "°\r\nL: " + str(day1_forecast['forecast_low']) + "°"
    day1_forecast_text_area = label.Label(font, text=day1_forecast_text, color=color_white, line_spacing=0.9)
    day1_forecast_text_area.x = 50
    day1_forecast_text_area.y = 190
    day1_forecast_text_group = displayio.Group()
    day1_forecast_text_group.append(day1_forecast_text_area)

    # Day2 Conditions Icon
    icon_day2_path = "/icons/small/" + day2_forecast['forecast_icon'] + ".bmp"
    icon_day2_bitmap = displayio.OnDiskBitmap(open(icon_day2_path, "rb"))
    icon_day2_tilegrid = displayio.TileGrid(icon_day2_bitmap, pixel_shader=displayio.ColorConverter())
    icon_day2_tilegrid.x = 115
    icon_day2_tilegrid.y = 175

    # Display Day 2 Forecast
    day2_forecast_text = day_name_forecast[now[6] + 2] + "\r\nH: " + str(day2_forecast['forecast_high']) + "°\r\nL: " + str(day2_forecast['forecast_low']) + "°"
    day2_forecast_text_area = label.Label(font, text=day2_forecast_text, color=color_white, line_spacing=0.9)
    day2_forecast_text_area.x = 160
    day2_forecast_text_area.y = 190
    day2_forecast_text_group = displayio.Group()
    day2_forecast_text_group.append(day2_forecast_text_area)

    # Day3 Conditions Icon
    icon_day3_path = "/icons/small/" + day3_forecast['forecast_icon'] + ".bmp"
    icon_day3_bitmap = displayio.OnDiskBitmap(open(icon_day3_path, "rb"))
    icon_day3_tilegrid = displayio.TileGrid(icon_day3_bitmap, pixel_shader=displayio.ColorConverter())
    icon_day3_tilegrid.x = 215
    icon_day3_tilegrid.y = 175

    # Display Day 3 Forecast
    day3_forecast_text = day_name_forecast[now[6] + 3] + "\r\nH: " + str(day3_forecast['forecast_high']) + "°\r\nL: " + str(day3_forecast['forecast_low']) + "°"
    day3_forecast_text_area = label.Label(font, text=day3_forecast_text, color=color_white, line_spacing=0.9)
    day3_forecast_text_area.x = 260
    day3_forecast_text_area.y = 190
    day3_forecast_text_group = displayio.Group()
    day3_forecast_text_group.append(day3_forecast_text_area)

    # Display Free Mem for Debugging 
    mem_text = "Mem: " + str(gc.mem_free())
    mem_text_area = label.Label(font, text=mem_text, color=color_white, line_spacing=0.9)
    mem_text_area.x = 200
    mem_text_area.y = 230
    mem_text_group = displayio.Group()
    mem_text_group.append(mem_text_area)

    # Set Background Colors
    background1 = Rect(0, 0, 340, 45, fill=color_purple)
    background2 = Rect(0, 45, 340, 300, fill=color_darkblue)

    # Weather Conditions Icon
    icon_path = "/icons/" + current_wx['weather'][0]['icon'] + ".bmp"
    icon_bitmap = displayio.OnDiskBitmap(open(icon_path, "rb"))
    icon_tilegrid = displayio.TileGrid(icon_bitmap, pixel_shader=displayio.ColorConverter())
    icon_tilegrid.x = 20
    icon_tilegrid.y = 35

    # Package up all the groups to pass to the display.
    group = displayio.Group()
    group.append(background2)
    group.append(icon_tilegrid)
    group.append(icon_day1_tilegrid)
    group.append(icon_day2_tilegrid)
    group.append(icon_day3_tilegrid)
    group.append(background1)
    #group.append(mem_text_group)
    group.append(time_text_group)
    group.append(cur_conditions_text_group)
    group.append(city_text_group)
    group.append(day1_forecast_text_group)
    group.append(day2_forecast_text_group)
    group.append(day3_forecast_text_group)

    # Output to Screen
    display.show(group)

    #Run Garbage Collection
    gc.collect()

    # Our Screen Refresh Rate
    time.sleep(1)
