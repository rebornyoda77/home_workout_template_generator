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
python main.py                          # generate a 4-day week (same as `generate`)
python main.py --days 3                 # generate a 3-day week
python main.py --dry-run                # preview without writing files or history
python main.py --seed 42                # reproducible output, for testing

python main.py list                     # list every generated week
python main.py delete --week 3          # delete week 3
python main.py regenerate --week 3      # reroll week 3's exercises, same slot/day count
python main.py regenerate --week 3 --days 4   # ...and change its day count too
```

Each `generate`/`regenerate` run:

1. Picks a set of day templates (see below), rotating which template starts
   the week so the day-to-day flow varies week over week.
2. Fills each block with exercises, preferring ones that haven't been used
   in the last `--avoid-weeks` weeks (default 2) and never repeating an
   exercise already used elsewhere that same week while alternatives exist.
3. Writes the plan to `output/week-NN-YYYY-MM-DD.md` and updates
   `data/history.json` (the record the "don't repeat too often" logic reads
   on the next run).

`regenerate` keeps the week's number (so its spot in `list`/the web history
page doesn't move) but discards its old exercises before rerolling, so they
don't count against the new pick's freshness. `delete` removes a week
entirely and recomputes exercise-use stats from what's left, so a deleted
week's exercises are free to reappear sooner than they otherwise would have.

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
7. **Bag Finisher** — a timed round on the boxing bag (e.g. 3 rounds of 2:00
   work / 30s rest), picked from a dedicated pool of distinct combos
   (jab-cross, hook-hook-cross, uppercut-cross, power cross ladder, speed
   jabs, ...) so it varies day to day. Every training day gets one.

Four day templates rotate through the week (`Lower-Body Power & Push`,
`Upper-Body Pull & Conditioning`, `Total-Body Metabolic`,
`Power & Carry Conditioning`), each pulling from different movement-pattern
pairs so a 3- or 4-day week stays varied. See
`workout_generator/day_builder.py` for the exact pattern assignments.

## Web interface

A small Flask app (styled like the budget tool's web interface: single
passcode gate, no accounts) lets you generate and browse weeks from a
browser instead of the CLI.

```bash
pip install -r requirements.txt
python web_main.py --set-passcode   # first time only
python web_main.py                  # runs at http://127.0.0.1:5050
```

Pages: **Dashboard** (generate a new week, shows the latest one, with
Regenerate/Delete buttons), **History** (every past week, with a View link
and a Delete button per row, and a link into each week's own page which also
has Regenerate/Delete), and **Glossary** (every exercise in the pool, grouped
by movement pattern, with a short how-to, equipment, and load hint for each).
The generator pages share the same `data/history.json` as the CLI, so weeks
generated, deleted, or regenerated either way show up on both — manage it
from your phone over the week, or from the terminal, and either sees what
the other did. Set `--host 0.0.0.0` (behind something like Tailscale, not
open to the internet) to reach it from another device.

## Project layout

```
workout_generator/
  exercises.py     exercise pool, tagged by movement pattern + equipment
  history.py       loads/saves data/history.json, scores exercise staleness
  blocks.py        builds individual blocks (superset/buyout/drop set/core)
  day_builder.py    day templates + assembling one day's blocks
  week_builder.py  picks day templates and assembles a full week
  formatter.py     renders a generated week to Markdown
  generate.py      shared "build a week + persist it" logic (CLI + web)
  cli.py           argparse CLI (see main.py)
  web_config.py    web passcode storage (data/web_config.json)
  web_server.py    Flask app (see web_main.py)
  templates/       Jinja2 templates for the web interface
data/
  history.json      generated at runtime; tracks exercise-use history
  web_config.json    generated at runtime; hashed web passcode
output/
  week-*.md        generated weekly plans
tests/
  test_generator.py
  test_web.py
```

## Tests

```bash
python -m unittest discover -s tests -v
```
