"""Assembles a full training week: picks which day templates to use (rotating
the starting template each week for variety), builds each day, and records
everything used back into the history.
"""

import random
from datetime import date

from .day_builder import DAY_TEMPLATES, build_day, exercise_names
from .history import History


def _select_templates(num_days, start_offset):
    n = len(DAY_TEMPLATES)
    if num_days > n:
        # more days requested than distinct templates: cycle through them
        return [DAY_TEMPLATES[(start_offset + i) % n] for i in range(num_days)]
    return [DAY_TEMPLATES[(start_offset + i) % n] for i in range(num_days)]


def build_week(
    num_days: int,
    history: History,
    rng: random.Random = None,
    avoid_weeks: int = 2,
    generated_at: str = None,
):
    if num_days < 3 or num_days > 4:
        raise ValueError("Weekly plans support 3-4 workout days")

    rng = rng or random.Random()
    generated_at = generated_at or date.today().isoformat()

    week_index = history.begin_week()
    start_offset = (week_index - 1) % len(DAY_TEMPLATES)
    templates = _select_templates(num_days, start_offset)

    used_this_week = set()
    days = []
    for template in templates:
        day = build_day(template, history, used_this_week, rng, avoid_weeks)
        history.record_day(day["title"], exercise_names(day))
        days.append(day)

    history.record_week(generated_at, [d["title"] for d in days])

    return {
        "week_index": week_index,
        "generated_at": generated_at,
        "days": days,
    }
