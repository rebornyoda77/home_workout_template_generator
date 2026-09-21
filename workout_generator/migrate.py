"""One-time migration of the app's original single-shared-history data
(from before per-user profiles existed) into one named user's own folder.

Deliberately explicit rather than automatic: this always requires the
owner to say *which* account inherits the old data, so it can never
silently land in the wrong family member's history just because of
whichever order accounts happened to get created in. See
docs/user_guide.md's upgrade instructions.
"""

import shutil
from pathlib import Path

from .history import DEFAULT_HISTORY_PATH
from .user_paths import DEFAULT_DATA_ROOT, DEFAULT_OUTPUT_ROOT, user_history_path, user_output_dir


def migrate_legacy_data(
    username: str,
    *,
    legacy_history_path: Path = DEFAULT_HISTORY_PATH,
    legacy_output_dir: Path = DEFAULT_OUTPUT_ROOT,
    data_root: Path = DEFAULT_DATA_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> dict:
    """Moves the pre-multi-user data/history.json (and its backups/ and any
    flat output/week-*.md files) into `username`'s own folder. Raises
    ValueError if there's no legacy history to migrate, or if that user
    already has history of their own (never overwrites existing data).
    Returns a summary dict of what was moved."""
    legacy_history_path = Path(legacy_history_path)
    if not legacy_history_path.exists():
        raise ValueError(f"No legacy history found at {legacy_history_path} -- nothing to migrate.")

    new_history_path = user_history_path(username, data_root)
    if new_history_path.exists():
        raise ValueError(
            f"{username} already has their own history at {new_history_path} -- "
            "refusing to overwrite it. Move or remove that file first if you really want to replace it."
        )

    new_history_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(legacy_history_path), str(new_history_path))
    summary = {"moved_history": True, "moved_backups": False, "moved_output_files": 0}

    legacy_backups_dir = legacy_history_path.parent / "backups"
    new_backups_dir = new_history_path.parent / "backups"
    if legacy_backups_dir.exists() and not new_backups_dir.exists():
        shutil.move(str(legacy_backups_dir), str(new_backups_dir))
        summary["moved_backups"] = True

    legacy_output_dir = Path(legacy_output_dir)
    output_files = sorted(legacy_output_dir.glob("week-*.md")) if legacy_output_dir.exists() else []
    if output_files:
        new_output_dir = user_output_dir(username, output_root)
        new_output_dir.mkdir(parents=True, exist_ok=True)
        for f in output_files:
            destination = new_output_dir / f.name
            if not destination.exists():
                shutil.move(str(f), str(destination))
                summary["moved_output_files"] += 1

    return summary
