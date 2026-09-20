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
python main.py rate --week 3 --stars 5  # rate how week 3 went (1-5)
python main.py rate --week 3 --clear    # remove that rating

# bench specific exercises or a whole movement pattern for this week (e.g. a sore shoulder):
python main.py generate --exclude-exercise "Shoulder Press Half-Kneeling"
python main.py generate --exclude-pattern push_vertical
python main.py regenerate --week 3 --exclude-pattern push_vertical --exclude-pattern pull_vertical
```

Each `generate`/`regenerate` run:

1. Picks a set of day templates (see below), rotating which template starts
   the week so the day-to-day flow varies week over week -- nudged by each
   template's average week rating, if any (see "Rate this week" below).
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

`--exclude-exercise`/`--exclude-pattern` are repeatable and available on both
`generate` and `regenerate`, in the web UI as a checkbox list under "Exclude
movement patterns" on the generate/regenerate forms. Some blocks need one
exercise from a specific pattern with no substitute in that slot (e.g. Block
A always needs a Squat and a Horizontal Push pick) — if excluding a whole
pattern can't be fully honored for that reason, you'll get a warning listing
which exercises had to be included anyway, rather than a silent no-op.

Every `generate`/`regenerate`/`delete` also snapshots `data/history.json`
into `data/backups/` (skipped if unchanged from the last snapshot, keeping
the most recent 20) — it's the only state the "don't repeat too often"
logic depends on, so it's worth protecting. `python main.py backups` lists
what's there; to restore one, just copy it back over `data/history.json`.

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
Regenerate/Delete/Print buttons), **History** (every past week, with a View
link and a Delete button per row, and a link into each week's own page which
also has Regenerate/Delete/Print), and **Glossary** (every exercise in the
pool, grouped by movement pattern, with a short how-to, equipment, and load
hint for each, plus a live search box that filters by name/equipment/
description as you type, and how often/recently each has been used). Print
uses the browser's own print dialog (Print This Week -> Ctrl/Cmd+P): a print
stylesheet hides the nav, buttons, and generate form so only that week's
days and blocks end up on paper. The generate and regenerate forms have a
collapsible "Exclude movement patterns" checkbox list for benching a
pattern for the week (see `--exclude-pattern` above).

Every day on the Dashboard/week page also has a log form right under it:
a "Mark this day complete" checkbox, a free-text "what did you actually do"
+ a quick "too easy / just right / too hard" pick per exercise, and a notes
field -- "Save Log" persists it to that day's entry in `data/history.json`
(also picked up by `python main.py list`/`backups`, and backed up like
everything else). A completed day gets a badge next to its title.

Once an exercise has been logged, its most recent "too easy/right/hard"
rating turns into a plain-language suggestion for next time (e.g. `last
time: "20 lb x10" -- felt easy -- try going heavier or adding reps`) --
shown right next to it the next time it's scheduled, and on its Glossary
entry. It's read-only guidance, not automatic: nothing here changes what
the generator picks or the load_hint text on its own.

**Today's Workout** (nav link, or `/today`) jumps straight to the latest
week's first not-yet-completed day in **Focus Mode**: one day at a time,
larger touch-friendly text, Previous/Next Day buttons, and the same log
form -- meant for actually working through the plan on your phone rather
than scrolling a full week. Any day-card also links into Focus Mode
directly ("Open in Focus Mode"). Saving a log from there keeps you on that
same day instead of bouncing to the full week view.

Every block (superset, buy-out, drop set, core finisher, bag round) has a
**Start Timer** button that opens an on-screen interval timer -- no phone
switching to a separate stopwatch app mid-set. It reads the same structure
the block already shows as text, so the countdown can never drift out of
sync with what's printed: fixed work/rest rounds count down and auto-advance
through each exercise, buy-outs run a single continuous countdown, AMRAP-style
blocks auto-cycle exercises on a fixed interval, and drop sets show a
self-paced "GO" step per round (tap "Done -- Start Rest" when you finish that
set) followed by a timed rest. Short tones mark each transition and a longer
tone marks the end of the block; Start/Pause and Skip controls sit under the
countdown, and the timer works the same way on the full week view and in
Focus Mode.

Every week page also has a 1-5 star **Rate this week** control (Clear to
remove it). It's more than a note to yourself: a week's rating nudges which
day templates ("Lower-Body Power & Push", "Total-Body Metabolic", etc.) get
picked more -- or less -- often in future weeks, on top of the usual
week-to-week rotation. A template with no rated weeks behind it yet is
treated as neutral, so an unrated history behaves exactly like plain
rotation always has. History's Rating column shows each past week's stars
at a glance. CLI parity: `python main.py rate --week N --stars 1-5` (or
`--clear`).

The generator pages share the same `data/history.json` as the CLI, so weeks
generated, deleted, or regenerated either way show up on both — manage it
from your phone over the week, or from the terminal, and either sees what
the other did. Set `--host 0.0.0.0` (behind something like Tailscale, not
open to the internet) to reach it from another device.

**Install it as an app** on your phone's home screen instead of using a
browser tab/bookmark: on iOS, open it in Safari and use Share -> Add to
Home Screen; on Android, open it in Chrome and use the menu's Install app
(or "Add to Home screen") option -- Chrome may only offer this automatically
over HTTPS, so plain `http://` over Tailscale/LAN might need the manual menu
option instead of an install banner. Either way you get a standalone app
icon (the same orange "W" as the browser tab) that opens straight into
**Today's Workout**, no browser chrome or address bar. This is served by a
`manifest.json` + a deliberately no-op service worker (it never caches
anything -- every page here is behind the passcode gate and shows live
data, so caching risks showing stale or, on a shared device, another
session's page; the service worker exists purely to satisfy Chrome's
installability check).

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
  static/          manifest.json, service worker, and app icons (PWA install)
data/
  history.json      generated at runtime; tracks exercise-use history
  web_config.json    generated at runtime; hashed web passcode
  backups/           generated at runtime; timestamped history.json snapshots
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
