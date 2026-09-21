#!/usr/bin/env python3
"""Standalone entry point for the Flask web interface.

Usage:
    python web_main.py --add-user             # create (or reset) an account
    python web_main.py --list-users           # list accounts
    python web_main.py --remove-user <name>   # remove an account (keeps its data)
    python web_main.py --migrate-legacy-data <name>   # move pre-multi-user data into <name>'s account
    python web_main.py                        # run the server (default 127.0.0.1:5050)
"""

import argparse
import getpass
import sys

from workout_generator import migrate, users, web_server


def _add_user() -> None:
    username = input("Username (2-32 chars, lowercase letters/numbers/-/_): ").strip()
    display_name = input("Display name (optional, shown instead of the username -- Enter to skip): ").strip()
    password = getpass.getpass("Password: ")
    if not password:
        print("Password cannot be blank.", file=sys.stderr)
        sys.exit(1)
    confirm = getpass.getpass("Confirm: ")
    if password != confirm:
        print("Passwords didn't match.", file=sys.stderr)
        sys.exit(1)
    try:
        users.add_user(username, password, display_name)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    print(f"Account '{users.normalize_username(username)}' is ready.")


def _list_users() -> None:
    accounts = users.list_users()
    if not accounts:
        print("No accounts yet. Create one with: python web_main.py --add-user")
        return
    for account in accounts:
        print(f"{account['username']} ({account['display_name']})")


def _remove_user(username: str) -> None:
    removed = users.remove_user(username)
    if not removed:
        print(f"No account named '{username}'.", file=sys.stderr)
        sys.exit(1)
    print(f"Removed account '{users.normalize_username(username)}'. Their data on disk was left alone.")


def _migrate_legacy_data(username: str) -> None:
    try:
        summary = migrate.migrate_legacy_data(username)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    print(f"Moved the old shared history.json into '{users.normalize_username(username)}'s account.")
    if summary["moved_backups"]:
        print("Moved its backups/ folder too.")
    if summary["moved_output_files"]:
        print(f"Moved {summary['moved_output_files']} generated week-*.md file(s) too.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the workout generator's web interface.")
    parser.add_argument(
        "--host", default="127.0.0.1",
        help="Interface to bind to (default: 127.0.0.1 -- use a tool like tailscale serve "
             "rather than binding 0.0.0.0 directly if you want it reachable from other devices).",
    )
    parser.add_argument(
        "--port", type=int, default=web_server.DEFAULT_PORT,
        help=f"Port to listen on (default: {web_server.DEFAULT_PORT}).",
    )
    parser.add_argument(
        "--add-user", action="store_true",
        help="Create (or reset the password on) an account interactively, then exit.",
    )
    parser.add_argument(
        "--list-users", action="store_true",
        help="List existing accounts, then exit.",
    )
    parser.add_argument(
        "--remove-user", metavar="USERNAME", default=None,
        help="Remove an account (its data on disk is kept), then exit.",
    )
    parser.add_argument(
        "--migrate-legacy-data", metavar="USERNAME", default=None,
        help="One-time: move the old shared data/history.json (from before accounts existed) "
             "into USERNAME's own account, then exit. Run this once, pointed at yourself, after "
             "upgrading a pre-existing install -- see docs/user_guide.md.",
    )
    args = parser.parse_args()

    if args.add_user:
        _add_user()
        return
    if args.list_users:
        _list_users()
        return
    if args.remove_user:
        _remove_user(args.remove_user)
        return
    if args.migrate_legacy_data:
        _migrate_legacy_data(args.migrate_legacy_data)
        return

    if not users.has_any_users():
        print(
            "No accounts yet. Create one first with:\n\n"
            "    python web_main.py --add-user\n",
            file=sys.stderr,
        )
        sys.exit(1)

    app = web_server.create_app()
    print(f"Workout Generator web interface running at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
