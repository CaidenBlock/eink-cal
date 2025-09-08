#!/usr/bin/python
# -*- coding:utf-8 -*-
import logging
import sys
import argparse
from display_controller import main as controller_main

def main():
    """Main entry point for the e-ink calendar display (for cron job execution)"""
    controller_main()

if __name__ == "__main__":
    main()