#!/usr/bin/python
# -*- coding:utf-8 -*-
import sys
import os
import requests
from zoneinfo import ZoneInfo
from ics import Calendar
from ics.timeline import Timeline
import datetime
picdir = './pic'
fontdir = './font'
import logging
from waveshare_epd import epd7in5bc
import time
from PIL import Image,ImageDraw,ImageFont
import traceback
import json
from dateutil.rrule import rrulestr

def updateCal(calendar_keys):
    calendars = []
    for key in calendar_keys:
        ics_url = secrets[key]
        if ics_url.startswith("webcal://"):
            ics_url = ics_url.replace("webcal://", "https://", 1)
        response = requests.get(ics_url)
        try:
            cal = Calendar(response.text)  # ics library parsing is simple
            calendars.append(cal)
            logging.info(f"Successfully parsed {key} calendar")
        except Exception as e:
            logging.error(f"Error parsing calendar for {key}: {e}")
            continue
    
    # Return the single calendar for single key
    if len(calendars) == 1:
        return calendars[0]
    else:
        # Merge if multiple
        merged = Calendar()
        for cal in calendars:
            for event in cal.events:
                merged.events.add(event)  # In ics library, events is a set
        return merged

def process_upcoming_events(events, event_amt=5):
    now = datetime.datetime.now(ZoneInfo("America/Chicago"))
    today = now.date()
    upcoming_events = []
    for event in sorted(events, key=lambda e: e.dtstart):
        event_date = event.dtstart.astimezone(ZoneInfo("America/Chicago")).date()
        if event.dtstart > now or event_date == today:
            upcoming_events.append(event)
        if len(upcoming_events) >= event_amt:
            break

    if upcoming_events:
        for i, event in enumerate(upcoming_events[:event_amt]):
            y = 75 + i * 30
            start_dt = event.dtstart.astimezone(ZoneInfo("America/Chicago"))
            start_str = start_dt.strftime('%Y-%m-%d @ %H:%M')
            name = event.summary
            if len(name) > 21:
                name = name[:21] + "..."
            drawblack.text((10, y), f"{start_str} - {name}", font=font18, fill=0)

def draw_day_blocks(calendar, image, font, epd_width, epd_height):
    tz = ZoneInfo("America/Chicago")
    now = datetime.datetime.now(tz)
    start_time = now.replace(hour=5, minute=0, second=0, microsecond=0)
    if now.hour < 5:
        start_time -= datetime.timedelta(days=1)
    end_time = start_time + datetime.timedelta(hours=22)

    block_left = epd_width - 200
    block_right = epd_width - 1
    top = 0
    bottom = epd_height

    time_window_minutes = (end_time - start_time).total_seconds() / 60
    vertical_pixels = bottom - top
    pixels_per_minute = vertical_pixels / time_window_minutes

    logging.info(f"Calendar has {len(calendar.events)} events")
    for event in calendar.events:
        logging.info(f"Event: '{event.summary}' - {event.dtstart} to {event.dtend}")
        if hasattr(event, 'rrule') and event.rrule:
            logging.info(f"Recurring event: '{event.summary}' with rules: {event.rrule}")

    count = 0
    # This will work with the ics library
    timeline = Timeline(calendar)
    for occ in timeline:
        if occ.begin > end_time:
            break
        if occ.begin < start_time:
            continue
        
        # Process each occurrence
        event_start = occ.begin.astimezone(tz)
        event_end = occ.end.astimezone(tz)

        count += 1
        logging.info(f"Occurrence {count}: '{occ.name}' - {event_start} to {event_end}")

        block_start = max(event_start, start_time)
        block_end = min(event_end, end_time)
        start_offset = (block_start - start_time).total_seconds() / 60
        end_offset = (block_end - start_time).total_seconds() / 60
        y1 = int(top + start_offset * pixels_per_minute)
        y2 = int(top + end_offset * pixels_per_minute)

        logging.info(f"Drawing '{occ.name}' from y={y1} to y={y2}")

        image.rectangle([block_left, y1, block_right, y2], outline=0, fill=0)
        name = occ.name
        if len(name) > 18:
            name = name[:18] + "..."
        image.text((block_left + 5, y1 + 2), name, font=font, fill=255)
        time_str = block_start.strftime('%H:%M')
        image.text((block_left + 5, y2 - 18), time_str, font=font, fill=255)

        logging.info(f"Occurrence from non-recurring event: '{occ.name}'")

    logging.info(f"Total occurrences processed: {count}")

# Merge multiple Calendar objects into one
def merge_calendars(calendar_list):
    merged = Calendar()
    for cal in calendar_list:
        for event in cal.events:
            merged.events.append(event)  # Changed from add to append for list
            logging.info(f"Added event '{event.summary}' to merged calendar")  # Changed from name to summary
            if hasattr(event, 'rrule') and event.rrule:  # Changed from recurrence_rules to rrule
                logging.info(f"Event '{event.summary}' has recurrence rules: {event.rrule}")  # Changed from name to summary
    return merged

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
    process_upcoming_events(calendar1_events.events, event_amt=5)
    calendar2_real = updateCal(["calendar2"])
    draw_day_blocks(calendar2_real, drawblack, font18, epd.width, epd.height)

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
