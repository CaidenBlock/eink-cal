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
    font72 = ImageFont.truetype(os.path.join(fontdir, 'Font.ttc'), 72)


    # Drawing on the Horizontal image
    logging.info("1.Drawing on the Horizontal image...") 
    HBlackimage = Image.new('1', (epd.width, epd.height), 255)
    HRimage = Image.new('1', (epd.width, epd.height), 255)  # 298*126  ryimage: red or yellow image  
    drawblack = ImageDraw.Draw(HBlackimage)
    drawred = ImageDraw.Draw(HRimage)
    date_str = datetime.datetime.now().strftime('%Y-%m-%d')
    drawblack.text((10, 10), date_str, font = font24, fill = 0)
    drawblack.line((0, 50, epd.width, 50), fill = 0, width=3)
    # drawblack.text((10, 20), '7.5inch e-Paper bc', font = font24, fill = 0)
    # drawblack.text((150, 0), u'微雪电子', font = font24, fill = 0)    
    # drawblack.line((70, 50, 20, 100), fill = 0)
    # drawblack.rectangle((20, 50, 70, 100), outline = 0)    
    # drawry.line((165, 50, 165, 100), fill = 0)
    # drawry.line((140, 75, 190, 75), fill = 0)
    # drawry.arc((140, 50, 190, 100), 0, 360, fill = 0)
    # drawry.rectangle((80, 50, 130, 100), fill = 0)
    # drawry.chord((200, 50, 250, 100), 0, 360, fill = 0)
    ics_url = secrets["calendar1"]
    response = requests.get(ics_url)
    calendar = Calendar(response.text)
    x = 5  # Number of upcoming events you want
    now = datetime.datetime.now(ZoneInfo("America/Chicago"))
    upcoming_events = []

    for event in sorted(calendar.events, key=lambda e: e.begin):
        if event.begin.datetime > now:
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
            drawblack.text((10, y), f"{start_str} - {event.name}", font=font24, fill=0)

    epd.display(epd.getbuffer(HBlackimage), epd.getbuffer(HRimage))
    time.sleep(2)
    logging.info("Goto Sleep...")
    epd.sleep()
        
except IOError as e:
    logging.info(e)
    
except KeyboardInterrupt:    
    logging.info("ctrl + c:")
    epd7in5bc.epdconfig.module_exit(cleanup=True)
    exit()
