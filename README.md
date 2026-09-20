# Home Workout Template Generator

Generates a weekly home workout plan (3-4 days) modeled on Orangetheory's
block structure — timed supersets, 2-minute metabolic buy-outs, and
descending-rep drop sets — built only from equipment you actually have:

- Kettlebells (5, 10, 15 lb)
- Dumbbells (5-30 lb)
- Resistance bands
- Adjustable bench
- Treadmill
- Boxing bag
- Yoga mats

No rower, TRX, or bosu ball. OTF moves that normally use that equipment are
swapped for a home-equivalent (see `workout_generator/exercises.py` module
docstring and each exercise's `note` field):

| OTF equipment | Home substitute |
| --- | --- |
| Rower intervals | Treadmill intervals, kettlebell swings, or boxing bag combos |
| TRX moves | Resistance band or bench-supported dumbbell version |
| Bosu moves | Flat bench or floor/mat version |

## Usage

```bash
python main.py                 # generate a 4-day week, save output + history
python main.py --days 3        # generate a 3-day week
python main.py --dry-run       # preview without writing files or history
python main.py --seed 42       # reproducible output, for testing
```

Each run:

1. Picks a set of day templates (see below), rotating which template starts
   the week so the day-to-day flow varies week over week.
2. Fills each block with exercises, preferring ones that haven't been used
   in the last `--avoid-weeks` weeks (default 2) and never repeating an
   exercise already used elsewhere that same week while alternatives exist.
3. Writes the plan to `output/week-NN-YYYY-MM-DD.md` and updates
   `data/history.json` (the record the "don't repeat too often" logic reads
   on the next run).

## Day structure

Every training day follows the same OTF-style block skeleton:

1. **Block A - Strength Superset** — two exercises back-to-back for a timed
   scheme (e.g. 4 rounds of 40s work / 20s rest each).
2. **Buy-Out 1** — a 2-minute continuous metabolic finisher (power/plyo,
   loaded carry, or a cardio-interval substitute for OTF's rower block).
3. **Block B - Strength Superset** — a second timed superset, different
   movement patterns than Block A.
4. **Buy-Out 2** — a second 2-minute buy-out.
5. **Drop Set (10/8/6)** — one exercise, three rounds of descending reps.
6. **Core Finisher** — a timed interval pairing a flexion/rotation move with
   an anti-extension/anti-rotation move.

Four day templates rotate through the week (`Lower-Body Power & Push`,
`Upper-Body Pull & Conditioning`, `Total-Body Metabolic`,
`Power & Carry Conditioning`), each pulling from different movement-pattern
pairs so a 3- or 4-day week stays varied. See
`workout_generator/day_builder.py` for the exact pattern assignments.

## Project layout

```
workout_generator/
  exercises.py     exercise pool, tagged by movement pattern + equipment
  history.py       loads/saves data/history.json, scores exercise staleness
  blocks.py        builds individual blocks (superset/buyout/drop set/core)
  day_builder.py    day templates + assembling one day's blocks
  week_builder.py  picks day templates and assembles a full week
  formatter.py     renders a generated week to Markdown
  cli.py           argparse CLI (see main.py)
data/
  history.json     generated at runtime; tracks exercise-use history
output/
  week-*.md        generated weekly plans
tests/
  test_generator.py
```

## Tests

```bash
python -m unittest discover -s tests -v
```
