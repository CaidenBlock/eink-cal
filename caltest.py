from pathlib import Path
from ical.calendar_stream import IcsCalendarStream
from ical.exceptions import CalendarParseError
import json
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Load secrets
with open("secrets.json") as f:
    secrets = json.load(f)
    ics_url = secrets["calendar2"]

# Get the ICS file from the web
response = requests.get(ics_url)
