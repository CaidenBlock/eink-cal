#!/usr/bin/python
# -*- coding:utf-8 -*-
import sys
import os
import requests
from zoneinfo import ZoneInfo
from ical.calendar_stream import IcsCalendarStream
from ical.exceptions import CalendarParseError
from datetime import datetime, timedelta
import pickle
from pathlib import Path
import time as systime

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

def updateCal(calendar_keys):
    all_calendars = []
    for key in calendar_keys:
        ics_url = secrets[key]
        # Support webcal:// URLs
        if ics_url.startswith("webcal://"):
            ics_url = ics_url.replace("webcal://", "https://", 1)
        response = requests.get(ics_url)
        if response.status_code == 200:
            try:
                calendar = IcsCalendarStream.calendar_from_ics(response.text)
                all_calendars.append(calendar)
            except CalendarParseError as err:
                logging.error(f"Failed to parse calendar for {key}: {err}")
    
    if len(all_calendars) == 1:
        return all_calendars[0]
    elif len(all_calendars) > 1:
        # Merge calendars - not a built-in function in ical, so we'll return the list
        # and handle merging elsewhere
        return all_calendars
    else:
        # No calendars parsed successfully
        logging.error("No calendars were successfully parsed")
        return None

def process_upcoming_events(calendar, event_amt=5):
    now = datetime.now(ZoneInfo("America/Chicago"))
    today = now.date()
    
    # Get all events from the calendar and sort by start time
    events = sorted(calendar.timeline, key=lambda e: e.dtstart)
    
    upcoming_events = []
    for event in events:
        event_date = event.dtstart.astimezone(ZoneInfo("America/Chicago")).date()
        if event.dtstart > now or event_date == today:
            upcoming_events.append(event)
        if len(upcoming_events) >= event_amt:
            break

    if upcoming_events:
        for i, event in enumerate(upcoming_events[:event_amt]):
            y = 75 + i * 30
            start_dt = event.dtstart.astimezone(ZoneInfo("America/Chicago"))
            start_str = start_dt.strftime('%m-%d@%H:%M')
            name = event.summary
            if len(name) > 18:
                name = name[:18] + "..."
            drawblack.text((10, y), f"{start_str} {name}", font=font24, fill=0)

def get_cached_calendar(ics_url, cache_time_minutes=60):
    cache_dir = Path('./cache')
    cache_dir.mkdir(exist_ok=True)
    
    # Create a filename based on the URL
    import hashlib
    url_hash = hashlib.md5(ics_url.encode()).hexdigest()
    cache_file = cache_dir / f"{url_hash}.pickle"
    
    # Check if cache exists and is recent enough
    if cache_file.exists():
        file_age_minutes = (systime.time() - cache_file.stat().st_mtime) / 60
        if file_age_minutes < cache_time_minutes:
            try:
                with open(cache_file, 'rb') as f:
                    logging.info(f"Using cached calendar data ({file_age_minutes:.1f} min old)")
                    return pickle.load(f)
            except Exception as e:
                logging.error(f"Error loading cache: {e}")
    
    # Fetch and parse the calendar
    logging.info("Fetching fresh calendar data")
    response = requests.get(ics_url)
    if response.status_code != 200:
        logging.error(f"Failed to fetch ICS file: HTTP {response.status_code}")
        return None
        
    try:
        calendar = IcsCalendarStream.calendar_from_ics(response.text)
        
        # Save to cache
        with open(cache_file, 'wb') as f:
            pickle.dump(calendar, f)
            
        return calendar
    except CalendarParseError as err:
        logging.error(f"Failed to parse ics file from {ics_url}: {err}")
        return None

# Update draw_day_blocks to accept a calendar object instead of a URL
def draw_day_blocks(calendar, image, font, epd_width, epd_height):
    # Time window: 5AM today to 3AM tomorrow (22 hours)
    tz = ZoneInfo("America/Chicago")
    now = datetime.now(tz)
    start_time = now.replace(hour=5, minute=0, second=0, microsecond=0)
    if now.hour < 5:
        start_time -= timedelta(days=1)
    end_time = start_time + timedelta(hours=22)
    
    logging.info(f"Time window: {start_time} to {end_time}")
    
    # Filter events within the date range
    filtered_events = [
        event for event in calendar.timeline
        if (event.dtend > start_time and event.dtstart < end_time)
    ]
    
    logging.info(f"Found {len(filtered_events)} events in the range")

    # Block area: rightmost 200 pixels
    block_left = epd_width - 200  # 440
    block_right = epd_width - 1   # 639
    top = 0
    bottom = epd_height           # 384
    
    logging.info(f"Drawing area: left={block_left}, right={block_right}, top={top}, bottom={bottom}")

    time_window_minutes = (end_time - start_time).total_seconds() / 60
    vertical_pixels = bottom - top
    pixels_per_minute = vertical_pixels / time_window_minutes
    
    logging.info(f"Time window: {time_window_minutes} minutes, {vertical_pixels} pixels")
    logging.info(f"Scale: {pixels_per_minute} pixels per minute")
    
    # Draw a border around the timeline area (for debugging)
    # image.rectangle([block_left, top, block_right, bottom], outline=0, fill=None)
    
    # Draw hour markers with explicit coordinates
    hours_to_draw = []
    current_hour = start_time.hour
    while True:
        hours_to_draw.append(current_hour)
        current_hour = (current_hour + 1) % 24
        if current_hour == (end_time.hour + 1) % 24:
            break

    logging.info(f"Hours to draw: {hours_to_draw}")

    for hour in hours_to_draw:
        marker_time = start_time.replace(hour=hour, minute=0)
        if marker_time < start_time:
            marker_time = marker_time + timedelta(days=1)  # Move to next day
        if marker_time > end_time:
            continue
            
        minutes_from_start = (marker_time - start_time).total_seconds() / 60
        y_marker = int(top + minutes_from_start * pixels_per_minute)
        
        logging.info(f"Hour {hour}: y={y_marker}, minutes_from_start={minutes_from_start}")
        
        # Draw solid line
        image.line([block_left, y_marker, block_right, y_marker], fill=0, width=1)
        
        # Format hour text
        hour_str = f"{hour % 12 or 12}"
        am_pm = "a" if hour < 12 else "p"
        time_str = f"{hour_str}{am_pm}"
        
        # Draw hour text
        image.text((block_left + 5, y_marker - 12), time_str, font=font, fill=0)
    
    # Draw timeline blocks for each event
    for event in filtered_events:
        # Clamp event start/end to the time window
        event_start = max(event.dtstart, start_time)
        event_end = min(event.dtend, end_time)
        
        # Calculate vertical positions
        start_offset_min = (event_start - start_time).total_seconds() / 60
        end_offset_min = (event_end - start_time).total_seconds() / 60
        
        y_start = int(top + start_offset_min * pixels_per_minute)
        y_end = int(top + end_offset_min * pixels_per_minute)
        
        logging.info(f"Event: {event.summary}, y_start={y_start}, y_end={y_end}")
        
        # Draw block with border
        image.rectangle([block_left, y_start, block_right, y_end], outline=0, fill=0)
        
        # Draw event summary text with higher contrast
        summary = event.summary if len(event.summary) <= 18 else event.summary[:15] + "..."
        image.text((block_left + 5, y_start + 2), summary, font=font, fill=255)

logging.basicConfig(level=logging.DEBUG)

try:
    logging.info("epd7in5bc Demo")
    
    epd = epd7in5bc.EPD()

    logging.info("init and Clear")
    epd.init()
    epd.Clear()

    # Drawing on the image
    logging.info("Drawing")    
    font24fs = ImageFont.truetype(os.path.join(fontdir, 'FSEX302.ttf'), 24)
    font24 = ImageFont.truetype(os.path.join(fontdir, 'Font.ttc'), 24)
    font18fs = ImageFont.truetype(os.path.join(fontdir, 'FSEX302.ttf'), 18)
    font18 = ImageFont.truetype(os.path.join(fontdir, 'Font.ttc'), 18)
    font32fs = ImageFont.truetype(os.path.join(fontdir, 'FSEX302.ttf'), 32)
    font48fs = ImageFont.truetype(os.path.join(fontdir, 'FSEX302.ttf'), 48)


    # Drawing on the Horizontal image
    logging.info("1.Drawing on the Horizontal image...") 
    HBlackimage = Image.new('1', (epd.width, epd.height), 255)
    HRimage = Image.new('1', (epd.width, epd.height), 255)
    drawblack = ImageDraw.Draw(HBlackimage)
    drawred = ImageDraw.Draw(HRimage)
    drawblack.line((0, 60, epd.width-200, 60), fill = 0, width=3)
    drawblack.line((epd.width - 200, 0, epd.width - 200, epd.height), fill = 0, width=3)

    date_str = datetime.now().strftime('%Y-%m-%d')
    drawred.text((10, 0), date_str, font = font48fs, fill = 0)

    # Get calendar1 (always fresh)
    calendar1_events = updateCal(["calendar1"])
    process_upcoming_events(calendar1_events, event_amt=5)

    # Get calendar2 (cached)
    ics_url = secrets["calendar2"]
    calendar2 = get_cached_calendar(ics_url)
    if calendar2:
        draw_day_blocks(calendar2, drawblack, font18fs, epd.width, epd.height)
    else:
        logging.error("Failed to get calendar2, skipping day blocks")

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
