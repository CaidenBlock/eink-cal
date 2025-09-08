#!/usr/bin/python
# -*- coding:utf-8 -*-
import logging
import json
import hashlib
import pickle
import time
from pathlib import Path
from datetime import datetime, timedelta, date  # Add date here
from zoneinfo import ZoneInfo
import requests
from ical.calendar_stream import IcsCalendarStream
from ical.exceptions import CalendarParseError

class CalendarManager:
    def __init__(self, secrets_file="secrets.json", cache_time_minutes=60):
        self.cache_time_minutes = cache_time_minutes
        self.cache_dir = Path('./cache')
        self.cache_dir.mkdir(exist_ok=True)
        
        # Load secrets
        with open(secrets_file, encoding="utf-8") as f:
            self.secrets = json.load(f)
            
        # Create calendar fingerprint cache
        self.fingerprint_file = self.cache_dir / "calendar_fingerprint.txt"
        
    def get_calendar(self, calendar_key, use_cache=True):
        """Get a calendar by key, using cache if specified"""
        if calendar_key not in self.secrets:
            logging.error(f"Calendar key '{calendar_key}' not found in secrets")
            return None
            
        ics_url = self.secrets[calendar_key]
        if use_cache:
            return self.get_cached_calendar(ics_url)
        else:
            return self.fetch_calendar(ics_url)
            
    def get_cached_calendar(self, ics_url):
        """Get a calendar from cache if recent enough, otherwise fetch it"""
        url_hash = hashlib.md5(ics_url.encode()).hexdigest()
        cache_file = self.cache_dir / f"{url_hash}.pickle"
        
        # Check if cache exists and is recent enough
        if cache_file.exists():
            file_age_minutes = (time.time() - cache_file.stat().st_mtime) / 60
            if file_age_minutes < self.cache_time_minutes:
                try:
                    with open(cache_file, 'rb') as f:
                        logging.info(f"Using cached calendar data ({file_age_minutes:.1f} min old)")
                        return pickle.load(f)
                except Exception as e:
                    logging.error(f"Error loading cache: {e}")

        # Fetch and parse the calendar
        return self.fetch_calendar(ics_url, cache_file)
        
    def fetch_calendar(self, ics_url, cache_file=None):
        """Fetch a calendar from the web and optionally cache it"""
        logging.info(f"Fetching fresh calendar data from {ics_url}")
        
        # Support webcal:// URLs
        if ics_url.startswith("webcal://"):
            ics_url = ics_url.replace("webcal://", "https://", 1)
            
        try:
            response = requests.get(ics_url, timeout=10)
            if response.status_code != 200:
                logging.error(f"Failed to fetch ICS file: HTTP {response.status_code}")
                return None
                
            calendar = IcsCalendarStream.calendar_from_ics(response.text)
            
            # Save to cache if a cache_file is provided
            if cache_file:
                with open(cache_file, 'wb') as f:
                    pickle.dump(calendar, f)
                    
            return calendar
            
        except CalendarParseError as err:
            logging.error(f"Failed to parse ics file from {ics_url}: {err}")
            return None
        except requests.RequestException as err:
            logging.error(f"Request error for {ics_url}: {err}")
            return None
            
    def update_calendars(self):
        """Update all calendars and check if they have changed"""
        calendars = {}
        has_changes = False
        
        # Get the calendars
        for key in self.secrets:
            if key.startswith("calendar"):
                # Use cache for calendar2 but not for calendar1
                use_cache = (key != "calendar1")
                calendars[key] = self.get_calendar(key, use_cache=use_cache)
        
        # Calculate a fingerprint of all calendar events
        new_fingerprint = self.calculate_calendars_fingerprint(calendars)
        
        # Check if the fingerprint has changed
        if self.fingerprint_file.exists():
            try:
                with open(self.fingerprint_file, 'r') as f:
                    old_fingerprint = f.read().strip()
                    if old_fingerprint != new_fingerprint:
                        has_changes = True
                        logging.info("Calendar events have changed")
                    else:
                        logging.info("No changes in calendar events")
            except Exception as e:
                logging.error(f"Error reading fingerprint file: {e}")
                has_changes = True
        else:
            has_changes = True
            logging.info("First run, treating as changed")
            
        # Save the new fingerprint
        with open(self.fingerprint_file, 'w') as f:
            f.write(new_fingerprint)
            
        return calendars, has_changes
        
    def calculate_calendars_fingerprint(self, calendars):
        """Calculate a fingerprint of all calendar events to detect changes"""
        event_data = []
        
        for cal_key, calendar in calendars.items():
            if not calendar:
                continue
                
            # Filter to get only relevant events (next 24 hours)
            now = datetime.now(ZoneInfo("America/Chicago"))
            end_time = now + timedelta(hours=24)
            
            relevant_events = []
            for event in calendar.timeline:
                # Handle both date and datetime values for event start/end
                event_start = event.dtstart
                event_end = event.dtend
                
                # Convert date to datetime if needed
                if isinstance(event_start, date) and not isinstance(event_start, datetime):
                    event_start = datetime.combine(event_start, datetime.min.time(), tzinfo=ZoneInfo("America/Chicago"))
                    
                if isinstance(event_end, date) and not isinstance(event_end, datetime):
                    event_end = datetime.combine(event_end, datetime.max.time(), tzinfo=ZoneInfo("America/Chicago"))
                
                # Now compare using compatible types
                if event_end > now and event_start < end_time:
                    relevant_events.append(event)
            
            # Add each event's key data to the fingerprint
            for event in relevant_events:
                # Convert to string representation for fingerprinting
                start_str = str(event.dtstart)
                end_str = str(event.dtend)
                event_data.append(f"{event.summary}|{start_str}|{end_str}")
                
        # Sort to ensure consistent ordering
        event_data.sort()
        
        # Create a hash of all event data
        fingerprint = hashlib.md5("|".join(event_data).encode()).hexdigest()
        return fingerprint
        
    def filter_events_in_timeframe(self, calendar, start_time, end_time):
        """Filter calendar events to those in a specific timeframe"""
        if not calendar:
            return []
            
        filtered_events = []
        for event in calendar.timeline:
            # Handle both date and datetime values for event start/end
            event_start = event.dtstart
            event_end = event.dtend
            
            # Convert date to datetime if needed
            if isinstance(event_start, date) and not isinstance(event_start, datetime):
                event_start = datetime.combine(event_start, datetime.min.time(), tzinfo=ZoneInfo("America/Chicago"))
                
            if isinstance(event_end, date) and not isinstance(event_end, datetime):
                event_end = datetime.combine(event_end, datetime.max.time(), tzinfo=ZoneInfo("America/Chicago"))
        
            # Now compare using compatible types
            if event_end > start_time and event_start < end_time:
                filtered_events.append(event)
            
        return filtered_events