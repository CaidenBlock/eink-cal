#!/usr/bin/python
# -*- coding:utf-8 -*-
import os
import logging
from datetime import datetime, timedelta, date  # Add date here
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont
from epd_compat import epd7in5bc

class DisplayManager:
    def __init__(self, font_dir='./font'):
        self.font_dir = font_dir
        self.epd = None
        self.drawblack = None
        self.drawred = None
        self.width = 0
        self.height = 0
        
        # Load fonts
        self.font18fs = ImageFont.truetype(os.path.join(font_dir, 'FSEX302.ttf'), 18)
        self.font20fs = ImageFont.truetype(os.path.join(font_dir, 'FSEX302.ttf'), 20)
        self.font24fs = ImageFont.truetype(os.path.join(font_dir, 'FSEX302.ttf'), 24)
        self.font32fs = ImageFont.truetype(os.path.join(font_dir, 'FSEX302.ttf'), 32)
        self.font48fs = ImageFont.truetype(os.path.join(font_dir, 'FSEX302.ttf'), 48)
        
    def initialize(self):
        """Initialize the e-paper display"""
        try:
            self.epd = epd7in5bc.EPD()
            self.epd.init()
            self.epd.Clear()
            self.width = self.epd.width
            self.height = self.epd.height
            
            # Create images and drawing objects
            self.HBlackimage = Image.new('1', (self.width, self.height), 255)
            self.HRimage = Image.new('1', (self.width, self.height), 255)
            self.drawblack = ImageDraw.Draw(self.HBlackimage)
            self.drawred = ImageDraw.Draw(self.HRimage)
            
            return True
        except Exception as e:
            logging.error(f"Error initializing display: {e}")
            return False
            
    def draw_layout(self):
        """Draw the basic layout elements"""
        # Draw the horizontal divider
        self.drawblack.line((0, 60, self.width-200, 60), fill=0, width=3)
        # Draw the vertical divider for the timeline
        self.drawblack.line((self.width - 200, 0, self.width - 200, self.height), fill=0, width=3)
        
    def draw_datetime(self):
        """Draw the current date and time"""
        now_dt = datetime.now()
        date_str = now_dt.strftime('%Y-%m-%d')
        time_str = now_dt.strftime('%H:%M:%S')
        
        # Draw date
        self.drawred.text((10, 0), date_str, font=self.font48fs, fill=0)
        
        # Draw time to the right of the date
        # Estimate width of date text for positioning
        left, top, right, bottom = self.font48fs.getbbox(date_str)
        date_width = right - left
        # Use a smaller font for the time
        self.drawred.text((10 + date_width + 10, 10), time_str, font=self.font18fs, fill=0)
        
    def draw_upcoming_events(self, calendar, event_amt=7):
        """Draw upcoming events from calendar1"""
        if not calendar:
            logging.error("No calendar provided for upcoming events")
            return
            
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
                self.drawblack.text((10, y), f"{start_str} - {name}", font=self.font20fs, fill=0)
                
    def draw_day_blocks(self, calendar):
        """Draw timeline blocks for the day"""
        if not calendar:
            logging.error("No calendar provided for day blocks")
            return
            
        # Time window: 5AM today to 3AM tomorrow (22 hours)
        tz = ZoneInfo("America/Chicago")
        now = datetime.now(tz)
        start_time = now.replace(hour=5, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(hours=22)
        
        logging.info(f"Time window: {start_time} to {end_time}")
        
        # Filter events within the date range
        filtered_events = []
        for event in calendar.timeline:
            # Handle both date and datetime values for event start/end
            event_start = event.dtstart
            event_end = event.dtend
            
            # Convert date to datetime if needed
            if isinstance(event_start, date) and not isinstance(event_start, datetime):
                event_start = datetime.combine(event_start, datetime.min.time(), tzinfo=tz)
                
            if isinstance(event_end, date) and not isinstance(event_end, datetime):
                event_end = datetime.combine(event_end, datetime.max.time(), tzinfo=tz)
            
            # Now compare using compatible types
            if event_end > start_time and event_start < end_time:
                # Store the converted datetime objects with the event for later use
                event._converted_start = event_start
                event._converted_end = event_end
                filtered_events.append(event)
        
        logging.info(f"Found {len(filtered_events)} events in the range")

        # Block area: rightmost 200 pixels
        block_left = self.width - 200  # 440
        block_right = self.width - 1   # 639
        top = 0
        bottom = self.height           # 384
        
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
            # Use the converted datetime objects
            event_start = max(event._converted_start, start_time)
            event_end = min(event._converted_end, end_time)
            
            # Calculate vertical positions
            start_offset_min = (event_start - start_time).total_seconds() / 60
            end_offset_min = (event_end - start_time).total_seconds() / 60
            y_start = int(top + start_offset_min * pixels_per_minute)
            y_end = int(top + end_offset_min * pixels_per_minute)

            # Calculate event duration in minutes
            event_duration_minutes = (event_end - event_start).total_seconds() / 60
            
            # Draw event block in RED
            self.drawred.rectangle([block_left + 2, y_start, block_right, y_end], outline=0, fill=0)
            
            # Draw event summary text
            summary = event.summary if len(event.summary) <= 15 else event.summary[:12] + "..."
            
            # For short events (less than 60 minutes), top-align the text
            text_y = y_start + 2  # Always top-align for short events
            
            # If event is longer than an hour, center it vertically
            if event_duration_minutes >= 60:
                # Calculate text height using getbbox
                _, _, _, text_height = self.font18fs.getbbox(summary)
                
                # Only center if there's enough space for the text to fit
                block_height = y_end - y_start
                if block_height > text_height * 1.2:  # Ensure at least 20% extra space
                    text_y = y_start + (block_height - text_height) // 2
                    
            self.drawred.text((block_left + 5, text_y), summary, font=self.font18fs, fill=255)

        # Draw hour markers and labels in BLACK AND RED LAST
        for hour, y_marker in hour_positions:
            # Draw solid line in BLACK (on black layer)
            self.drawblack.line([block_left, y_marker, block_right, y_marker], fill=0, width=1)

            # Also draw the same line in WHITE (on red layer)
            self.drawred.line([block_left, y_marker, block_right, y_marker], fill=255, width=1)

            # Use 24-hour format without am/pm
            hour_marker_str = f"{hour}"

            # Calculate text position
            left, top, right, bottom = self.font18fs.getbbox(hour_marker_str)
            text_width = right - left
            text_x = block_right - text_width - 5
            text_y = y_marker

            # Draw hour text at right edge in BLACK (on black layer)
            self.drawblack.text((text_x, text_y), hour_marker_str, font=self.font18fs, fill=0)

            # Also draw the same text in WHITE (on red layer)
            self.drawred.text((text_x, text_y), hour_marker_str, font=self.font18fs, fill=255)
            
    def update_display(self):
        """Update the physical display with the current image buffers"""
        try:
            self.epd.display(self.epd.getbuffer(self.HBlackimage), self.epd.getbuffer(self.HRimage))
            return True
        except Exception as e:
            logging.error(f"Error updating display: {e}")
            return False
            
    def sleep(self):
        """Put the display to sleep"""
        try:
            self.epd.sleep()
            return True
        except Exception as e:
            logging.error(f"Error putting display to sleep: {e}")
            return False