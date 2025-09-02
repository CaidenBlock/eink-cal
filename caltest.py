from ics import Calendar
import json
import datetime
from zoneinfo import ZoneInfo
import requests

with open("secrets.json") as f:
    secrets = json.load(f)


ics_url = secrets["calendar1"]
response = requests.get(ics_url)
calendar = Calendar(response.text)
x = 5  # Number of upcoming events you want
now = datetime.datetime.now(ZoneInfo("America/Chicago"))
upcoming_events = []

for event in sorted(calendar.events, key=lambda e: e.begin):
    if event.begin.datetime > now:
        upcoming_events.append(event)
    if len(upcoming_events) >= x:
        break

print("Upcoming Events:")
for event in upcoming_events:
    print(f" - {event.name} at {event.begin.datetime}")
print(upcoming_events[0].name)