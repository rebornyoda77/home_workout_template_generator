#!/usr/bin/env python3
"""Entry point: generate a weekly home workout template.

Usage:
    python main.py                    # 4-day week, saves output + updates history
    python main.py --days 3
    python main.py --dry-run          # preview without saving
"""

import sys

from workout_generator.cli import main

if __name__ == "__main__":
    sys.exit(main())
