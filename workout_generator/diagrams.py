"""Resolves an exercise's how-to diagram, if one exists yet, from a plain
image file in static/diagrams/ -- see that folder's README for naming
convention and where to source images. Deliberately not a field on
Exercise (exercises.py): most exercises have no diagram yet, and this way
dropping a correctly-named file in is enough to make it appear, with
nothing in exercises.py to keep in sync as diagrams get added over time.
"""

import re
from pathlib import Path

DIAGRAMS_DIR = Path(__file__).resolve().parent / "static" / "diagrams"

# Checked in this order -- an SVG (if ever hand-drawn/traced) wins over a
# raster fallback for the same exercise.
DIAGRAM_EXTENSIONS = (".svg", ".png", ".webp", ".jpg", ".jpeg", ".gif")


def diagram_slug(exercise_name: str) -> str:
    """The filename (minus extension) a diagram for this exercise is
    expected under, e.g. "Goblet Squat" -> "goblet-squat"."""
    slug = re.sub(r"[^a-z0-9]+", "-", exercise_name.strip().lower())
    return slug.strip("-")


def diagram_filename(exercise_name: str, diagrams_dir: Path = DIAGRAMS_DIR) -> str:
    """This exercise's diagram filename within static/diagrams/ (e.g.
    "goblet-squat.png"), or "" if no diagram exists for it yet. Checks disk
    directly rather than a separate manifest, so adding or removing a file
    takes effect on the very next request."""
    slug = diagram_slug(exercise_name)
    for ext in DIAGRAM_EXTENSIONS:
        if (diagrams_dir / f"{slug}{ext}").is_file():
            return f"{slug}{ext}"
    return ""
