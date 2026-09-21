"""Builds individual OTF-style blocks: timed supersets, buy-out finishers,
drop-set rounds, and core-interval finishers.

Each block is returned as a plain dict so the formatter and tests don't need
to know about internal classes:

    {
        "type": "superset" | "buyout" | "drop_set" | "core_finisher" | "bag_round",
        "title": str,
        "structure": str,           # human-readable timing/rep scheme
        "exercises": [Exercise, ...],
        "timer": {...},             # machine-readable version of `structure`,
                                     # for the web interval timer -- see below
    }

`timer` shapes (all seconds are ints; `exercise_count` tells the client how
many of the block's exercises to cycle through):
    {"kind": "intervals", "rounds": N, "work_seconds": W, "rest_seconds": R, "exercise_count": E}
        -- N rounds, each round working every exercise for W seconds with
        an R-second rest after each (superset/core-finisher/most bag rounds).
    {"kind": "amrap", "total_seconds": T, "segment_seconds": S, "exercise_count": E}
        -- one continuous T-second block, alternating exercises every S
        seconds, no rest (the "8-minute block, non-stop" superset variant).
    {"kind": "continuous", "seconds": T, "exercise_count": E}
        -- one uninterrupted T-second block (buy-outs, some bag rounds).
    {"kind": "rounds_with_rest", "rounds": N, "rest_seconds": R, "rep_labels": [...]}
        -- N self-paced (rep-based, not timed) rounds with an R-second
        rest between them (drop sets).
"""

import random

from . import exercises as ex_pool
from .history import History


SUPERSET_STRUCTURES = [
    ("4 rounds: 40s work / 20s rest per exercise",
     {"kind": "intervals", "rounds": 4, "work_seconds": 40, "rest_seconds": 20}),
    ("5 rounds: 30s work / 15s rest per exercise",
     {"kind": "intervals", "rounds": 5, "work_seconds": 30, "rest_seconds": 15}),
    ("3 rounds: 45s work / 15s rest per exercise",
     {"kind": "intervals", "rounds": 3, "work_seconds": 45, "rest_seconds": 15}),
    ("8-minute block, non-stop: alternate exercises every 40s",
     {"kind": "amrap", "total_seconds": 480, "segment_seconds": 40}),
]

CORE_FINISHER_STRUCTURES = [
    ("3 rounds: 30s work / 15s rest per exercise",
     {"kind": "intervals", "rounds": 3, "work_seconds": 30, "rest_seconds": 15}),
    ("2 rounds: 45s work / 15s rest per exercise",
     {"kind": "intervals", "rounds": 2, "work_seconds": 45, "rest_seconds": 15}),
]

BUYOUT_DURATION = "2:00 continuous buy-out"
BUYOUT_TIMER = {"kind": "continuous", "seconds": 120}

DROP_SET_REPS = (10, 8, 6)
DROP_SET_REST_SECONDS = 30

BAG_ROUND_STRUCTURES = [
    ("3 rounds: 2:00 work / 30s rest -- throw combos non-stop",
     {"kind": "intervals", "rounds": 3, "work_seconds": 120, "rest_seconds": 30}),
    ("1 round: 3:00 continuous -- keep combos moving the whole round",
     {"kind": "continuous", "seconds": 180}),
    ("4 rounds: 1:00 work / 20s rest -- high output, fast hands",
     {"kind": "intervals", "rounds": 4, "work_seconds": 60, "rest_seconds": 20}),
]

# Warm-up/cooldown moves are fixed, equipment-free content -- not part of
# the trackable exercise pool (no pattern in ALL_PATTERNS, so they never
# show up in the Glossary or compete for freshness/staleness scoring).
# Picked fresh with `rng.sample` each time rather than repeated every week,
# for a little variety, but with no history-based "don't repeat" logic --
# unlike the main pool, that would be overkill for a fixed warm-up routine.
WARMUP_PATTERN = "warmup"
COOLDOWN_PATTERN = "cooldown"

WARMUP_MOVES = [
    ex_pool.Exercise("Arm Circles", WARMUP_PATTERN, load_hint="bodyweight",
                      description="Circle both arms forward, then backward, gradually widening the "
                                   "range of motion to loosen up the shoulders."),
    ex_pool.Exercise("Bodyweight Squats", WARMUP_PATTERN, load_hint="bodyweight",
                      description="Slow, controlled squats to loosen up the hips, knees, and ankles "
                                   "before loading up."),
    ex_pool.Exercise("High Knees", WARMUP_PATTERN, load_hint="bodyweight",
                      description="Jog in place, driving the knees up toward hip height to raise the "
                                   "heart rate and warm up the hip flexors."),
    ex_pool.Exercise("Walking Lunge with Reach", WARMUP_PATTERN, load_hint="bodyweight", unilateral=True,
                      description="Step into a walking lunge and reach both arms overhead at the "
                                   "bottom, opening up the hips and shoulders."),
    ex_pool.Exercise("Jumping Jacks", WARMUP_PATTERN, load_hint="bodyweight",
                      description="Jump the feet out while raising the arms overhead, then back "
                                   "together, to get the whole body moving."),
    ex_pool.Exercise("Inchworm to Push-Up", WARMUP_PATTERN, load_hint="bodyweight",
                      description="Hinge over and walk the hands out to a plank, do one push-up, then "
                                   "walk the feet back up to standing."),
]

COOLDOWN_MOVES = [
    ex_pool.Exercise("Standing Quad Stretch", COOLDOWN_PATTERN, load_hint="bodyweight", unilateral=True,
                      description="Standing on one leg, pull the other heel toward the glutes to "
                                   "stretch the front of the thigh, holding each side."),
    ex_pool.Exercise("Standing Hamstring Stretch", COOLDOWN_PATTERN, load_hint="bodyweight", unilateral=True,
                      description="With one heel propped forward on the floor, hinge at the hips and "
                                   "reach toward the toes, holding each side."),
    ex_pool.Exercise("Doorway Chest Stretch", COOLDOWN_PATTERN, load_hint="bodyweight",
                      description="Place a forearm on a doorframe and gently lean forward to stretch "
                                   "the chest and front of the shoulder, holding each side."),
    ex_pool.Exercise("Child's Pose", COOLDOWN_PATTERN, load_hint="bodyweight",
                      description="Kneel and sit back onto the heels, reaching the arms forward on the "
                                   "floor to stretch the low back and shoulders."),
    ex_pool.Exercise("Cross-Body Shoulder Stretch", COOLDOWN_PATTERN, load_hint="bodyweight", unilateral=True,
                      description="Pull one arm across the chest with the other hand to stretch the "
                                   "back of the shoulder, holding each side."),
    ex_pool.Exercise("Seated Forward Fold", COOLDOWN_PATTERN, load_hint="bodyweight",
                      description="Sit with legs extended and reach toward the toes, keeping the back "
                                   "long, to stretch the hamstrings and low back."),
]

WARMUP_COUNT = 4
COOLDOWN_COUNT = 4
WARMUP_STRUCTURE = f"{WARMUP_COUNT} moves, 30s each -- get the heart rate up and the joints moving"
COOLDOWN_STRUCTURE = f"{COOLDOWN_COUNT} stretches, 30s per side/hold -- bring the heart rate back down"

# Deload/recovery week variants: fixed (not random-rolled) lighter structures
# for every block type -- fewer rounds and/or more rest than any normal-week
# option, so a deload week is unambiguously the lightest version rather than
# just whichever random pick happened to land. See week_builder.is_deload_week
# for how a week gets flagged as a deload week in the first place.
DELOAD_TAG = " -- deload week, keep it light"

DELOAD_SUPERSET_STRUCTURE = (
    f"3 rounds: 30s work / 30s rest per exercise{DELOAD_TAG}",
    {"kind": "intervals", "rounds": 3, "work_seconds": 30, "rest_seconds": 30},
)
DELOAD_CORE_FINISHER_STRUCTURE = (
    f"2 rounds: 30s work / 30s rest per exercise{DELOAD_TAG}",
    {"kind": "intervals", "rounds": 2, "work_seconds": 30, "rest_seconds": 30},
)
DELOAD_BAG_ROUND_STRUCTURE = (
    f"2 rounds: 1:00 work / 45s rest -- easy pace, focus on form{DELOAD_TAG}",
    {"kind": "intervals", "rounds": 2, "work_seconds": 60, "rest_seconds": 45},
)
DELOAD_BUYOUT_DURATION = f"1:00 continuous buy-out{DELOAD_TAG}"
DELOAD_BUYOUT_TIMER = {"kind": "continuous", "seconds": 60}
DELOAD_DROP_SET_REPS = (8, 6, 4)
DELOAD_DROP_SET_REST_SECONDS = 45


def _candidates(pattern, history: History, used_this_week, avoid_weeks, excluded_names=frozenset()):
    pool = ex_pool.by_pattern(pattern)
    if not pool:
        raise ValueError(f"No exercises registered for pattern '{pattern}'")

    def available(fresh_only, respect_exclusions):
        out = []
        for exercise in pool:
            if exercise.name in used_this_week:
                continue
            if respect_exclusions and exercise.name in excluded_names:
                continue
            if fresh_only and history.used_within(exercise.name, avoid_weeks):
                continue
            out.append(exercise)
        return out

    candidates = available(fresh_only=True, respect_exclusions=True)
    if not candidates:
        candidates = available(fresh_only=False, respect_exclusions=True)
    if not candidates:
        # Every non-excluded exercise for this pattern is already used this
        # week, or the whole pattern got excluded -- ignoring the exclusion
        # beats being unable to build the plan at all.
        candidates = available(fresh_only=False, respect_exclusions=False)
    if not candidates:
        # Every exercise for this pattern is already used this week (small
        # pool, big week) -- fall back to the full pattern pool so the
        # generator never errors out.
        candidates = list(pool)
    return candidates


def pick_exercise(pattern, history: History, used_this_week, rng: random.Random, avoid_weeks=2, excluded_names=frozenset()):
    """Pick one exercise for `pattern`, preferring ones not used recently and
    not in `excluded_names` (e.g. benched for the week due to soreness/injury)."""
    candidates = _candidates(pattern, history, used_this_week, avoid_weeks, excluded_names)
    weights = [history.staleness(c.name) for c in candidates]
    if all(w == float("inf") for w in weights):
        weights = [1.0] * len(candidates)
    else:
        finite_max = max((w for w in weights if w != float("inf")), default=1.0)
        weights = [finite_max * 2 if w == float("inf") else w + 0.5 for w in weights]
    choice = rng.choices(candidates, weights=weights, k=1)[0]
    used_this_week.add(choice.name)
    return choice


def build_superset(patterns, history, used_this_week, rng, avoid_weeks=2, title="Block", excluded_names=frozenset(), deload=False):
    picked = [pick_exercise(p, history, used_this_week, rng, avoid_weeks, excluded_names) for p in patterns]
    structure, timer = DELOAD_SUPERSET_STRUCTURE if deload else rng.choice(SUPERSET_STRUCTURES)
    return {
        "type": "superset",
        "title": title,
        "structure": structure,
        "timer": {**timer, "exercise_count": len(picked)},
        "exercises": picked,
    }


def build_buyout(patterns, history, used_this_week, rng, avoid_weeks=2, title="Buy-Out", excluded_names=frozenset(), deload=False):
    pattern_options = patterns if isinstance(patterns, (list, tuple)) else (patterns,)
    # Buy-outs choose freely among several patterns (unlike a superset, which
    # needs one exercise per listed pattern) -- so if one option is entirely
    # excluded, just steer the choice toward the ones that aren't, rather
    # than rolling it anyway and having to ignore the exclusion downstream.
    viable = [p for p in pattern_options if any(e.name not in excluded_names for e in ex_pool.by_pattern(p))]
    pattern = rng.choice(viable) if viable else rng.choice(pattern_options)
    picked = [pick_exercise(pattern, history, used_this_week, rng, avoid_weeks, excluded_names)]
    duration, timer = (DELOAD_BUYOUT_DURATION, DELOAD_BUYOUT_TIMER) if deload else (BUYOUT_DURATION, BUYOUT_TIMER)
    return {
        "type": "buyout",
        "title": title,
        "structure": duration,
        "timer": {**timer, "exercise_count": len(picked)},
        "exercises": picked,
    }


def build_drop_set(pattern, history, used_this_week, rng, avoid_weeks=2, title="Drop Set", excluded_names=frozenset(), deload=False):
    picked = [pick_exercise(pattern, history, used_this_week, rng, avoid_weeks, excluded_names)]
    rep_values = DELOAD_DROP_SET_REPS if deload else DROP_SET_REPS
    rest_seconds = DELOAD_DROP_SET_REST_SECONDS if deload else DROP_SET_REST_SECONDS
    reps = "/".join(str(r) for r in rep_values)
    structure = f"3 rounds, descending reps: {reps} (rest {rest_seconds}s between rounds)"
    if deload:
        structure += DELOAD_TAG
    return {
        "type": "drop_set",
        "title": title,
        "structure": structure,
        "timer": {
            "kind": "rounds_with_rest", "rounds": len(rep_values),
            "rest_seconds": rest_seconds,
            "rep_labels": [str(r) for r in rep_values],
        },
        "exercises": picked,
    }


def build_core_finisher(patterns, history, used_this_week, rng, avoid_weeks=2, title="Core Finisher", excluded_names=frozenset(), deload=False):
    picked = [pick_exercise(p, history, used_this_week, rng, avoid_weeks, excluded_names) for p in patterns]
    structure, timer = DELOAD_CORE_FINISHER_STRUCTURE if deload else rng.choice(CORE_FINISHER_STRUCTURES)
    return {
        "type": "core_finisher",
        "title": title,
        "structure": structure,
        "timer": {**timer, "exercise_count": len(picked)},
        "exercises": picked,
    }


def build_bag_round(pattern, history, used_this_week, rng, avoid_weeks=2, title="Bag Finisher", excluded_names=frozenset(), deload=False):
    picked = [pick_exercise(pattern, history, used_this_week, rng, avoid_weeks, excluded_names)]
    structure, timer = DELOAD_BAG_ROUND_STRUCTURE if deload else rng.choice(BAG_ROUND_STRUCTURES)
    return {
        "type": "bag_round",
        "title": title,
        "structure": structure,
        "timer": {**timer, "exercise_count": len(picked)},
        "exercises": picked,
    }


def build_warmup(rng, count=WARMUP_COUNT, title="Warm-Up"):
    picked = rng.sample(WARMUP_MOVES, k=min(count, len(WARMUP_MOVES)))
    return {
        "type": "warmup",
        "title": title,
        "structure": WARMUP_STRUCTURE,
        "timer": {"kind": "intervals", "rounds": 1, "work_seconds": 30, "rest_seconds": 10, "exercise_count": len(picked)},
        "exercises": picked,
    }


def build_cooldown(rng, count=COOLDOWN_COUNT, title="Cooldown & Stretch"):
    picked = rng.sample(COOLDOWN_MOVES, k=min(count, len(COOLDOWN_MOVES)))
    return {
        "type": "cooldown",
        "title": title,
        "structure": COOLDOWN_STRUCTURE,
        "timer": {"kind": "intervals", "rounds": 1, "work_seconds": 30, "rest_seconds": 5, "exercise_count": len(picked)},
        "exercises": picked,
    }
