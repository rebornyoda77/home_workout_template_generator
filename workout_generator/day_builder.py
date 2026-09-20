"""Day templates: each defines the OTF-style block sequence for one training
day (two timed supersets, two 2-minute buy-outs, one drop-set round, a
timed core finisher, and a boxing-bag round), expressed purely in movement
patterns so the actual exercises can rotate week to week.
"""

from . import exercises as ex_pool
from .blocks import build_bag_round, build_buyout, build_core_finisher, build_drop_set, build_superset

CORE_PAIR = (ex_pool.CORE_FLEX, ex_pool.CORE_ANTI)

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


def build_day(template, history, used_this_week, rng, avoid_weeks=2, excluded_names=frozenset()):
    blocks = [
        build_superset(
            template["block_a_patterns"], history, used_this_week, rng, avoid_weeks,
            title="Block A - Strength Superset", excluded_names=excluded_names,
        ),
        build_buyout(
            template["buyout_1_patterns"], history, used_this_week, rng, avoid_weeks,
            title="Buy-Out 1", excluded_names=excluded_names,
        ),
        build_superset(
            template["block_b_patterns"], history, used_this_week, rng, avoid_weeks,
            title="Block B - Strength Superset", excluded_names=excluded_names,
        ),
        build_buyout(
            template["buyout_2_patterns"], history, used_this_week, rng, avoid_weeks,
            title="Buy-Out 2", excluded_names=excluded_names,
        ),
        build_drop_set(
            template["drop_set_pattern"], history, used_this_week, rng, avoid_weeks,
            title="Drop Set (10/8/6)", excluded_names=excluded_names,
        ),
        build_core_finisher(
            template["core_finisher_patterns"], history, used_this_week, rng, avoid_weeks,
            title="Core Finisher", excluded_names=excluded_names,
        ),
        build_bag_round(
            ex_pool.BAG, history, used_this_week, rng, avoid_weeks,
            title="Bag Finisher", excluded_names=excluded_names,
        ),
    ]
    return {"title": template["title"], "blocks": blocks}


def exercise_names(day):
    names = []
    for block in day["blocks"]:
        names.extend(e.name for e in block["exercises"])
    return names
