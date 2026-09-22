# Exercise diagrams

This folder is where per-exercise how-to diagrams live. It's currently
empty -- this is the scaffolding for adding them, not the diagrams
themselves.

## How it works

Nothing in `exercises.py` needs to change to add a diagram. The Glossary
page (`workout_generator/diagrams.py`) looks for a file in this folder
named after the exercise, slugified: lowercase, spaces and punctuation
collapsed to single hyphens. E.g.:

| Exercise name              | Expected filename            |
| --------------------------- | ----------------------------- |
| Goblet Squat                 | `goblet-squat.png`             |
| Single-Arm High Row          | `single-arm-high-row.png`      |
| Bird Dog Low Row (each side) | `bird-dog-low-row.png` (the "(each side)" tag is shown separately, not part of the exercise's own name) |

Supported extensions, checked in this order: `.svg`, `.png`, `.webp`,
`.jpg`/`.jpeg`, `.gif` -- so a hand-drawn SVG takes priority over a raster
fallback for the same exercise if both exist. Just drop a correctly-named
file in; it shows up on the very next page load, no restart or code change
needed. An exercise with no matching file here simply shows no diagram, as
today.

To get the exact expected filename for every exercise currently in the
pool (e.g. to plan out what to source, or to batch-rename downloaded
images), run:

```bash
python3 -c "
from workout_generator import exercises as ex_pool
from workout_generator.diagrams import diagram_slug
for e in sorted(ex_pool.EXERCISES, key=lambda e: e.name):
    print(f'{diagram_slug(e.name)}.png  <-  {e.name}')
"
```

## Where to source images

Not populated yet -- a few candidates worth checking when it's time to
fill this in, roughly in order of how little friction they add to a
self-hosted, offline-friendly setup like this one:

- **[free-exercise-db](https://github.com/yuhonas/free-exercise-db)** --
  exercise data with step-by-step JPEG images, released to the public
  domain (Unlicense). No attribution required, easiest to just vendor in.
- **[wger](https://wger.de/)** -- open-source workout manager with its own
  exercise database and a public API; images are CC-BY-SA 4.0, so using
  them means keeping attribution and the same license on redistribution.
- **[Everkinetic](https://everkinetic.com/)** -- illustrated exercise
  library; check the current license on whatever's pulled from it, it's
  varied release-to-release.
- **[ExerciseDB](https://exercisedb.dev/)** (or similar RapidAPI-hosted
  APIs) -- animated GIFs, but commercial/freemium and needs an API key +
  network access, which cuts against this app's self-hosted-on-a-Pi,
  no-external-dependency design.

Whatever the source, this project is for personal/household use, not
redistribution -- but license terms (especially CC-BY-SA's attribution and
share-alike requirements) still apply to what's kept here. If images come
from a CC-BY-SA source, keep a note of which ones and their attribution
somewhere in this folder (e.g. a `CREDITS.md` here) so it doesn't get lost.

## Sizing

The Glossary displays each diagram at 88x88px (`.glossary-diagram` in
`base.html`), `object-fit: contain`. Source images don't need to be
square or that exact size -- anything roughly square and legible at
thumbnail size works; oversized files just mean slower page loads for no
visual benefit, so a scaled-down copy (a few hundred px per side) is
plenty.
