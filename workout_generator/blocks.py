"""Builds individual OTF-style blocks: timed supersets, buy-out finishers,
drop-set rounds, and core-interval finishers.

Each block is returned as a plain dict so the formatter and tests don't need
to know about internal classes:

    {
        "type": "superset" | "buyout" | "drop_set" | "core_finisher",
        "title": str,
        "structure": str,           # human-readable timing/rep scheme
        "exercises": [Exercise, ...],
    }
"""

import random

from . import exercises as ex_pool
from .history import History


SUPERSET_STRUCTURES = [
    "4 rounds: 40s work / 20s rest per exercise",
    "5 rounds: 30s work / 15s rest per exercise",
    "3 rounds: 45s work / 15s rest per exercise",
    "8-minute block, non-stop: alternate exercises every 40s",
]

CORE_FINISHER_STRUCTURES = [
    "3 rounds: 30s work / 15s rest per exercise",
    "2 rounds: 45s work / 15s rest per exercise",
]

BUYOUT_DURATION = "2:00 continuous buy-out"
DROP_SET_REPS = (10, 8, 6)


def _candidates(pattern, history: History, used_this_week, avoid_weeks):
    pool = ex_pool.by_pattern(pattern)
    if not pool:
        raise ValueError(f"No exercises registered for pattern '{pattern}'")

    def available(fresh_only):
        out = []
        for exercise in pool:
            if exercise.name in used_this_week:
                continue
            if fresh_only and history.used_within(exercise.name, avoid_weeks):
                continue
            out.append(exercise)
        return out

    candidates = available(fresh_only=True)
    if not candidates:
        candidates = available(fresh_only=False)
    if not candidates:
        # Every exercise for this pattern is already used this week (small
        # pool, big week) -- fall back to the full pattern pool so the
        # generator never errors out.
        candidates = list(pool)
    return candidates


def pick_exercise(pattern, history: History, used_this_week, rng: random.Random, avoid_weeks=2):
    """Pick one exercise for `pattern`, preferring ones not used recently."""
    candidates = _candidates(pattern, history, used_this_week, avoid_weeks)
    weights = [history.staleness(c.name) for c in candidates]
    if all(w == float("inf") for w in weights):
        weights = [1.0] * len(candidates)
    else:
        finite_max = max((w for w in weights if w != float("inf")), default=1.0)
        weights = [finite_max * 2 if w == float("inf") else w + 0.5 for w in weights]
    choice = rng.choices(candidates, weights=weights, k=1)[0]
    used_this_week.add(choice.name)
    return choice


def build_superset(patterns, history, used_this_week, rng, avoid_weeks=2, title="Block"):
    picked = [pick_exercise(p, history, used_this_week, rng, avoid_weeks) for p in patterns]
    return {
        "type": "superset",
        "title": title,
        "structure": rng.choice(SUPERSET_STRUCTURES),
        "exercises": picked,
    }


def build_buyout(patterns, history, used_this_week, rng, avoid_weeks=2, title="Buy-Out"):
    pattern = rng.choice(patterns) if isinstance(patterns, (list, tuple)) else patterns
    picked = [pick_exercise(pattern, history, used_this_week, rng, avoid_weeks)]
    return {
        "type": "buyout",
        "title": title,
        "structure": BUYOUT_DURATION,
        "exercises": picked,
    }


def build_drop_set(pattern, history, used_this_week, rng, avoid_weeks=2, title="Drop Set"):
    picked = [pick_exercise(pattern, history, used_this_week, rng, avoid_weeks)]
    reps = "/".join(str(r) for r in DROP_SET_REPS)
    return {
        "type": "drop_set",
        "title": title,
        "structure": f"3 rounds, descending reps: {reps} (rest 30s between rounds)",
        "exercises": picked,
    }


def build_core_finisher(patterns, history, used_this_week, rng, avoid_weeks=2, title="Core Finisher"):
    picked = [pick_exercise(p, history, used_this_week, rng, avoid_weeks) for p in patterns]
    return {
        "type": "core_finisher",
        "title": title,
        "structure": rng.choice(CORE_FINISHER_STRUCTURES),
        "exercises": picked,
    }
