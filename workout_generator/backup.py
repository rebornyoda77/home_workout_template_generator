"""Local backups of data/history.json -- the only state that makes the
"don't repeat too often" logic work, so losing it silently would quietly
degrade variety with no error. Mirrors budget_tool's backup.py, sized down:
plain file copies, no compression/encryption, kept alongside the history
file itself.
"""

from datetime import datetime, timezone
from pathlib import Path

DEFAULT_KEEP = 20


def backup_history(history_path: Path, backups_dir: Path = None, keep: int = DEFAULT_KEEP) -> Path:
    """Copies history_path into backups_dir with a timestamped name, unless
    it's byte-identical to the most recent existing backup (no point
    snapshotting a no-op run). Prunes down to the `keep` most recent
    backups afterward. Returns the new backup's path, or None if nothing
    was written (history_path doesn't exist yet, or content is unchanged)."""
    history_path = Path(history_path)
    if not history_path.exists():
        return None

    backups_dir = Path(backups_dir) if backups_dir else history_path.parent / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    content = history_path.read_bytes()

    existing = sorted(backups_dir.glob(f"{history_path.stem}_*.json"))
    if existing and existing[-1].read_bytes() == content:
        return None

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    backup_path = backups_dir / f"{history_path.stem}_{timestamp}.json"
    backup_path.write_bytes(content)

    all_backups = sorted(backups_dir.glob(f"{history_path.stem}_*.json"))
    for stale in all_backups[:-keep]:
        stale.unlink()

    return backup_path
