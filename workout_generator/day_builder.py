"""Day templates: each defines the OTF-style block sequence for one training
day (two timed supersets, two 2-minute buy-outs, one drop-set round, a
timed core finisher, and a boxing-bag round), expressed purely in movement
patterns so the actual exercises can rotate week to week.
"""

from . import exercises as ex_pool
from .blocks import (
    build_bag_round, build_buyout, build_cooldown, build_core_finisher, build_drop_set,
    build_superset, build_warmup,
)

CORE_PAIR = (ex_pool.CORE_FLEX, ex_pool.CORE_ANTI)

# On a deload week, steer buy-outs away from Power/Plyo (the only pattern
# high-impact enough to matter here -- see the templates below, it never
# appears in Block A/B, the drop set, or the core finisher) toward the
# calmer Cardio/Carry alternatives, reusing the same excluded_names steering
# that --exclude-pattern already gives block builders (see blocks.py).
DELOAD_EXCLUDED_NAMES = frozenset(e.name for e in ex_pool.by_pattern(ex_pool.POWER))

DAY_TEMPLATES = [
    {
        "title": "Lower-Body Power & Push",
        "block_a_patterns": (ex_pool.SQUAT, ex_pool.PUSH_H),
        "buyout_1_patterns": (ex_pool.POWER, ex_pool.CARDIO),
        "block_b_patterns": (ex_pool.HINGE, ex_pool.PULL_H),
        "buyout_2_patterns": (ex_pool.CARRY,),
        "drop_set_pattern": ex_pool.ARMS,
        "core_finisher_patterns": CORE_PAIR,
    },
    {
        "title": "Upper-Body Pull & Conditioning",
        "block_a_patterns": (ex_pool.PUSH_V, ex_pool.PULL_V),
        "buyout_1_patterns": (ex_pool.CARDIO,),
        "block_b_patterns": (ex_pool.LUNGE, ex_pool.PULL_H),
        "buyout_2_patterns": (ex_pool.POWER,),
        "drop_set_pattern": ex_pool.GLUTES,
        "core_finisher_patterns": CORE_PAIR,
    },
    {
        "title": "Total-Body Metabolic",
        "block_a_patterns": (ex_pool.LUNGE, ex_pool.PUSH_V),
        "buyout_1_patterns": (ex_pool.CARRY,),
        "block_b_patterns": (ex_pool.SQUAT, ex_pool.PULL_H),
        "buyout_2_patterns": (ex_pool.POWER, ex_pool.CARDIO),
        "drop_set_pattern": ex_pool.CORE_FLEX,
        "core_finisher_patterns": CORE_PAIR,
    },
    {
        "title": "Power & Carry Conditioning",
        "block_a_patterns": (ex_pool.HINGE, ex_pool.PULL_V),
        "buyout_1_patterns": (ex_pool.CARDIO,),
        "block_b_patterns": (ex_pool.LUNGE, ex_pool.PUSH_H),
        "buyout_2_patterns": (ex_pool.CARRY,),
        "drop_set_pattern": ex_pool.ARMS,
        "core_finisher_patterns": CORE_PAIR,
    },
]


def build_day(template, history, used_this_week, rng, avoid_weeks=2, excluded_names=frozenset(), deload=False):
    if deload:
        excluded_names = frozenset(excluded_names) | DELOAD_EXCLUDED_NAMES
    drop_set_title = "Drop Set (8/6/4)" if deload else "Drop Set (10/8/6)"
    blocks = [
        build_warmup(rng),
        build_superset(
            template["block_a_patterns"], history, used_this_week, rng, avoid_weeks,
            title="Block A - Strength Superset", excluded_names=excluded_names, deload=deload,
        ),
        build_buyout(
            template["buyout_1_patterns"], history, used_this_week, rng, avoid_weeks,
            title="Buy-Out 1", excluded_names=excluded_names, deload=deload,
        ),
        build_superset(
            template["block_b_patterns"], history, used_this_week, rng, avoid_weeks,
            title="Block B - Strength Superset", excluded_names=excluded_names, deload=deload,
        ),
        build_buyout(
            template["buyout_2_patterns"], history, used_this_week, rng, avoid_weeks,
            title="Buy-Out 2", excluded_names=excluded_names, deload=deload,
        ),
        build_drop_set(
            template["drop_set_pattern"], history, used_this_week, rng, avoid_weeks,
            title=drop_set_title, excluded_names=excluded_names, deload=deload,
        ),
        build_core_finisher(
            template["core_finisher_patterns"], history, used_this_week, rng, avoid_weeks,
            title="Core Finisher", excluded_names=excluded_names, deload=deload,
        ),
        build_bag_round(
            ex_pool.BAG, history, used_this_week, rng, avoid_weeks,
            title="Bag Finisher", excluded_names=excluded_names, deload=deload,
        ),
        build_cooldown(rng),
    ]
    return {"title": template["title"], "blocks": blocks}


def exercise_names(day):
    """Names used for history's freshness/staleness bookkeeping -- excludes
    warm-up/cooldown blocks, since those are fixed content outside the
    trackable exercise pool (see blocks.py), not exercises to avoid
    repeating week to week."""
    names = []
    for block in day["blocks"]:
        if block["type"] in ("warmup", "cooldown"):
            continue
        names.extend(e.name for e in block["exercises"])
    return names
