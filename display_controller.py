#!/usr/bin/python
# -*- coding:utf-8 -*-
import logging
import argparse
from datetime import datetime
from calendar_manager import CalendarManager
from display_manager import DisplayManager

class DisplayController:
    """Controller for the e-ink calendar display, optimized for cron-based execution"""
    
    def __init__(self, force_update=False):
        self.force_update = force_update
        self.calendar_manager = CalendarManager()
        self.display_manager = DisplayManager()
        self.last_day = self.get_state_day()
        
        logging.info(f"Display controller initialized (force_update={force_update})")
        
    def get_state_day(self):
        """Get the last updated day from state file"""
        try:
            with open("cache/last_update_day.txt", "r") as f:
                return int(f.read().strip())
        except (FileNotFoundError, ValueError):
            return -1  # Return invalid day to force update
            
    def save_state_day(self, day):
        """Save the current day to state file"""
        try:
            with open("cache/last_update_day.txt", "w") as f:
                f.write(str(day))
        except Exception as e:
            logging.error(f"Failed to save state: {e}")
        
    def check_day_change(self):
        """Check if the day has changed since last update"""
        current_day = datetime.now().day
        if current_day != self.last_day:
            logging.info(f"Day changed from {self.last_day} to {current_day} - forcing update")
            self.last_day = current_day
            self.save_state_day(current_day)
            return True
        return False
        
    def update_display(self):
        """Update the display if needed based on calendar changes or force flag"""
        # Check for day change
        day_changed = self.check_day_change()
        
        # Update calendars and check if they changed
        calendars, has_changes = self.calendar_manager.update_calendars()
        
        if has_changes or self.force_update or day_changed:
            if self.force_update and not has_changes and not day_changed:
                logging.info("Force update requested, updating display even without changes")
            elif day_changed and not has_changes:
                logging.info("Day changed, forcing display update")
            else:
                logging.info("Calendar changes detected, updating display")
                
            if self.update_display_with_calendars(calendars):
                logging.info("Display updated successfully")
                return True
            else:
                logging.error("Failed to update display")
                return False
        else:
            logging.info("No calendar changes or day change, skipping display update")
            return False
            
    def update_display_with_calendars(self, calendars):
        """Update the display with the current calendar data"""
        if not self.display_manager.initialize():
            logging.error("Failed to initialize display")
            return False
            
        # Draw the basic layout
        self.display_manager.draw_layout()
        
        # Draw the current date and time
        self.display_manager.draw_datetime()
        
        # Draw upcoming events from calendar1
        self.display_manager.draw_upcoming_events(calendars.get("calendar1"))
        
        # Draw day blocks from calendar2
        self.display_manager.draw_day_blocks(calendars.get("calendar2"))
        
        # Update the physical display
        success = self.display_manager.update_display()
        
        # Put the display to sleep
        self.display_manager.sleep()
        
        return success

def main():
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("cache/calendar_display.log"),
            logging.StreamHandler()
        ]
    )
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='E-Ink Calendar Display Controller')
    parser.add_argument('--force', action='store_true', help='Force display update even without changes')
    args = parser.parse_args()
    
    # Create controller and update display
    controller = DisplayController(force_update=args.force)
    controller.update_display()

if __name__ == "__main__":
    main()