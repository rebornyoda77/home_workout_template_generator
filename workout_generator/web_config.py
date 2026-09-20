"""Stores the web interface's single passcode (hashed) in a small local
JSON file -- same single-passcode-gate model as the budget tool's web
interface, sized down for a single-user tool (no per-user accounts).
"""

import json
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "web_config.json"


def _load(path: Path = DEFAULT_CONFIG_PATH) -> dict:
    path = Path(path)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save(data: dict, path: Path = DEFAULT_CONFIG_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def has_web_passcode(path: Path = DEFAULT_CONFIG_PATH) -> bool:
    return bool(_load(path).get("passcode_hash"))


def set_web_passcode(passcode: str, path: Path = DEFAULT_CONFIG_PATH) -> None:
    data = _load(path)
    data["passcode_hash"] = generate_password_hash(passcode)
    _save(data, path)


def verify_web_passcode(passcode: str, path: Path = DEFAULT_CONFIG_PATH) -> bool:
    stored = _load(path).get("passcode_hash")
    if not stored:
        return False
    return check_password_hash(stored, passcode)
