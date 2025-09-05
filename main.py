#!/usr/bin/python
# -*- coding:utf-8 -*-
import os
import logging
import time
import json
import hashlib
from zoneinfo import ZoneInfo
from pathlib import Path
from datetime import datetime, timedelta
import pickle
import requests
from ical.calendar_stream import IcsCalendarStream
from ical.exceptions import CalendarParseError
from PIL import Image,ImageDraw,ImageFont
from epd_compat import epd7in5bc

PIC_DIR = './pic'
FONT_DIR = './font'

with open("secrets.json", encoding="utf-8") as f:
    secrets = json.load(f)

def update_cal(calendar_keys):
    all_calendars = []
    for key in calendar_keys:
        ics_url = secrets[key]
        # Support webcal:// URLs
        if ics_url.startswith("webcal://"):
            ics_url = ics_url.replace("webcal://", "https://", 1)
        response = requests.get(ics_url, timeout=10)
        if response.status_code == 200:
            try:
                calendar = IcsCalendarStream.calendar_from_ics(response.text)
                all_calendars.append(calendar)
            except CalendarParseError as err:
                logging.error("Failed to parse calendar for %s: %s", key, err)

    # Combine calendars if more than one.
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

def process_upcoming_events(calendar, event_amt):
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
            start_str = start_dt.strftime('%m-%d @ %H:%M')
            name = event.summary
            if len(name) > 24:
                name = name[:24] + ".."
            drawblack.text((10, y), f"{start_str} - {name}", font=font20fs, fill=0)

def get_cached_calendar(ics_url, cache_time_minutes=60):
    cache_dir = Path('./cache')
    cache_dir.mkdir(exist_ok=True)
    # Create a filename based on the URL
    url_hash = hashlib.md5(ics_url.encode()).hexdigest()
    cache_file = cache_dir / f"{url_hash}.pickle"
    # Check if cache exists and is recent enough
    if cache_file.exists():
        file_age_minutes = (time.time() - cache_file.stat().st_mtime) / 60
        if file_age_minutes < cache_time_minutes:
            try:
                with open(cache_file, 'rb') as f:
                    logging.info("Using cached calendar data (%.1f min old)", file_age_minutes)
                    return pickle.load(f)
            except Exception as e:
                logging.error("Error loading cache: %s", e)

    # Fetch and parse the calendar
    logging.info("Fetching fresh calendar data")
    response = requests.get(ics_url, timeout=10)
    if response.status_code != 200:
        logging.error("Failed to fetch ICS file: HTTP %d", response.status_code)
        return None
    try:
        calendar = IcsCalendarStream.calendar_from_ics(response.text)
        # Save to cache
        with open(cache_file, 'wb') as f:
            pickle.dump(calendar, f)
        return calendar
    except CalendarParseError as err:
        logging.error("Failed to parse ics file from %s: %s", ics_url, err)
        return None

# Update draw_day_blocks to accept a calendar object instead of a URL
def draw_day_blocks(calendar, black_image, red_image, font, epd_width, epd_height):
    # Time window: 5AM today to 3AM tomorrow (22 hours)
    tz = ZoneInfo("America/Chicago")
    now = datetime.now(tz)
    start_time = now.replace(hour=5, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(hours=22)
    logging.info("Time window: %s to %s", start_time, end_time)
    # Filter events within the date range
    filtered_events = [
        event for event in calendar.timeline
        if (event.dtend > start_time and event.dtstart < end_time)
    ]
    logging.info("Found %d events in the range", len(filtered_events))

    # Block area: rightmost 200 pixels
    block_left = epd_width - 200  # 440
    block_right = epd_width - 1   # 639
    top = 0
    bottom = epd_height           # 384
    time_window_minutes = (end_time - start_time).total_seconds() / 60
    vertical_pixels = bottom - top
    pixels_per_minute = vertical_pixels / time_window_minutes

    # First, calculate all hour marker positions
    hour_positions = []
    hours_to_draw = []
    current_hour = start_time.hour
    while True:
        hours_to_draw.append(current_hour)
        current_hour = (current_hour + 1) % 24
        if current_hour == (end_time.hour + 1) % 24:
            break

    for hour in hours_to_draw:
        marker_time = start_time.replace(hour=hour, minute=0)
        if marker_time < start_time:
            marker_time = marker_time + timedelta(days=1)  # Move to next day
        if marker_time > end_time:
            continue

        # Calculate vertical position
        minutes_from_start = (marker_time - start_time).total_seconds() / 60
        y_marker = int(top + minutes_from_start * pixels_per_minute)
        hour_positions.append((hour, y_marker))

    # Draw timeline blocks for each event (in RED) FIRST
    for event in filtered_events:
        # Clamp event start/end to the time window
        event_start = max(event.dtstart, start_time)
        event_end = min(event.dtend, end_time)

        # Calculate vertical positions
        start_offset_min = (event_start - start_time).total_seconds() / 60
        end_offset_min = (event_end - start_time).total_seconds() / 60
        y_start = int(top + start_offset_min * pixels_per_minute)
        y_end = int(top + end_offset_min * pixels_per_minute)

        # Calculate event duration in minutes
        event_duration_minutes = (event_end - event_start).total_seconds() / 60
        # Draw event block in RED
        red_image.rectangle([block_left + 2, y_start, block_right, y_end], outline=0, fill=0)
        # Draw event summary text
        summary = event.summary if len(event.summary) <= 15 else event.summary[:12] + "..."
        # For short events (less than 60 minutes), top-align the text
        text_y = y_start - 2  # Always top-align for short events
        # If event is longer than an hour, you could center it vertically
        if event_duration_minutes >= 60:
            # Calculate text height using getbbox
            _, _, _, text_height = font.getbbox(summary)
            # Only center if there's enough space for the text to fit
            block_height = y_end - y_start
            if block_height > text_height * 1.2:  # Ensure at least 20% extra space
                text_y = y_start + (block_height - text_height) // 2
        red_image.text((block_left + 5, text_y), summary, font=font, fill=255)

    # Draw hour markers and labels in BLACK AND RED LAST
    for hour, y_marker in hour_positions:
        # Draw solid line in BLACK (on black layer)
        black_image.line([block_left, y_marker, block_right, y_marker], fill=0, width=1)

        # Also draw the same line in WHITE (on red layer)
        red_image.line([block_left, y_marker, block_right, y_marker], fill=255, width=1)

        # Use 24-hour format without am/pm
        hour_marker_str = f"{hour}"

        # Calculate text position using getbbox or getlength instead of getsize
        if hasattr(font, 'getbbox'):
            left, top, right, bottom = font.getbbox(hour_marker_str)
            text_width = right - left
        elif hasattr(font, 'getlength'):
            text_width = int(font.getlength(hour_marker_str))
        else:
            text_width = len(hour_marker_str) * 8

        text_x = block_right - text_width - 5
        text_y = y_marker

        # Draw hour text at right edge in BLACK (on black layer)
        black_image.text((text_x, text_y), hour_marker_str, font=font, fill=0)

        # Also draw the same text in WHITE (on red layer)
        red_image.text((text_x, text_y), hour_marker_str, font=font, fill=255)

logging.basicConfig(level=logging.DEBUG)

try:
    logging.info("epd7in5bc Demo")
    epd = epd7in5bc.EPD()
    logging.info("init and Clear")
    epd.init()
    epd.Clear()

    # Drawing on the image
    logging.info("Drawing")
    font24fs = ImageFont.truetype(os.path.join(FONT_DIR, 'FSEX302.ttf'), 24)
    font18fs = ImageFont.truetype(os.path.join(FONT_DIR, 'FSEX302.ttf'), 18)
    font20fs = ImageFont.truetype(os.path.join(FONT_DIR, 'FSEX302.ttf'), 20)
    font32fs = ImageFont.truetype(os.path.join(FONT_DIR, 'FSEX302.ttf'), 32)
    font48fs = ImageFont.truetype(os.path.join(FONT_DIR, 'FSEX302.ttf'), 48)


    # Drawing on the Horizontal image
    logging.info("1.Drawing on the Horizontal image...")
    HBlackimage = Image.new('1', (epd.width, epd.height), 255)
    HRimage = Image.new('1', (epd.width, epd.height), 255)
    drawblack = ImageDraw.Draw(HBlackimage)
    drawred = ImageDraw.Draw(HRimage)
    drawblack.line((0, 60, epd.width-200, 60), fill = 0, width=3)
    drawblack.line((epd.width - 200, 0, epd.width - 200, epd.height), fill = 0, width=3)

    now_dt = datetime.now()
    date_str = now_dt.strftime('%Y-%m-%d')
    time_str = now_dt.strftime('%H:%M:%S')
    # Draw date
    drawred.text((10, 0), date_str, font=font48fs, fill=0)
    # Draw time to the right of the date
    # Estimate width of date text for positioning
    left, top, right, bottom = font48fs.getbbox(date_str)
    date_width = right - left
    # Use a smaller font for the time
    drawred.text((10 + date_width + 10, 10), time_str, font=font18fs, fill=0)

    # Get calendar1 (always fresh)
    calendar1_events = update_cal(["calendar1"])
    process_upcoming_events(calendar1_events, event_amt=7)

    # Get calendar2 (cached)
    ics_url = secrets["calendar2"]
    calendar2 = get_cached_calendar(ics_url)
    if calendar2:
        draw_day_blocks(calendar2, drawblack, drawred, font18fs, epd.width, epd.height)
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
