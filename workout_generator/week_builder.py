"""Assembles a full training week: picks which day templates to use (rotating
the starting template each week for variety), builds each day, and records
everything used back into the history.
"""

import random
from dataclasses import asdict
from datetime import date

from .day_builder import DAY_TEMPLATES, build_day, exercise_names
from .history import History


def _select_templates(num_days, start_offset):
    n = len(DAY_TEMPLATES)
    if num_days > n:
        # more days requested than distinct templates: cycle through them
        return [DAY_TEMPLATES[(start_offset + i) % n] for i in range(num_days)]
    return [DAY_TEMPLATES[(start_offset + i) % n] for i in range(num_days)]


def serialize_day(day: dict) -> dict:
    """Turns a day's Exercise dataclass instances into plain dicts so the
    whole week can be stored as JSON in history and redisplayed later
    (e.g. by the web interface) without regenerating it. Also seeds the
    logging fields (completed/notes per day, actual/feel per exercise --
    see History.update_day_log) so a freshly generated week has a
    consistent shape from the start, ready to be logged against."""
    return {
        "title": day["title"],
        "completed": False,
        "notes": "",
        "blocks": [
            {
                "type": block["type"],
                "title": block["title"],
                "structure": block["structure"],
                "exercises": [{**asdict(e), "actual": "", "feel": ""} for e in block["exercises"]],
            }
            for block in day["blocks"]
        ],
    }


def _validate_num_days(num_days: int) -> None:
    if num_days < 3 or num_days > 4:
        raise ValueError("Weekly plans support 3-4 workout days")


def _build_days(
    num_days: int, slot_index: int, history: History, rng: random.Random, avoid_weeks: int,
    excluded_names=frozenset(),
):
    """Builds one week's worth of days. `slot_index` only decides which day
    templates to start rotating from (so a given slot always leans toward
    the same day-template flavor); it does not affect exercise freshness
    scoring, which always runs off history's live week counter -- see
    History.record_week's docstring for why that matters for regenerate."""
    start_offset = (slot_index - 1) % len(DAY_TEMPLATES)
    templates = _select_templates(num_days, start_offset)

    used_this_week = set()
    days = []
    for template in templates:
        day = build_day(template, history, used_this_week, rng, avoid_weeks, excluded_names)
        history.record_day(day["title"], exercise_names(day))
        days.append(day)
    return days


def build_week(
    num_days: int,
    history: History,
    rng: random.Random = None,
    avoid_weeks: int = 2,
    generated_at: str = None,
    excluded_names=frozenset(),
):
    _validate_num_days(num_days)
    rng = rng or random.Random()
    generated_at = generated_at or date.today().isoformat()

    week_index = history.begin_week()
    days = _build_days(num_days, week_index, history, rng, avoid_weeks, excluded_names)
    history.record_week(generated_at, [serialize_day(d) for d in days])

    return {
        "week_index": week_index,
        "generated_at": generated_at,
        "days": days,
    }


def regenerate_week(
    week_index: int,
    num_days: int,
    history: History,
    rng: random.Random = None,
    avoid_weeks: int = 2,
    generated_at: str = None,
    excluded_names=frozenset(),
):
    """Rerolls a specific week's content in place, keeping its week_index
    (so its slot in history/the web UI doesn't move). Any existing entry
    at that index is discarded first -- its exercises no longer count
    toward freshness scoring, so the reroll is free to reuse them if
    they're otherwise the freshest choice."""
    _validate_num_days(num_days)
    rng = rng or random.Random()
    generated_at = generated_at or date.today().isoformat()

    history.delete_week(week_index)
    # Regenerating happens "now", so freshness scoring shouldn't regress to
    # treat it as further in the past than the most recent week still on
    # record -- only relevant when the week being regenerated was itself
    # the highest index and got wiped out by delete_week above.
    history.week_index = max(history.week_index, week_index)

    days = _build_days(num_days, week_index, history, rng, avoid_weeks, excluded_names)
    history.record_week(generated_at, [serialize_day(d) for d in days], week_index=week_index)

    return {
        "week_index": week_index,
        "generated_at": generated_at,
        "days": days,
    }
