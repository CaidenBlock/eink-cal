#!/usr/bin/python
# -*- coding:utf-8 -*-
import sys
import os
import requests
from zoneinfo import ZoneInfo
from ics import Calendar
import datetime
picdir = './pic'
fontdir = './font'
import logging
from waveshare_epd import epd7in5bc
import time
from PIL import Image,ImageDraw,ImageFont
import traceback
import json

with open("secrets.json") as f:
    secrets = json.load(f)

logging.basicConfig(level=logging.DEBUG)

try:
    logging.info("epd7in5bc Demo")
    
    epd = epd7in5bc.EPD()

    logging.info("init and Clear")
    epd.init()
    epd.Clear()

    # Drawing on the image
    logging.info("Drawing")    
    font24 = ImageFont.truetype(os.path.join(fontdir, 'Font.ttc'), 24)
    font18 = ImageFont.truetype(os.path.join(fontdir, 'Font.ttc'), 18)
    font32 = ImageFont.truetype(os.path.join(fontdir, 'Font.ttc'), 32)
    font72 = ImageFont.truetype(os.path.join(fontdir, 'Font.ttc'), 72)


    # Drawing on the Horizontal image
    logging.info("1.Drawing on the Horizontal image...") 
    HBlackimage = Image.new('1', (epd.width, epd.height), 255)
    HRimage = Image.new('1', (epd.width, epd.height), 255)
    drawblack = ImageDraw.Draw(HBlackimage)
    drawred = ImageDraw.Draw(HRimage)

    date_str = datetime.datetime.now().strftime('%Y-%m-%d')

    drawred.text((10, 10), date_str, font = font32, fill = 0)
    drawblack.line((0, 60, epd.width, 60), fill = 0, width=3)
 
    ics_url = secrets["calendar1"]
    response = requests.get(ics_url)
    calendar = Calendar(response.text)
    x = 5  # Number of upcoming events you want
    upcoming_events = []

    now = datetime.datetime.now(ZoneInfo("America/Chicago"))
    today = now.date()
    for event in sorted(calendar.events, key=lambda e: e.begin):
        event_date = event.begin.datetime.astimezone(ZoneInfo("America/Chicago")).date()
        if event.begin.datetime > now or event_date == today:
            upcoming_events.append(event)
            print(f" - {event.name} at {event.begin.datetime}")
        if len(upcoming_events) >= x:
            break

    if upcoming_events:
        for i, event in enumerate(upcoming_events[:5]):
            y = 75 + i * 30
            # Format start date and time as YYYY-MM-DD @ HH:MM
            start_dt = event.begin.datetime.astimezone(ZoneInfo("America/Chicago"))
            start_str = start_dt.strftime('%Y-%m-%d @ %H:%M')
            name = event.name
            if len(name) > 24:
                name = name[:24] + "..."
            drawblack.text((10, y), f"{start_str} - {name}", font=font24, fill=0)

    epd.display(epd.getbuffer(HBlackimage), epd.getbuffer(HRimage))
    time.sleep(2)
    logging.info("Goto Sleep...")
    epd.sleep()
        
    time.sleep(30)

    logging.info("Wake up...")
    epd.init()
    drawblack.line((0, 300, epd.width, 300), fill = 0, width=3)
    epd.display(epd.getbuffer(HBlackimage), epd.getbuffer(HRimage))
    epd.sleep()


except IOError as e:
    logging.info(e)
    
except KeyboardInterrupt:    
    logging.info("ctrl + c:")
    epd7in5bc.epdconfig.module_exit(cleanup=True)
    exit()
