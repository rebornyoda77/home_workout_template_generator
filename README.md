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

- [User Guide](docs/user_guide.md) — running the web interface unattended
  on a server, behind nginx and Tailscale

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
python main.py streaks                  # current/longest day-completion streaks

# bench specific exercises or a whole movement pattern for this week (e.g. a sore shoulder):
python main.py generate --exclude-exercise "Shoulder Press Half-Kneeling"
python main.py generate --exclude-pattern push_vertical
python main.py regenerate --week 3 --exclude-pattern push_vertical --exclude-pattern pull_vertical

# every 6th week is automatically a lighter deload/recovery week -- override it either way:
python main.py generate --deload           # force this week to be a deload week
python main.py generate --no-deload        # force it to be a normal week instead

# copy a week's full plan into someone else's history, as a fresh week --
# e.g. give a spouse the same exercises you're doing, for them to retarget:
python main.py copy --week 3 --user dad --to mom

python main.py export                   # full history as CSV, one row per exercise, to stdout
python main.py export --out history.csv # ...or straight to a file

python main.py log --week 3 --day 2 --complete --notes "felt strong"  # mark a day done + note
python main.py log --week 3 --day 2 --incomplete                      # undo that

python main.py balance                  # movement-pattern usage counts, lifetime (ASCII bars)

python main.py family                   # household summary: every account's this-week completions/streaks

# --user picks whose history.json/output to use (see "Web interface" below) --
# every subcommand above accepts it; omit it to use the shared default path
python main.py generate --user dad
python main.py list --user kiddo
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
   on the next run) -- or, with `--user <name>`, that person's own
   `output/<name>/week-NN-*.md` and `data/users/<name>/history.json` instead
   (see "Web interface" below; the web UI always uses your logged-in
   account's own files this way).

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

If the same set of patterns gets benched over and over (a standing shoulder
issue, a leg day you're skipping this cycle), the **Presets** page lets you
save it under a name once -- check the patterns, type a name, Save Preset --
and every "Exclude movement patterns" section afterward (Dashboard,
regenerate, week page) gets an "Apply a saved preset" dropdown that
pre-checks the same boxes for you, no retyping. It's purely a shortcut for
filling in the checkboxes: picking a preset doesn't change what gets
submitted or how exclusion is enforced, and presets are per-account like
everything else. Delete a preset from the same page when it's no longer
needed.

Every 6th week (`week_index % 6 == 0`) is automatically built as a lighter
**deload/recovery week**: 3 rounds instead of 4-5 for supersets, 2 rounds for
the core finisher, a 1-minute buy-out instead of 2, a 3-rep drop set
(8/6/4) instead of 5/8/6 -- all with more rest between rounds -- and
Power/Plyo exercises are steered away from in buy-outs (unless a day
template has no substitute pattern there, the same "no substitute exists"
fallback `--exclude-pattern` already has). `--deload`/`--no-deload` (or the
web UI's own "Deload / recovery week" override, on both the generate and
regenerate forms) force this week to be one, or not, regardless of where it
falls in that schedule; `list` and the web UI both flag a deload week
wherever it shows up.

`python main.py copy --week N --user <source> --to <target>` copies week
N's exact plan -- every day, block, and exercise -- from `<source>`'s
history into `<target>`'s, landing as a brand-new week at the end of
`<target>`'s own sequence (their own next week number, not necessarily
`N`). It's for e.g. a spouse who wants to do the same exercises without
generating their own random pick: completion, notes, and any logged
actual/feel/weight reset (it's a fresh plan for them), but each exercise's
prescribed load carries over as-is, ready for them to retarget in the web
UI. The copy is a fully independent snapshot from that moment -- editing
either person's copy afterward, including its `load_hint`, never touches
the other's. Copying also updates the target's own freshness tracking, so
their next real `generate` treats these exercises as freshly used, same as
if they'd generated the week themselves. In the web UI, every week page has
a "Copy to..." picker (of every other account) and a Copy This Week button;
no CLI/web equivalent exists for the reverse (pulling *from* the target),
since copying is directional -- just swap `--user`/`--to`.

Every exercise's prescribed load (the text next to its name, e.g. "2x DB,
15-25 lb each") is directly editable in the web UI, inline, as part of the
same log form used for completion/notes/actual/feel -- click it and type,
same "Save Log" button. It's a plain edit to that one week's own stored
copy of the exercise (the same independence `copy` above relies on):
editing it never touches the shared exercise pool, any other week, or
anyone else's account.

`python main.py export` (add `--user <name>` for a specific person, `--out
<file>` to write straight to a file instead of stdout) flattens that
person's whole history into CSV, one row per exercise instance across
every generated week -- week number/date/deload flag/rating, day
number/title/completion/notes, block title/type/structure, and the
exercise's own name/prescribed load/weight/actual/feel -- for opening in a
spreadsheet or charting elsewhere. Read-only: it never changes
history.json. The web UI has the same export as a link on the History page.

Every `generate`/`regenerate`/`delete` also snapshots that history file
into a `backups/` folder right next to it (`data/backups/`, or
`data/users/<name>/backups/` with `--user`) — skipped if unchanged from the
last snapshot, keeping the most recent 20. It's the only state the "don't
repeat too often" logic depends on, so it's worth protecting.
`python main.py backups` (add `--user <name>` for a specific person) lists
what's there; to restore one, just copy it back over that same
`history.json`.

Marking a day complete for the first time (see "Web interface" below)
stamps it with today's date; `python main.py streaks` (or the dashboard,
which shows the same numbers) turns those dates into a current streak
(consecutive calendar days with a completed workout -- still counts as
current if you haven't logged today's yet, so it doesn't reset just because
the day isn't over) and your longest streak ever, per account.
`python main.py log --week N --day M --complete/--incomplete --notes
"..."` is the CLI equivalent of the web log form's "Mark this day
complete" + notes fields (day numbers are 1-based, matching what's printed
onscreen) -- per-exercise actual/feel/load logging stays web-only, where
there's a field for each exercise right in front of you.

Once it's been 10+ days since you last generated (or regenerated, or
copied in) a week, the dashboard shows a small reminder -- "It's been N
days since you generated a new week. Ready for the next one?" -- and
`python main.py streaks` prints the same note. It goes away the moment you
generate again; there's no dismiss button, since generating is what it's
nudging you to do.

## Day structure

Every training day opens with a **Warm-Up** (4 bodyweight movement-prep
moves, 30s each) and closes with a **Cooldown & Stretch** (4 static
stretches, 30s per side/hold) -- both picked from a small fixed set with no
equipment needed, and, unlike the rest of the day, not part of the
freshness/staleness tracking that governs the movement-pattern pool below
(a warm-up routine repeating is fine; a strength exercise repeating too
often isn't). They still get a Start Timer button like any other block, but
no "what did you actually do" logging -- that doesn't apply to a stretch.

(Every 6th week is a lighter deload/recovery week by default -- see
"Usage" above -- which swaps the round counts and rest below for lighter
versions, but leaves the warm-up/cooldown alone; they're already easy.)

In between, every training day follows the same OTF-style block skeleton:

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

A small Flask app lets you generate and browse weeks from a browser
instead of the CLI. Each person gets their own login and their own
completely separate history -- generated weeks, exercise-use tracking,
ratings, and logs never mix between accounts, so you can share one
install with your household and everyone sees only their own workouts.

```bash
pip install -r requirements.txt
python web_main.py --add-user       # create your account (and again for anyone else)
python web_main.py                  # runs at http://127.0.0.1:5050
```

`--add-user` prompts for a username, an optional display name, and a
password -- run it once per person. Other account commands:
`--list-users`, `--remove-user <name>` (keeps their data, just removes
the login), and `--migrate-legacy-data <name>` (see "Upgrading from a
single shared login" below). The login page shows a dropdown of every
account by display name -- pick yourself and enter your password.

Pages: **Dashboard** (generate a new week, shows the latest one, with
Regenerate/Delete/Print buttons), **History** (every past week, with a View
link and a Delete button per row, a link into each week's own page which
also has Regenerate/Delete/Print, and an Export as CSV link), **Glossary**
(every exercise in the pool, grouped by movement pattern, with a short
how-to, equipment, and load hint for each, plus a live search box that
filters by name/equipment/description as you type, how often/recently
each has been used, and a "PR: N lb" tag once you've logged a weight for
it), and **Balance** (a bar per movement pattern showing
how many times it's appeared across every week you've generated, lifetime,
plus a Push-vs-Pull total -- patterns that show up in every training day
regardless of which templates get picked, like the core finisher and the
bag round, are tagged "every day" so their bar isn't misread as a rotation
choice; CLI parity: `python main.py balance`, the same counts as ASCII
bars), **Family** (every account's this-week completed-day count and
current/longest streak, side by side, sorted busiest-first -- so anyone
sharing the install can see how everyone's doing without logging in as
them; your own row is tagged "You". CLI parity: `python main.py family`,
the same numbers as a plain table), and **Presets** (create/delete named
movement-pattern exclusion presets -- see above). Print
uses the browser's own print dialog (Print This Week -> Ctrl/Cmd+P): a print
stylesheet hides the nav, buttons, and generate form so only that week's
days and blocks end up on paper. The generate and regenerate forms have a
collapsible "Exclude movement patterns" checkbox list for benching a
pattern for the week (see `--exclude-pattern` above), and a collapsible
"Deload / recovery week" select (Auto / Yes / No) to override that week's
auto-detected deload status (see `--deload`/`--no-deload` above) -- a
deload week shows a small "Deload Week" badge next to its heading on the
Dashboard, week page, Today's Workout, and in the History table. If any
other accounts exist, the week page also has a "Copy to..." picker and a
Copy This Week button (see `copy` above).

Every day on the Dashboard/week page also has a log form right under it:
a "Mark this day complete" checkbox, an editable prescribed-load field per
exercise (click the load text next to its name, e.g. "2x DB, 15-25 lb
each", and type -- see `copy`/load_hint above for why this is safe to
change), a numeric weight field, a free-text reps/notes field + a quick
"too easy / just right / too hard" pick per exercise, and a day-level notes
field -- "Save Log" persists it all to that day's entry in your account's
own `history.json` (also picked up by `python main.py list --user
<name>`/`backups`, and backed up like everything else). A completed day
gets a badge next to its title.

The weight field is kept separate from the free-text reps/notes field
specifically so PRs can be tracked reliably -- a number typed there is
compared against the heaviest weight you've ever logged for that exercise,
across every week, and a new high gets a "New PR: <exercise> at N lb!"
flash on save. It's optional and per-exercise: leave it blank and nothing
changes. The current best for each exercise also shows up as a "PR: N lb"
tag on its Glossary entry.

The first time you mark a day complete, it's stamped with today's date --
once there's at least one, the Dashboard shows a small streak panel above
the generate form: your current streak (consecutive calendar days with a
completed workout; still counts as current if today's isn't logged yet, so
it doesn't drop to zero mid-day), your longest streak ever, and your total
completed workouts, all scoped to your own account. CLI parity: `python
main.py streaks`.

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

The generator pages share the same per-user `data/users/<name>/history.json`
as the CLI's `--user <name>` flag, so weeks generated, deleted, or
regenerated either way show up on both — manage your week from your phone,
or from the terminal, and either sees what the other did. To reach it from
another device, don't just bind `--host 0.0.0.0` (that exposes it,
unencrypted, to everything on your network) — see the
[User Guide](docs/user_guide.md) for running it behind nginx and Tailscale
instead, with a real HTTPS URL and zero public exposure.

### Upgrading from a single shared login

If you're updating an install from before accounts existed, your old data
is still there in `data/history.json` -- nothing was deleted, but the app
won't use it until you claim it:

```bash
python web_main.py --add-user               # create your own account
python web_main.py --migrate-legacy-data <your-username>
```

That moves the old shared `history.json` (and its backups, and any
already-generated `output/week-*.md` files) into your new account. Run
`--add-user` again for anyone else in your household -- they start with a
fresh, empty history of their own.

**Install it as an app** on your phone's home screen instead of using a
browser tab/bookmark: on iOS, open it in Safari and use Share -> Add to
Home Screen; on Android, open it in Chrome and use the menu's Install app
(or "Add to Home screen") option -- Chrome may only offer this automatically
over HTTPS, so plain `http://` over Tailscale/LAN might need the manual menu
option instead of an install banner. Either way you get a standalone app
icon (the same orange "W" as the browser tab) that opens straight into
**Today's Workout**, no browser chrome or address bar. This is served by a
`manifest.json` + a deliberately no-op service worker (it never caches
anything -- every page here is behind a login and shows live per-user
data, so caching risks showing stale or, on a shared device, another
account's page; the service worker exists purely to satisfy Chrome's
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
  export.py        flattens history into CSV rows (`export`, one row per exercise)
  balance.py       aggregates use_count by movement pattern (`balance` / the Balance page)
  generate.py      shared "build a week + persist it" logic (CLI + web)
  cli.py           argparse CLI (see main.py)
  users.py         account storage (data/users.json) -- one login per person
  user_paths.py    resolves a username to their own history/output paths
  migrate.py       one-time move of pre-accounts data into a named user
  web_server.py    Flask app (see web_main.py)
  templates/       Jinja2 templates for the web interface
  static/          manifest.json, service worker, and app icons (PWA install)
data/
  users.json         generated at runtime; account usernames + hashed passwords
  users/<name>/
    history.json       generated at runtime; that user's own exercise-use history
    backups/            generated at runtime; timestamped history.json snapshots
  history.json       pre-accounts installs only; see "Upgrading" above
output/
  <name>/week-*.md  generated weekly plans, one folder per user
  week-*.md         pre-accounts installs only; see "Upgrading" above
tests/
  test_generator.py
  test_web.py
```

## Tests

```bash
python -m unittest discover -s tests -v
```
