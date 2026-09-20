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
BAG = "boxing_bag"  # dedicated bag-round finisher, on every training day

ALL_PATTERNS = [
    SQUAT, HINGE, LUNGE, PUSH_H, PULL_H, PUSH_V, PULL_V,
    ARMS, GLUTES, CALVES, CORE_FLEX, CORE_ANTI, POWER, CARRY, CARDIO, BAG,
]

# Display label + glossary ordering for each pattern.
PATTERN_LABELS = {
    SQUAT: "Squat",
    HINGE: "Hinge / Deadlift",
    LUNGE: "Lunge",
    PUSH_H: "Horizontal Push",
    PULL_H: "Horizontal Pull",
    PUSH_V: "Vertical Push",
    PULL_V: "Vertical Pull",
    ARMS: "Arms",
    GLUTES: "Glutes",
    CALVES: "Calves",
    CORE_FLEX: "Core: Flexion / Rotation",
    CORE_ANTI: "Core: Anti-Extension / Anti-Rotation",
    POWER: "Power / Plyo",
    CARRY: "Loaded Carry",
    CARDIO: "Cardio / Conditioning",
    BAG: "Boxing Bag",
}


@dataclass(frozen=True)
class Exercise:
    name: str
    pattern: str
    equipment: tuple = ()
    unilateral: bool = False
    load_hint: str = "bodyweight"
    note: str = ""  # e.g. which OTF/rower/TRX/bosu move this substitutes for
    tags: tuple = field(default_factory=tuple)
    description: str = ""  # short how-to, for the glossary page


EXERCISES = [
    # ---- Squat ----------------------------------------------------------
    Exercise("Goblet Squat", SQUAT, ("kettlebell", "dumbbell"), load_hint="1x KB/DB, 15-25 lb",
             description="Hold a kettlebell or dumbbell vertically at chest height with both hands. "
                          "Squat down keeping the chest tall and elbows tracking inside the knees, then drive back up."),
    Exercise("Goblet Alt Transverse Squat", SQUAT, ("kettlebell", "dumbbell"), load_hint="1x KB/DB, 10-20 lb",
             description="From a goblet hold, squat down and rotate the torso to tap the weight toward one hip "
                          "at the bottom, alternating sides each rep."),
    Exercise("Goblet Step-Down Toe Tap", SQUAT, ("kettlebell", "dumbbell", "bench"),
             unilateral=True, load_hint="1x KB/DB, 10-15 lb", note="bosu step-down sub",
             description="Standing on a bench or step holding a weight at the chest, lower one leg down to "
                          "lightly tap the floor with the toes, then return to standing on the bench."),
    Exercise("Two-Hand Dumbbell Squat", SQUAT, ("dumbbell",), load_hint="2x DB, 15-25 lb each",
             description="Hold a dumbbell in each hand at your sides and squat down keeping the torso upright, "
                          "then stand back up."),
    Exercise("Sumo Squat to Upright Row", SQUAT, ("dumbbell", "kettlebell"), load_hint="1x KB/DB, 10-20 lb",
             description="From a wide-stance sumo squat holding a weight with both hands, stand up and pull the "
                          "weight up to chest height, leading with the elbows."),
    Exercise("Dumbbell Tap Front Squat", SQUAT, ("dumbbell",), load_hint="2x DB, 10-20 lb each",
             description="Hold two dumbbells at shoulder height and squat down until the dumbbells lightly tap "
                          "near the floor, then stand back up."),
    Exercise("Bench Split Squat (RFE)", SQUAT, ("dumbbell", "bench"), unilateral=True,
             load_hint="2x DB, 10-20 lb each", note="rear-foot-elevated",
             description="With the rear foot elevated on a bench and a dumbbell in each hand, lower the back "
                          "knee toward the floor and drive back up through the front leg."),
    Exercise("Goblet Sit-to-Stand", SQUAT, ("kettlebell", "dumbbell", "bench"),
             load_hint="1x KB/DB, 15-25 lb", note="bosu sit-to-stand sub",
             description="Holding a weight at chest height, sit back onto a bench, then stand back up without "
                          "losing tension in the legs."),

    # ---- Hinge / deadlift -------------------------------------------------
    Exercise("Single-Leg Deadlift", HINGE, ("dumbbell",), unilateral=True, load_hint="1-2x DB, 10-20 lb",
             description="Balancing on one leg with a dumbbell in hand, hinge forward at the hip while the free "
                          "leg extends straight back, then return to standing."),
    Exercise("Split Stance Deadlift", HINGE, ("dumbbell",), unilateral=True, load_hint="2x DB, 15-25 lb each",
             description="From a staggered stance (one foot forward, one back) with a dumbbell in each hand, "
                          "hinge at the hips keeping the back flat, then return to standing."),
    Exercise("Two-Hand Dumbbell Deadlift", HINGE, ("dumbbell",), load_hint="2x DB, 20-30 lb each",
             description="With feet hip-width apart and a dumbbell in each hand, hinge at the hips to lower the "
                          "weights along the shins, then drive the hips forward to stand."),
    Exercise("Alt Step-Out Deadlift", HINGE, ("dumbbell",), load_hint="2x DB, 15-25 lb each",
             description="Step one foot out to the side into a hinge, lowering the dumbbells toward that foot, "
                          "then step back to center and repeat on the other side."),
    Exercise("Single Arm Hip Hinge Swing", HINGE, ("kettlebell",), unilateral=True,
             load_hint="1x KB, 10-15 lb", tags=("power",),
             description="Hike a kettlebell back between the legs with one hand, then snap the hips forward to "
                          "swing it up to chest height, controlling it back down."),

    # ---- Lunge -----------------------------------------------------------
    Exercise("Reverse Lunge", LUNGE, ("dumbbell",), unilateral=True, load_hint="2x DB, 10-20 lb each",
             description="Step one foot backward into a lunge, lowering the back knee toward the floor, then "
                          "push off that foot back to standing."),
    Exercise("Lateral Lunge", LUNGE, ("dumbbell",), unilateral=True, load_hint="1-2x DB, 10-20 lb",
             description="Step one foot out to the side and sit back into that hip while the other leg stays "
                          "straight, then push back to center."),
    Exercise("Forward Lunge", LUNGE, ("dumbbell",), unilateral=True, load_hint="2x DB, 10-20 lb each",
             description="Step one foot forward into a lunge, lowering the back knee toward the floor, then "
                          "push off the front foot back to standing."),
    Exercise("Step-Up to Hammer Curl", LUNGE, ("dumbbell", "bench"), unilateral=True, load_hint="2x DB, 8-15 lb each",
             description="Step up onto a bench with one leg, and as you stand tall at the top, curl a dumbbell "
                          "in each hand up to the shoulders."),
    Exercise("Lunge to Calf Raise", LUNGE, ("dumbbell",), unilateral=True, load_hint="2x DB, 10-20 lb each",
             description="Perform a lunge, and as you return to standing on the working leg, rise onto the ball "
                          "of that foot for a calf raise before lowering."),
    Exercise("Dumbbell Swing Lunge", LUNGE, ("dumbbell",), unilateral=True, load_hint="1x DB, 10-20 lb",
             description="Step into a reverse lunge while swinging a dumbbell from near the front shin up to "
                          "chest height as you drive back to standing."),

    # ---- Horizontal push ---------------------------------------------------
    Exercise("Chest Press", PUSH_H, ("dumbbell", "bench"), load_hint="2x DB, 15-30 lb each",
             description="Lying on a bench with a dumbbell in each hand at chest level, press the weights "
                          "straight up until arms are extended, then lower under control."),
    Exercise("Push-Up", PUSH_H, ("mat",), load_hint="bodyweight",
             description="From a high plank, lower the chest toward the floor keeping the body in a straight "
                          "line, then press back up."),
    Exercise("Push-Up Rotational", PUSH_H, ("mat",), load_hint="bodyweight",
             description="At the top of a push-up, rotate the torso and reach one arm toward the ceiling, "
                          "opening into a side plank, then return and repeat on the other side."),
    Exercise("Push-Up Knee-Drive", PUSH_H, ("mat",), load_hint="bodyweight",
             description="As you press up out of a push-up, drive one knee in toward the same-side elbow, "
                          "alternating sides each rep."),
    Exercise("Alt Chest Fly", PUSH_H, ("dumbbell", "bench"), load_hint="2x DB, 8-15 lb each",
             description="Lying on a bench with a light dumbbell in each hand and arms slightly bent, lower the "
                          "weights out to the sides in an arc, then bring them back together over the chest."),

    # ---- Horizontal pull ---------------------------------------------------
    Exercise("Low Row", PULL_H, ("dumbbell",), load_hint="2x DB, 15-25 lb each",
             description="Hinged forward at the hips with a dumbbell in each hand, pull the elbows straight "
                          "back past the ribs, squeezing the shoulder blades together."),
    Exercise("Low Row (Band)", PULL_H, ("band",), load_hint="medium-heavy band", note="TRX row sub",
             description="Anchor a resistance band at chest height (or under both feet) and pull the handles "
                          "back toward the ribs, squeezing the shoulder blades together."),
    Exercise("Single-Arm High Row", PULL_H, ("dumbbell",), unilateral=True, load_hint="1x DB, 15-25 lb",
             description="Hinged forward with a dumbbell in one hand, pull the elbow up and back toward the "
                          "hip, leading with the elbow high."),
    Exercise("Bird Dog Low Row", PULL_H, ("dumbbell", "mat"), unilateral=True, load_hint="1x DB, 8-15 lb",
             description="From a hands-and-knees position with a dumbbell in one hand, extend the opposite arm "
                          "and leg while rowing the dumbbell up toward the ribs."),

    # ---- Vertical push ------------------------------------------------------
    Exercise("Shoulder Press Seated-to-Stand", PUSH_V, ("dumbbell", "bench"), load_hint="2x DB, 10-20 lb each",
             description="Starting seated on a bench with a dumbbell in each hand at shoulder height, stand up "
                          "as you press the weights overhead."),
    Exercise("Shoulder Press Half-Kneeling", PUSH_V, ("dumbbell",), unilateral=True, load_hint="1x DB, 10-20 lb",
             description="From a half-kneeling position (one knee down), press a dumbbell overhead on the side "
                          "opposite the down knee, bracing the core against rotation."),
    Exercise("Neutral Grip Shoulder Press w/ Rotation", PUSH_V, ("dumbbell",), load_hint="2x DB, 10-15 lb each",
             description="Press two dumbbells overhead with palms facing each other, rotating the torso "
                          "slightly as the weights rise."),
    Exercise("Power Push-Up", PUSH_V, ("mat",), load_hint="bodyweight", tags=("power",),
             description="Perform an explosive push-up, driving hard enough off the floor that the hands leave "
                          "the ground briefly before landing softly."),

    # ---- Vertical pull ------------------------------------------------------
    Exercise("High Pull", PULL_V, ("kettlebell", "dumbbell"), load_hint="1x KB/DB, 10-20 lb",
             description="Hold a kettlebell or dumbbell with both hands in front of the hips and pull it up "
                          "toward chin height, leading with the elbows high and wide."),
    Exercise("Single Arm Clean", PULL_V, ("kettlebell", "dumbbell"), unilateral=True, load_hint="1x KB/DB, 10-15 lb",
             description="In one fluid motion, pull a kettlebell or dumbbell from beside the legs up to a "
                          "racked position at the shoulder."),
    Exercise("Band Face Pull", PULL_V, ("band",), load_hint="light-medium band", note="TRX face pull sub",
             description="Anchor a band at face height and pull the handles back toward the face, leading with "
                          "the elbows high and squeezing the shoulder blades together."),

    # ---- Arms ------------------------------------------------------------
    Exercise("Concentration Curl", ARMS, ("dumbbell", "bench"), unilateral=True, load_hint="1x DB, 8-15 lb",
             description="Seated with an elbow braced against the inner thigh, curl a dumbbell up toward the "
                          "shoulder with strict control."),
    Exercise("Hammer Curl", ARMS, ("dumbbell",), load_hint="2x DB, 8-15 lb each",
             description="Standing with a dumbbell in each hand, palms facing each other, curl the weights up "
                          "toward the shoulders."),
    Exercise("Balance Bicep Curl", ARMS, ("dumbbell",), unilateral=True, load_hint="2x DB, 5-12 lb each",
             description="Standing on one leg, curl dumbbells up toward the shoulders while maintaining balance "
                          "on the standing leg."),
    Exercise("Tricep Extension (Overhead)", ARMS, ("dumbbell",), load_hint="1x DB, 8-15 lb",
             description="Holding one dumbbell with both hands overhead, lower it behind the head by bending "
                          "the elbows, then extend back up."),
    Exercise("Tricep Extension (Bench)", ARMS, ("dumbbell", "bench"), load_hint="2x DB, 8-15 lb each",
             description="Lying on a bench with a dumbbell in each hand extended toward the ceiling, lower the "
                          "weights toward the forehead by bending the elbows, then extend back up."),

    # ---- Glutes ------------------------------------------------------------
    Exercise("Bench Bridge (Shoulders on Bench)", GLUTES, ("bench",), load_hint="bodyweight or 1x DB across hips",
             description="With shoulders resting on a bench and feet flat on the floor, drive the hips up into "
                          "a bridge, squeezing the glutes at the top."),
    Exercise("Sumo Squat Pulse", GLUTES, ("kettlebell", "dumbbell"), load_hint="1x KB/DB, 10-20 lb",
             description="From a wide-stance squat holding a weight, pulse a few inches up and down near the "
                          "bottom of the squat."),
    Exercise("RFE Split Squat (Glute Bias)", GLUTES, ("dumbbell", "bench"), unilateral=True,
             load_hint="2x DB, 10-20 lb each",
             description="A rear-foot-elevated split squat performed with a more upright torso and a longer "
                          "stride to emphasize the glute of the front leg."),

    # ---- Calves ------------------------------------------------------------
    Exercise("Lunge-to-Calf-Raise Combo", CALVES, ("dumbbell",), unilateral=True, load_hint="2x DB, 8-15 lb each",
             description="Combine a lunge with a calf raise at the top of each rep, pausing briefly on the ball "
                          "of the front foot to emphasize the calf."),

    # ---- Core: flexion / rotation -------------------------------------------
    Exercise("Sit-Up to Torso Rotation", CORE_FLEX, ("mat",), load_hint="bodyweight or 1x DB",
             description="Perform a sit-up, and at the top rotate the torso to one side before lowering back "
                          "down, alternating sides each rep."),
    Exercise("Double Crunch", CORE_FLEX, ("mat",), load_hint="bodyweight",
             description="Curl the shoulders and knees toward each other at the same time, crunching the upper "
                          "and lower abs together."),
    Exercise("Sprinter Sit-Up", CORE_FLEX, ("mat",), load_hint="bodyweight",
             description="Sit up while driving one knee up and the opposite elbow back as if sprinting, "
                          "alternating sides each rep."),
    Exercise("Torso Rotation", CORE_FLEX, ("mat", "band"), load_hint="bodyweight or light band",
             description="Seated or standing with a weight or band held at chest height, rotate the torso side "
                          "to side under control."),

    # ---- Core: anti-extension / anti-rotation --------------------------------
    Exercise("Bird Dog", CORE_ANTI, ("mat",), load_hint="bodyweight",
             description="From hands and knees, extend one arm and the opposite leg straight out while keeping "
                          "the hips and back still, then switch sides."),
    Exercise("Deadbug", CORE_ANTI, ("mat",), load_hint="bodyweight",
             description="Lying on your back with arms reaching up and knees bent at 90 degrees, lower one arm "
                          "and the opposite leg toward the floor while keeping the low back pressed down."),
    Exercise("High Plank Pull-Through", CORE_ANTI, ("mat", "dumbbell"), load_hint="1x DB, 5-10 lb",
             description="From a high plank with a dumbbell on the floor to one side, reach under the body with "
                          "the opposite hand to pull the dumbbell across to the other side, keeping the hips level."),
    Exercise("Reverse Fly from Plank", CORE_ANTI, ("mat", "dumbbell"), load_hint="2x DB, 5-10 lb each",
             description="From a high plank position with a dumbbell in each hand, raise both arms out to the "
                          "sides in a fly motion while keeping the hips square and still."),

    # ---- Power / plyo --------------------------------------------------------
    Exercise("Speed Skater", POWER, ("mat",), load_hint="bodyweight",
             description="Leap laterally from one foot to the other in a skating motion, landing softly and "
                          "staying low."),
    Exercise("Squat Jump", POWER, ("mat",), load_hint="bodyweight", note="box jump sub (no box at home)",
             description="From a squat position, jump straight up as high as possible and land softly back "
                          "into the squat."),
    Exercise("In/In-Out/Out", POWER, ("mat",), load_hint="bodyweight",
             description="A fast-feet pattern: jump the feet in, in, out, out in quick succession."),
    Exercise("Up/Up-Down/Down", POWER, ("mat",), load_hint="bodyweight",
             description="A fast-feet pattern: step or jump up, up, down, down in place, staying light on the feet."),
    Exercise("Fast Feet", POWER, (), load_hint="bodyweight", tags=("reaction",),
             description="Rapidly shuffle the feet in place, staying light and quick, low to the ground."),
    Exercise("Heisman", POWER, (), load_hint="bodyweight", tags=("reaction",),
             description="Hop side to side, driving the opposite knee and arm up like a stiff-arm, in a "
                          "shuffling reaction drill."),
    Exercise("Pop Squat", POWER, (), load_hint="bodyweight", tags=("reaction",),
             description="Jump the feet out into a squat and back together in quick succession."),
    Exercise("Burpee", POWER, (), load_hint="bodyweight", tags=("reaction",),
             description="From standing, drop into a squat, kick the feet back to a plank, then jump the feet "
                          "back in and explode up into a jump."),

    # ---- Loaded carry ----------------------------------------------------
    Exercise("Dumbbell Halo", CARRY, ("dumbbell",), load_hint="1x DB, 8-15 lb",
             description="Holding a dumbbell close to the chest, circle it around the head in one direction, "
                          "then reverse."),
    Exercise("Front-Loaded March in Place", CARRY, ("dumbbell", "kettlebell"), load_hint="2x DB/KB, 10-20 lb each",
             description="Hold a dumbbell or kettlebell at each shoulder and march in place, driving the knees "
                          "up high."),

    # ---- Cardio / conditioning (rower-interval substitute) --------------------
    Exercise("Treadmill Sprint Intervals", CARDIO, ("treadmill",), load_hint="n/a", note="rower interval sub",
             description="Alternate short bursts of fast running with easier recovery paces or walks on the "
                          "treadmill."),
    Exercise("Treadmill Incline Walk Intervals", CARDIO, ("treadmill",), load_hint="n/a", note="rower interval sub",
             description="Alternate steep, fast-paced incline walking with easier recovery walking on the "
                          "treadmill."),
    Exercise("Kettlebell Swings", CARDIO, ("kettlebell",), load_hint="1x KB, 10-15 lb",
              note="rower interval sub", tags=("power",),
             description="Hike the kettlebell back between the legs and snap the hips forward to swing it up "
                          "to chest height, repeating continuously."),
    Exercise("Boxing Bag Combos", CARDIO, ("bag",), load_hint="n/a", note="rower interval sub",
             description="Throw continuous punch combinations on the bag for the full interval, keeping the "
                          "feet moving between combos."),

    # ---- Boxing bag (dedicated finisher, every training day) ------------------
    Exercise("Jab-Cross Combo (1-2)", BAG, ("bag",), load_hint="n/a",
             description="Throw a lead-hand jab immediately followed by a rear-hand cross, resetting your "
                          "guard between combos."),
    Exercise("Jab-Cross-Hook Combo (1-2-3)", BAG, ("bag",), load_hint="n/a",
             description="Throw a jab, then a cross, then a lead-hand hook, rotating the hips and feet through "
                          "each punch."),
    Exercise("Hook-Hook-Cross Combo", BAG, ("bag",), load_hint="n/a",
             description="Throw a lead hook, a rear hook, then a cross, rotating the hips through each shot."),
    Exercise("Uppercut-Cross Combo", BAG, ("bag",), load_hint="n/a",
             description="Throw a rear-hand uppercut followed by a cross, driving up through the legs on the "
                          "uppercut."),
    Exercise("Power Cross Ladder", BAG, ("bag",), load_hint="n/a", note="alternating max-power crosses",
             description="Throw alternating rear-hand crosses at maximum power, resetting your stance between "
                          "each one."),
    Exercise("Speed Jabs", BAG, ("bag",), load_hint="n/a", note="high frequency, light power",
             description="Throw rapid, light jabs for pure hand speed rather than power, keeping the guard up "
                          "between shots."),
    Exercise("Freestyle Combo Round", BAG, ("bag",), load_hint="n/a", note="mix combos freely, keep hands moving",
             description="Mix any combos freely for the whole round, keeping the hands up and feet moving the "
                          "entire time."),
]


def by_pattern(pattern: str):
    """Return every exercise for a given movement pattern."""
    return [ex for ex in EXERCISES if ex.pattern == pattern]
