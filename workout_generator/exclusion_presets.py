"""Named, per-user presets of movement patterns to exclude from a
generated week -- e.g. a "sore shoulder" preset that always benches
Vertical Push. Saves re-checking the same boxes on the generate/regenerate
forms every time: pick the preset from a dropdown there instead. Same
plain-JSON storage style as history.py/users.py, one file per user (see
user_paths.user_presets_path).
"""

import json
from pathlib import Path

from . import exercises as ex_pool


def _load(path: Path) -> list:
    path = Path(path)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _save(presets: list, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(presets, indent=2) + "\n", encoding="utf-8")


def list_presets(path: Path) -> list:
    """[{"name": ..., "patterns": [...]}, ...], sorted by name (case-insensitive)."""
    return sorted(_load(path), key=lambda p: p["name"].lower())


def save_preset(name: str, patterns, path: Path) -> None:
    """Creates a new preset, or overwrites an existing one with the same
    name (case-insensitive) -- same reset-by-resubmission convention as
    users.add_user."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Preset name cannot be blank.")
    patterns = sorted({p for p in patterns if p in ex_pool.ALL_PATTERNS})
    presets = [p for p in _load(path) if p["name"].lower() != name.lower()]
    presets.append({"name": name, "patterns": patterns})
    _save(presets, path)


def delete_preset(name: str, path: Path) -> bool:
    """Returns True if a preset with that name (case-insensitive) existed."""
    name = (name or "").strip().lower()
    presets = _load(path)
    remaining = [p for p in presets if p["name"].lower() != name]
    if len(remaining) == len(presets):
        return False
    _save(remaining, path)
    return True
