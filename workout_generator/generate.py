"""Shared "generate/regenerate/delete a week and persist it" logic used by
both the CLI (main.py) and the Flask web interface, so the two never drift
apart.
"""

import random
from pathlib import Path

from .formatter import week_to_markdown
from .history import DEFAULT_HISTORY_PATH, History
from .week_builder import build_week
from .week_builder import regenerate_week as _regenerate_week_core

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def _remove_output_files(output_dir: Path, week_index: int) -> None:
    output_dir = Path(output_dir)
    if not output_dir.exists():
        return
    for f in output_dir.glob(f"week-{week_index:02d}-*.md"):
        f.unlink()


def generate_week(
    num_days: int,
    *,
    history_path: Path = DEFAULT_HISTORY_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    avoid_weeks: int = 2,
    seed: int = None,
    save: bool = True,
):
    """Builds a new week, renders it to Markdown, and (unless save=False)
    writes the history file and a Markdown file to disk. Returns (week,
    markdown, output_path); output_path is None when save=False."""
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


def delete_week(
    week_index: int,
    *,
    history_path: Path = DEFAULT_HISTORY_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> bool:
    """Removes a previously generated week from history, along with its
    saved Markdown file (if any). Returns True if a week was actually
    removed, False if that week_index didn't exist."""
    history = History.load(history_path)
    removed = history.delete_week(week_index)
    if removed:
        history.save(history_path)
        _remove_output_files(output_dir, week_index)
    return removed


def regenerate_week(
    week_index: int,
    *,
    history_path: Path = DEFAULT_HISTORY_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    num_days: int = None,
    avoid_weeks: int = 2,
    seed: int = None,
    save: bool = True,
):
    """Rerolls a specific week's content in place, keeping its week_index
    (so it stays in the same spot in history/the web UI) but replacing its
    exercises and getting a fresh generated_at date. `num_days` defaults to
    that week's original day count. Returns (week, markdown, output_path),
    or None if that week hasn't been generated yet. output_path is None
    when save=False."""
    rng = random.Random(seed)
    history = History.load(history_path)
    existing = history.week_by_index(week_index)
    if existing is None:
        return None

    if num_days is None:
        num_days = len(existing["days"])

    week = _regenerate_week_core(week_index, num_days, history, rng=rng, avoid_weeks=avoid_weeks)
    markdown = week_to_markdown(week)

    output_path = None
    if save:
        _remove_output_files(output_dir, week_index)
        history.save(history_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"week-{week['week_index']:02d}-{week['generated_at']}.md"
        output_path.write_text(markdown, encoding="utf-8")

    return week, markdown, output_path
