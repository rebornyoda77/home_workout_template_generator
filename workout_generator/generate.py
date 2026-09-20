"""Shared "generate a week and persist it" logic used by both the CLI
(main.py) and the Flask web interface, so the two never drift apart.
"""

import random
from pathlib import Path

from .formatter import week_to_markdown
from .history import DEFAULT_HISTORY_PATH, History
from .week_builder import build_week

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def generate_week(
    num_days: int,
    *,
    history_path: Path = DEFAULT_HISTORY_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    avoid_weeks: int = 2,
    seed: int = None,
    save: bool = True,
):
    """Builds a week, renders it to Markdown, and (unless save=False) writes
    the history file and a Markdown file to disk. Returns (week, markdown,
    output_path); output_path is None when save=False."""
    rng = random.Random(seed)
    history = History.load(history_path)
    week = build_week(num_days, history, rng=rng, avoid_weeks=avoid_weeks)
    markdown = week_to_markdown(week)

    output_path = None
    if save:
        history.save(history_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"week-{week['week_index']:02d}-{week['generated_at']}.md"
        output_path.write_text(markdown, encoding="utf-8")

    return week, markdown, output_path
