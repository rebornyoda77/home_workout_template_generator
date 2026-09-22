"""Household-wide workout summary -- one row per account, side by side, so
anyone sharing the install can see how everyone's doing at a glance without
switching logins. Built from each account's own History the same way the
CLI's --user flag already reads it, just for every account at once. Shared
by the web Family page and the CLI `family` subcommand, the same way
balance.py is shared for the Balance page/`balance` subcommand.
"""

from datetime import date

from . import users
from .history import History
from .user_paths import DEFAULT_DATA_ROOT, user_history_path


def household_rows(users_path=None, data_root=DEFAULT_DATA_ROOT, today: date = None) -> list:
    """One dict per account -- username, display_name, completed_this_week
    (see History.completed_days_this_week), current_streak, longest_streak,
    total_active_days -- sorted by this week's completions (most first),
    then display name. Empty list if no accounts exist yet."""
    if users_path is None:
        users_path = users.DEFAULT_USERS_PATH
    rows = []
    for account in users.list_users(users_path):
        history = History.load(user_history_path(account["username"], data_root))
        stats = history.streaks(today=today)
        rows.append({
            "username": account["username"],
            "display_name": account["display_name"],
            "completed_this_week": history.completed_days_this_week(today=today),
            "current_streak": stats["current_streak"],
            "longest_streak": stats["longest_streak"],
            "total_active_days": stats["total_active_days"],
        })
    rows.sort(key=lambda r: (-r["completed_this_week"], r["display_name"].lower()))
    return rows
