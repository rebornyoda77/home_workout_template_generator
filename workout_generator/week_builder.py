"""Assembles a full training week: picks which day templates to use (rotating
the starting template each week for variety), builds each day, and records
everything used back into the history.
"""

import random
from dataclasses import asdict
from datetime import date

from .day_builder import DAY_TEMPLATES, build_day, exercise_names
from .history import History


DELOAD_INTERVAL_WEEKS = 6


def is_deload_week(week_index: int, interval: int = DELOAD_INTERVAL_WEEKS) -> bool:
    """Every `interval`th week is automatically treated as a lighter
    deload/recovery week (see blocks.py's DELOAD_* structures and
    day_builder.build_day for what that actually changes), unless the
    caller passes an explicit `deload=True/False` override to build_week/
    regenerate_week. `interval <= 0` disables auto-detection entirely."""
    return interval > 0 and week_index > 0 and week_index % interval == 0


def _template_bias(avg_rating) -> float:
    """Turns a template's average week rating (1-5) into a +/-3 nudge on
    top of its rotation position -- neutral (0) when the template has no
    rated weeks behind it yet, so an unrated app behaves exactly like the
    old pure-rotation selection below."""
    if avg_rating is None:
        return 0.0
    return (avg_rating - 3) * 1.5


def _select_templates(num_days, start_offset, rating_bias=None):
    """Picks which day templates make up this week. Rotation (starting
    from `start_offset`, which slot_index derives) decides the baseline
    order so a given week slot still leans toward the same flavor as
    before; `rating_bias` (title -> +/-3, from _template_bias) can then
    outrank that position, so templates behind consistently well-rated
    weeks get chosen more often -- and ones behind poorly-rated weeks less
    often -- for weeks that don't have room for all of them. With no
    ratings at all, every bias is 0 and this reduces to plain rotation."""
    rating_bias = rating_bias or {}
    n = len(DAY_TEMPLATES)
    if num_days > n:
        # more days requested than distinct templates: cycle through them
        return [DAY_TEMPLATES[(start_offset + i) % n] for i in range(num_days)]

    rotation_order = [DAY_TEMPLATES[(start_offset + i) % n] for i in range(n)]
    ranked = sorted(
        enumerate(rotation_order),
        key=lambda pair: (n - pair[0]) + rating_bias.get(pair[1]["title"], 0.0),
        reverse=True,
    )
    chosen_titles = {template["title"] for _, template in ranked[:num_days]}
    return [template for template in rotation_order if template["title"] in chosen_titles]


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
                "timer": block["timer"],
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
    excluded_names=frozenset(), deload: bool = False,
):
    """Builds one week's worth of days. `slot_index` only decides which day
    templates to start rotating from (so a given slot always leans toward
    the same day-template flavor); it does not affect exercise freshness
    scoring, which always runs off history's live week counter -- see
    History.record_week's docstring for why that matters for regenerate."""
    start_offset = (slot_index - 1) % len(DAY_TEMPLATES)
    rating_bias = {title: _template_bias(avg) for title, avg in history.template_average_ratings().items()}
    templates = _select_templates(num_days, start_offset, rating_bias)

    used_this_week = set()
    days = []
    for template in templates:
        day = build_day(template, history, used_this_week, rng, avoid_weeks, excluded_names, deload=deload)
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
    deload: bool = None,
):
    """`deload=None` (the default) auto-detects via is_deload_week; pass
    True/False to force this week to be (or not be) a lighter recovery
    week regardless of where it falls in the interval."""
    _validate_num_days(num_days)
    rng = rng or random.Random()
    generated_at = generated_at or date.today().isoformat()

    week_index = history.begin_week()
    deload_flag = is_deload_week(week_index) if deload is None else bool(deload)
    days = _build_days(num_days, week_index, history, rng, avoid_weeks, excluded_names, deload=deload_flag)
    history.record_week(generated_at, [serialize_day(d) for d in days], deload=deload_flag)

    return {
        "week_index": week_index,
        "generated_at": generated_at,
        "deload": deload_flag,
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
    deload: bool = None,
):
    """Rerolls a specific week's content in place, keeping its week_index
    (so its slot in history/the web UI doesn't move). Any existing entry
    at that index is discarded first -- its exercises no longer count
    toward freshness scoring, so the reroll is free to reuse them if
    they're otherwise the freshest choice. `deload` behaves as in
    build_week -- None auto-detects from this same week_index."""
    _validate_num_days(num_days)
    rng = rng or random.Random()
    generated_at = generated_at or date.today().isoformat()

    history.delete_week(week_index)
    # Regenerating happens "now", so freshness scoring shouldn't regress to
    # treat it as further in the past than the most recent week still on
    # record -- only relevant when the week being regenerated was itself
    # the highest index and got wiped out by delete_week above.
    history.week_index = max(history.week_index, week_index)

    deload_flag = is_deload_week(week_index) if deload is None else bool(deload)
    days = _build_days(num_days, week_index, history, rng, avoid_weeks, excluded_names, deload=deload_flag)
    history.record_week(generated_at, [serialize_day(d) for d in days], week_index=week_index, deload=deload_flag)

    return {
        "week_index": week_index,
        "generated_at": generated_at,
        "deload": deload_flag,
        "days": days,
    }
