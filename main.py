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

def updateCal(calendar_keys):
    all_events = []
    for key in calendar_keys:
        ics_url = secrets[key]
        # Support webcal:// URLs
        if ics_url.startswith("webcal://"):
            ics_url = ics_url.replace("webcal://", "https://", 1)
        response = requests.get(ics_url)
        # Try parsing multiple calendars
        try:
            calendars = Calendar.parse_multiple(response.text)
            for cal in calendars:
                all_events.extend(cal.events)
        except NotImplementedError:
            # Fallback to single calendar
            calendar = Calendar(response.text)
            all_events.extend(calendar.events)
    return all_events

def process_upcoming_events(events, event_amt=5):
    now = datetime.datetime.now(ZoneInfo("America/Chicago"))
    today = now.date()
    upcoming_events = []
    for event in sorted(events, key=lambda e: e.begin):
        event_date = event.begin.datetime.astimezone(ZoneInfo("America/Chicago")).date()
        if event.begin.datetime > now or event_date == today:
            upcoming_events.append(event)
        if len(upcoming_events) >= event_amt:
            break

    if upcoming_events:
        for i, event in enumerate(upcoming_events[:event_amt]):
            y = 75 + i * 30
            start_dt = event.begin.datetime.astimezone(ZoneInfo("America/Chicago"))
            start_str = start_dt.strftime('%Y-%m-%d @ %H:%M')
            name = event.name
            if len(name) > 21:
                name = name[:21] + "..."
            drawblack.text((10, y), f"{start_str} - {name}", font=font18, fill=0)

def draw_day_blocks(events, image, font, epd_width, epd_height):
    # Time window: 5AM today to 3AM tomorrow (22 hours)
    tz = ZoneInfo("America/Chicago")
    now = datetime.datetime.now(tz)
    start_time = now.replace(hour=5, minute=0, second=0, microsecond=0)
    if now.hour < 5:
        start_time -= datetime.timedelta(days=1)
    end_time = start_time + datetime.timedelta(hours=22)

    # Block area: rightmost 200 pixels
    block_left = epd_width - 200  # 440
    block_right = epd_width - 1   # 639
    top = 0
    bottom = epd_height           # 384

    time_window_minutes = (end_time - start_time).total_seconds() / 60
    vertical_pixels = bottom - top
    pixels_per_minute = vertical_pixels / time_window_minutes

    for event in events:
        print(event.name)
        event_start = event.begin.datetime
        event_end = event.end.datetime

        # Ensure timezone-aware (assume UTC if naive)
        if event_start.tzinfo is None:
            event_start = event_start.replace(tzinfo=datetime.timezone.utc)
        if event_end.tzinfo is None:
            event_end = event_end.replace(tzinfo=datetime.timezone.utc)

        # Convert to Central Time
        event_start = event_start.astimezone(tz)
        event_end = event_end.astimezone(tz)

        # Only draw events within the window
        if event_end < start_time or event_start > end_time:
            continue

        # Clamp event start/end to window
        block_start = max(event_start, start_time)
        block_end = min(event_end, end_time)

        # Calculate vertical positions
        start_offset = (block_start - start_time).total_seconds() / 60
        end_offset = (block_end - start_time).total_seconds() / 60
        y1 = int(top + start_offset * pixels_per_minute)
        y2 = int(top + end_offset * pixels_per_minute)

        # Draw rectangle for the event
        drawblack.rectangle([block_left, y1, block_right, y2], outline=0, fill=0)

        # Draw event name (trimmed)
        name = event.name
        if len(name) > 18:
            name = name[:18] + "..."
        drawblack.text((block_left + 5, y1 + 2), name, font=font, fill=255)

        # Draw start time at bottom of block
        time_str = block_start.strftime('%H:%M')
        drawblack.text((block_left + 5, y2 - 18), time_str, font=font, fill=255)



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
    font24 = ImageFont.truetype(os.path.join(fontdir, 'FSEX302.ttf'), 24)
    font18 = ImageFont.truetype(os.path.join(fontdir, 'Font.ttc'), 18)
    font32 = ImageFont.truetype(os.path.join(fontdir, 'Font.ttc'), 32)


    # Drawing on the Horizontal image
    logging.info("1.Drawing on the Horizontal image...") 
    HBlackimage = Image.new('1', (epd.width, epd.height), 255)
    HRimage = Image.new('1', (epd.width, epd.height), 255)
    drawblack = ImageDraw.Draw(HBlackimage)
    drawred = ImageDraw.Draw(HRimage)
    drawblack.line((0, 60, epd.width, 60), fill = 0, width=3)

    date_str = datetime.datetime.now().strftime('%Y-%m-%d')
    drawred.text((10, 10), date_str, font = font32, fill = 0)

    calendar1_events = updateCal(["calendar1"])
    calendar2_3_merged_events = updateCal(["calendar2", "calendar3"])

    # Add dummy event
    from ics import Event
    tz = ZoneInfo("America/Chicago")
    now = datetime.datetime.now(tz)
    dummy_start = now.replace(hour=9, minute=0, second=0, microsecond=0)
    dummy_end = now.replace(hour=11, minute=0, second=0, microsecond=0)
    dummy_event = Event()
    dummy_event.name = "Dummy Event"
    dummy_event.begin = dummy_start
    dummy_event.end = dummy_end
    calendar2_3_merged_events.append(dummy_event)

    # Draw calendar 1 events (up to 5)
    process_upcoming_events(calendar1_events, event_amt=5)

    # Draw merged calendar 2 and 3 events (up to 5, adjust y offset if needed)
    draw_day_blocks(calendar2_3_merged_events, drawblack, font18, epd.width, epd.height)

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
