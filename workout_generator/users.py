"""Stores the web interface's user accounts (hashed passwords) in a small
local JSON file -- replaces the old single shared passcode (web_config.py)
now that different people in the household each want their own login and
their own separate workout history. Same plain-JSON, hash-based storage
style as history.py/web_config.py: no database, hand-editable if needed.
"""

import json
import re
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

DEFAULT_USERS_PATH = Path(__file__).resolve().parent.parent / "data" / "users.json"

# lowercase letters/digits/-/_ only, so a username is always safe to use
# as a filesystem directory name in user_paths.py.
_USERNAME_RE = re.compile(r"^[a-z0-9_-]{2,32}$")


def normalize_username(username: str) -> str:
    return (username or "").strip().lower()


def is_valid_username(username: str) -> bool:
    return bool(_USERNAME_RE.match(username))


def _load(path: Path = DEFAULT_USERS_PATH) -> dict:
    path = Path(path)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save(data: dict, path: Path = DEFAULT_USERS_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def list_users(path: Path = DEFAULT_USERS_PATH) -> list:
    """[{"username": ..., "display_name": ...}, ...], sorted by username --
    enough for a login-page picker without exposing password hashes."""
    data = _load(path)
    return [
        {"username": username, "display_name": entry.get("display_name") or username}
        for username, entry in sorted(data.items())
    ]


def has_any_users(path: Path = DEFAULT_USERS_PATH) -> bool:
    return bool(_load(path))


def user_exists(username: str, path: Path = DEFAULT_USERS_PATH) -> bool:
    return normalize_username(username) in _load(path)


def display_name_for(username: str, path: Path = DEFAULT_USERS_PATH) -> str:
    entry = _load(path).get(normalize_username(username), {})
    return entry.get("display_name") or username


def add_user(username: str, password: str, display_name: str = "", path: Path = DEFAULT_USERS_PATH) -> None:
    """Creates a new account, or resets an existing one's password/display
    name if that username is already taken (matches how --set-passcode used
    to just overwrite the single passcode)."""
    username = normalize_username(username)
    if not is_valid_username(username):
        raise ValueError(
            "Usernames must be 2-32 characters: lowercase letters, numbers, - or _ only."
        )
    if not password:
        raise ValueError("Password cannot be blank.")
    data = _load(path)
    data[username] = {
        "password_hash": generate_password_hash(password),
        "display_name": (display_name or username).strip() or username,
    }
    _save(data, path)


def remove_user(username: str, path: Path = DEFAULT_USERS_PATH) -> bool:
    """Removes an account (not its data -- see user_paths.py/migrate.py;
    that's left on disk in case it was removed by mistake). Returns True if
    that username existed."""
    username = normalize_username(username)
    data = _load(path)
    if username not in data:
        return False
    del data[username]
    _save(data, path)
    return True


def verify_user(username: str, password: str, path: Path = DEFAULT_USERS_PATH) -> bool:
    entry = _load(path).get(normalize_username(username))
    if not entry:
        return False
    return check_password_hash(entry["password_hash"], password)
