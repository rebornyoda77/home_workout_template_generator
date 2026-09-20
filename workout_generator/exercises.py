"""Exercise pool, organized by movement pattern.

Every exercise here uses only the home equipment on hand: kettlebells
(5/10/15 lb), dumbbells (5-30 lb), resistance bands, an adjustable bench,
a treadmill, a boxing bag, and yoga mats. There is no rower, TRX, or bosu
ball, so OTF moves that normally rely on that equipment have been swapped
for an equivalent below:

  * Rower intervals      -> treadmill intervals, kettlebell swings, or bag combos
  * TRX moves            -> resistance band or bench-supported dumbbell version
  * Bosu moves           -> flat bench or floor/mat version
"""

from dataclasses import dataclass, field


# Movement pattern keys used to build day/block templates.
SQUAT = "squat"
HINGE = "hinge"
LUNGE = "lunge"
PUSH_H = "push_horizontal"
PULL_H = "pull_horizontal"
PUSH_V = "push_vertical"
PULL_V = "pull_vertical"
ARMS = "arms"
GLUTES = "glutes"
CALVES = "calves"
CORE_FLEX = "core_flexion_rotation"
CORE_ANTI = "core_anti_extension_rotation"
POWER = "power_plyo"
CARRY = "loaded_carry"
CARDIO = "cardio_conditioning"  # rower-interval substitute block

ALL_PATTERNS = [
    SQUAT, HINGE, LUNGE, PUSH_H, PULL_H, PUSH_V, PULL_V,
    ARMS, GLUTES, CALVES, CORE_FLEX, CORE_ANTI, POWER, CARRY, CARDIO,
]


@dataclass(frozen=True)
class Exercise:
    name: str
    pattern: str
    equipment: tuple = ()
    unilateral: bool = False
    load_hint: str = "bodyweight"
    note: str = ""  # e.g. which OTF/rower/TRX/bosu move this substitutes for
    tags: tuple = field(default_factory=tuple)


EXERCISES = [
    # ---- Squat ----------------------------------------------------------
    Exercise("Goblet Squat", SQUAT, ("kettlebell", "dumbbell"), load_hint="1x KB/DB, 15-25 lb"),
    Exercise("Goblet Alt Transverse Squat", SQUAT, ("kettlebell", "dumbbell"), load_hint="1x KB/DB, 10-20 lb"),
    Exercise("Goblet Step-Down Toe Tap", SQUAT, ("kettlebell", "dumbbell", "bench"),
             unilateral=True, load_hint="1x KB/DB, 10-15 lb", note="bosu step-down sub"),
    Exercise("Two-Hand Dumbbell Squat", SQUAT, ("dumbbell",), load_hint="2x DB, 15-25 lb each"),
    Exercise("Sumo Squat to Upright Row", SQUAT, ("dumbbell", "kettlebell"), load_hint="1x KB/DB, 10-20 lb"),
    Exercise("Dumbbell Tap Front Squat", SQUAT, ("dumbbell",), load_hint="2x DB, 10-20 lb each"),
    Exercise("Bench Split Squat (RFE)", SQUAT, ("dumbbell", "bench"), unilateral=True,
             load_hint="2x DB, 10-20 lb each", note="rear-foot-elevated"),
    Exercise("Goblet Sit-to-Stand", SQUAT, ("kettlebell", "dumbbell", "bench"),
             load_hint="1x KB/DB, 15-25 lb", note="bosu sit-to-stand sub"),

    # ---- Hinge / deadlift -------------------------------------------------
    Exercise("Single-Leg Deadlift", HINGE, ("dumbbell",), unilateral=True, load_hint="1-2x DB, 10-20 lb"),
    Exercise("Split Stance Deadlift", HINGE, ("dumbbell",), unilateral=True, load_hint="2x DB, 15-25 lb each"),
    Exercise("Two-Hand Dumbbell Deadlift", HINGE, ("dumbbell",), load_hint="2x DB, 20-30 lb each"),
    Exercise("Alt Step-Out Deadlift", HINGE, ("dumbbell",), load_hint="2x DB, 15-25 lb each"),
    Exercise("Single Arm Hip Hinge Swing", HINGE, ("kettlebell",), unilateral=True,
             load_hint="1x KB, 10-15 lb", tags=("power",)),

    # ---- Lunge -----------------------------------------------------------
    Exercise("Reverse Lunge", LUNGE, ("dumbbell",), unilateral=True, load_hint="2x DB, 10-20 lb each"),
    Exercise("Lateral Lunge", LUNGE, ("dumbbell",), unilateral=True, load_hint="1-2x DB, 10-20 lb"),
    Exercise("Forward Lunge", LUNGE, ("dumbbell",), unilateral=True, load_hint="2x DB, 10-20 lb each"),
    Exercise("Step-Up to Hammer Curl", LUNGE, ("dumbbell", "bench"), unilateral=True, load_hint="2x DB, 8-15 lb each"),
    Exercise("Lunge to Calf Raise", LUNGE, ("dumbbell",), unilateral=True, load_hint="2x DB, 10-20 lb each"),
    Exercise("Dumbbell Swing Lunge", LUNGE, ("dumbbell",), unilateral=True, load_hint="1x DB, 10-20 lb"),

    # ---- Horizontal push ---------------------------------------------------
    Exercise("Chest Press", PUSH_H, ("dumbbell", "bench"), load_hint="2x DB, 15-30 lb each"),
    Exercise("Push-Up", PUSH_H, ("mat",), load_hint="bodyweight"),
    Exercise("Push-Up Rotational", PUSH_H, ("mat",), load_hint="bodyweight"),
    Exercise("Push-Up Knee-Drive", PUSH_H, ("mat",), load_hint="bodyweight"),
    Exercise("Alt Chest Fly", PUSH_H, ("dumbbell", "bench"), load_hint="2x DB, 8-15 lb each"),

    # ---- Horizontal pull ---------------------------------------------------
    Exercise("Low Row", PULL_H, ("dumbbell",), load_hint="2x DB, 15-25 lb each"),
    Exercise("Low Row (Band)", PULL_H, ("band",), load_hint="medium-heavy band", note="TRX row sub"),
    Exercise("Single-Arm High Row", PULL_H, ("dumbbell",), unilateral=True, load_hint="1x DB, 15-25 lb"),
    Exercise("Bird Dog Low Row", PULL_H, ("dumbbell", "mat"), unilateral=True, load_hint="1x DB, 8-15 lb"),

    # ---- Vertical push ------------------------------------------------------
    Exercise("Shoulder Press Seated-to-Stand", PUSH_V, ("dumbbell", "bench"), load_hint="2x DB, 10-20 lb each"),
    Exercise("Shoulder Press Half-Kneeling", PUSH_V, ("dumbbell",), unilateral=True, load_hint="1x DB, 10-20 lb"),
    Exercise("Neutral Grip Shoulder Press w/ Rotation", PUSH_V, ("dumbbell",), load_hint="2x DB, 10-15 lb each"),
    Exercise("Power Push-Up", PUSH_V, ("mat",), load_hint="bodyweight", tags=("power",)),

    # ---- Vertical pull ------------------------------------------------------
    Exercise("High Pull", PULL_V, ("kettlebell", "dumbbell"), load_hint="1x KB/DB, 10-20 lb"),
    Exercise("Single Arm Clean", PULL_V, ("kettlebell", "dumbbell"), unilateral=True, load_hint="1x KB/DB, 10-15 lb"),
    Exercise("Band Face Pull", PULL_V, ("band",), load_hint="light-medium band", note="TRX face pull sub"),

    # ---- Arms ------------------------------------------------------------
    Exercise("Concentration Curl", ARMS, ("dumbbell", "bench"), unilateral=True, load_hint="1x DB, 8-15 lb"),
    Exercise("Hammer Curl", ARMS, ("dumbbell",), load_hint="2x DB, 8-15 lb each"),
    Exercise("Balance Bicep Curl", ARMS, ("dumbbell",), unilateral=True, load_hint="2x DB, 5-12 lb each"),
    Exercise("Tricep Extension (Overhead)", ARMS, ("dumbbell",), load_hint="1x DB, 8-15 lb"),
    Exercise("Tricep Extension (Bench)", ARMS, ("dumbbell", "bench"), load_hint="2x DB, 8-15 lb each"),

    # ---- Glutes ------------------------------------------------------------
    Exercise("Bench Bridge (Shoulders on Bench)", GLUTES, ("bench",), load_hint="bodyweight or 1x DB across hips"),
    Exercise("Sumo Squat Pulse", GLUTES, ("kettlebell", "dumbbell"), load_hint="1x KB/DB, 10-20 lb"),
    Exercise("RFE Split Squat (Glute Bias)", GLUTES, ("dumbbell", "bench"), unilateral=True,
             load_hint="2x DB, 10-20 lb each"),

    # ---- Calves ------------------------------------------------------------
    Exercise("Lunge-to-Calf-Raise Combo", CALVES, ("dumbbell",), unilateral=True, load_hint="2x DB, 8-15 lb each"),

    # ---- Core: flexion / rotation -------------------------------------------
    Exercise("Sit-Up to Torso Rotation", CORE_FLEX, ("mat",), load_hint="bodyweight or 1x DB"),
    Exercise("Double Crunch", CORE_FLEX, ("mat",), load_hint="bodyweight"),
    Exercise("Sprinter Sit-Up", CORE_FLEX, ("mat",), load_hint="bodyweight"),
    Exercise("Torso Rotation", CORE_FLEX, ("mat", "band"), load_hint="bodyweight or light band"),

    # ---- Core: anti-extension / anti-rotation --------------------------------
    Exercise("Bird Dog", CORE_ANTI, ("mat",), load_hint="bodyweight"),
    Exercise("Deadbug", CORE_ANTI, ("mat",), load_hint="bodyweight"),
    Exercise("High Plank Pull-Through", CORE_ANTI, ("mat", "dumbbell"), load_hint="1x DB, 5-10 lb"),
    Exercise("Reverse Fly from Plank", CORE_ANTI, ("mat", "dumbbell"), load_hint="2x DB, 5-10 lb each"),

    # ---- Power / plyo --------------------------------------------------------
    Exercise("Speed Skater", POWER, ("mat",), load_hint="bodyweight"),
    Exercise("Squat Jump", POWER, ("mat",), load_hint="bodyweight", note="box jump sub (no box at home)"),
    Exercise("In/In-Out/Out", POWER, ("mat",), load_hint="bodyweight"),
    Exercise("Up/Up-Down/Down", POWER, ("mat",), load_hint="bodyweight"),
    Exercise("Fast Feet", POWER, (), load_hint="bodyweight", tags=("reaction",)),
    Exercise("Heisman", POWER, (), load_hint="bodyweight", tags=("reaction",)),
    Exercise("Pop Squat", POWER, (), load_hint="bodyweight", tags=("reaction",)),
    Exercise("Burpee", POWER, (), load_hint="bodyweight", tags=("reaction",)),

    # ---- Loaded carry ----------------------------------------------------
    Exercise("Dumbbell Halo", CARRY, ("dumbbell",), load_hint="1x DB, 8-15 lb"),
    Exercise("Front-Loaded March in Place", CARRY, ("dumbbell", "kettlebell"), load_hint="2x DB/KB, 10-20 lb each"),

    # ---- Cardio / conditioning (rower-interval substitute) --------------------
    Exercise("Treadmill Sprint Intervals", CARDIO, ("treadmill",), load_hint="n/a", note="rower interval sub"),
    Exercise("Treadmill Incline Walk Intervals", CARDIO, ("treadmill",), load_hint="n/a", note="rower interval sub"),
    Exercise("Kettlebell Swings", CARDIO, ("kettlebell",), load_hint="1x KB, 10-15 lb",
              note="rower interval sub", tags=("power",)),
    Exercise("Boxing Bag Combos", CARDIO, ("bag",), load_hint="n/a", note="rower interval sub"),
]


def by_pattern(pattern: str):
    """Return every exercise for a given movement pattern."""
    return [ex for ex in EXERCISES if ex.pattern == pattern]
