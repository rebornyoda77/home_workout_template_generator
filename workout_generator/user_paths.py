"""Resolves where a given user's own history/output/backups live, now that
each person tracks their workouts separately (see users.py for accounts).
Each user gets a self-contained slice of the existing data/output layout:

    data/users/<username>/history.json
    data/users/<username>/backups/       (backup.py derives this from
                                           history_path's own parent, so it
                                           falls out for free)
    output/<username>/week-NN-*.md
"""

from pathlib import Path

from .users import normalize_username

DEFAULT_DATA_ROOT = Path(__file__).resolve().parent.parent / "data"
DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parent.parent / "output"


def user_history_path(username: str, data_root: Path = DEFAULT_DATA_ROOT) -> Path:
    return Path(data_root) / "users" / normalize_username(username) / "history.json"


def user_output_dir(username: str, output_root: Path = DEFAULT_OUTPUT_ROOT) -> Path:
    return Path(output_root) / normalize_username(username)
