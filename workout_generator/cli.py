import argparse
import sys
from pathlib import Path

from . import exercises as ex_pool
from . import user_paths
from . import users
from .backup import DEFAULT_KEEP
from .balance import pattern_rows, push_pull_totals
from .export import history_to_csv
from .family import household_rows
from .generate import (
    DEFAULT_OUTPUT_DIR, copy_week, delete_week, find_exclusion_violations, generate_week,
    log_day, rate_week, regenerate_week, resolve_excluded_names,
)
from .history import DEFAULT_HISTORY_PATH, DEFAULT_STALE_DAYS, History
from .week_builder import DELOAD_INTERVAL_WEEKS

COMMANDS = (
    "generate", "list", "delete", "regenerate", "backups", "rate", "streaks", "copy", "export",
    "log", "balance", "family",
)


def _common_paths(parser):
    parser.add_argument(
        "--history-file", type=Path, default=None,
        help=f"Path to the history JSON file (default: {DEFAULT_HISTORY_PATH}, or that "
             "user's own file if --user is given).",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=None,
        help=f"Directory holding generated Markdown files (default: {DEFAULT_OUTPUT_DIR}, or "
             "that user's own folder if --user is given).",
    )
    parser.add_argument(
        "--user", default=None, metavar="USERNAME",
        help="Operate on this person's own data instead of the shared default path -- see "
             "docs/user_guide.md. Ignored if --history-file/--output-dir are also given.",
    )


def _resolve_history_file(args, data_root: Path = user_paths.DEFAULT_DATA_ROOT) -> Path:
    if args.history_file is not None:
        return args.history_file
    if getattr(args, "user", None):
        return user_paths.user_history_path(args.user, data_root=data_root)
    return DEFAULT_HISTORY_PATH


def _resolve_output_dir(args, output_root: Path = user_paths.DEFAULT_OUTPUT_ROOT) -> Path:
    if getattr(args, "output_dir", None) is not None:
        return args.output_dir
    if getattr(args, "user", None):
        return user_paths.user_output_dir(args.user, output_root=output_root)
    return DEFAULT_OUTPUT_DIR


def _exclusion_args(parser):
    parser.add_argument(
        "--exclude-exercise", action="append", default=[], metavar="NAME",
        choices=sorted(e.name for e in ex_pool.EXERCISES),
        help="Exclude a specific exercise from this week (repeatable). E.g. sore shoulder -> "
             '--exclude-exercise "Shoulder Press Half-Kneeling".',
    )
    parser.add_argument(
        "--exclude-pattern", action="append", default=[], metavar="PATTERN",
        choices=ex_pool.ALL_PATTERNS,
        help="Exclude a whole movement pattern from this week (repeatable). Choices: "
             + ", ".join(ex_pool.ALL_PATTERNS),
    )


def _deload_args(parser):
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--deload", action="store_true",
        help="Force this week to be a lighter deload/recovery week, regardless of the "
             f"automatic every-{DELOAD_INTERVAL_WEEKS}-weeks schedule.",
    )
    group.add_argument(
        "--no-deload", action="store_true",
        help="Force this week to be a normal week, even if it would auto-trigger a deload week.",
    )


def _resolve_deload(args):
    if args.deload:
        return True
    if args.no_deload:
        return False
    return None


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Generate, list, delete, or regenerate weekly home workout templates.",
    )
    sub = parser.add_subparsers(dest="command")

    generate_parser = sub.add_parser("generate", help="Generate the next week (default command).")
    generate_parser.add_argument(
        "--days", type=int, default=4, choices=(3, 4),
        help="Number of workout days to generate this week (default: 4).",
    )
    generate_parser.add_argument(
        "--avoid-weeks", type=int, default=2,
        help="Try not to repeat an exercise used within this many past weeks (default: 2).",
    )
    generate_parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed, for reproducible output (mainly for testing).",
    )
    generate_parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the plan without saving history or writing a file.",
    )
    _exclusion_args(generate_parser)
    _deload_args(generate_parser)
    _common_paths(generate_parser)

    list_parser = sub.add_parser("list", help="List every generated week.")
    _common_paths(list_parser)

    delete_parser = sub.add_parser("delete", help="Delete a previously generated week.")
    delete_parser.add_argument("--week", type=int, required=True, help="Week number to delete.")
    _common_paths(delete_parser)

    regenerate_parser = sub.add_parser("regenerate", help="Reroll a week's exercises in place.")
    regenerate_parser.add_argument("--week", type=int, required=True, help="Week number to regenerate.")
    regenerate_parser.add_argument(
        "--days", type=int, default=None, choices=(3, 4),
        help="Number of workout days (default: keep that week's original count).",
    )
    regenerate_parser.add_argument(
        "--avoid-weeks", type=int, default=2,
        help="Try not to repeat an exercise used within this many past weeks (default: 2).",
    )
    regenerate_parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed, for reproducible output (mainly for testing).",
    )
    regenerate_parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the plan without saving history or writing a file.",
    )
    _exclusion_args(regenerate_parser)
    _deload_args(regenerate_parser)
    _common_paths(regenerate_parser)

    rate_parser = sub.add_parser("rate", help="Rate (or clear the rating on) a past week.")
    rate_parser.add_argument("--week", type=int, required=True, help="Week number to rate.")
    rate_group = rate_parser.add_mutually_exclusive_group(required=True)
    rate_group.add_argument("--stars", type=int, choices=(1, 2, 3, 4, 5), help="Rating, 1-5.")
    rate_group.add_argument("--clear", action="store_true", help="Clear that week's rating.")
    _common_paths(rate_parser)

    streaks_parser = sub.add_parser("streaks", help="Show current/longest day-completion streaks.")
    _common_paths(streaks_parser)

    copy_parser = sub.add_parser("copy", help="Copy a generated week's full plan into another person's history.")
    copy_parser.add_argument("--week", type=int, required=True, help="Week number to copy (from the source).")
    copy_parser.add_argument(
        "--to", required=True, metavar="USERNAME",
        help="Account to copy this week's plan into, as a brand-new week in their own sequence.",
    )
    _common_paths(copy_parser)

    export_parser = sub.add_parser("export", help="Export full history as CSV (one row per exercise).")
    export_parser.add_argument(
        "--out", type=Path, default=None,
        help="Write the CSV to this file instead of printing it to stdout.",
    )
    _common_paths(export_parser)

    log_parser = sub.add_parser("log", help="Log a day: mark it complete and/or add notes.")
    log_parser.add_argument("--week", type=int, required=True, help="Week number.")
    log_parser.add_argument("--day", type=int, required=True, help="Day number within that week (1-based).")
    log_complete_group = log_parser.add_mutually_exclusive_group()
    log_complete_group.add_argument("--complete", action="store_true", help="Mark this day complete.")
    log_complete_group.add_argument("--incomplete", action="store_true", help="Mark this day not complete.")
    log_parser.add_argument("--notes", default=None, help="Replace this day's notes.")
    _common_paths(log_parser)

    balance_parser = sub.add_parser("balance", help="Show movement-pattern usage counts (lifetime).")
    _common_paths(balance_parser)

    family_parser = sub.add_parser(
        "family", help="Show a household summary: every account's this-week completions and streaks, side by side.",
    )
    family_parser.add_argument(
        "--users-file", type=Path, default=None,
        help=f"Path to the accounts JSON file (default: {users.DEFAULT_USERS_PATH}).",
    )
    family_parser.add_argument(
        "--data-dir", type=Path, default=None,
        help=f"Root directory holding each account's own history.json (default: {user_paths.DEFAULT_DATA_ROOT}).",
    )

    backups_parser = sub.add_parser("backups", help="List history.json backup snapshots.")
    backups_parser.add_argument(
        "--history-file", type=Path, default=None,
        help=f"Path to the history JSON file (default: {DEFAULT_HISTORY_PATH}, or that "
             "user's own file if --user is given).",
    )
    backups_parser.add_argument(
        "--user", default=None, metavar="USERNAME",
        help="Operate on this person's own data instead of the shared default path.",
    )

    return parser


def _normalize_argv(argv):
    """Lets `generate`'s flags be used with no subcommand at all, for
    backward compatibility with the original flat CLI (`main.py --days 3`)."""
    if not argv or (argv[0] not in COMMANDS and argv[0] not in ("-h", "--help")):
        return ["generate", *argv]
    return list(argv)


def _cmd_generate(args) -> int:
    history_file = _resolve_history_file(args)
    week, markdown, out_path = generate_week(
        args.days,
        history_path=history_file,
        output_dir=_resolve_output_dir(args),
        avoid_weeks=args.avoid_weeks,
        seed=args.seed,
        save=not args.dry_run,
        excluded_exercises=args.exclude_exercise,
        excluded_patterns=args.exclude_pattern,
        deload=_resolve_deload(args),
    )
    print(markdown)
    _warn_exclusion_violations(args, week)
    if out_path is not None:
        print(f"Saved to {out_path}", file=sys.stderr)
        print(f"History updated at {history_file}", file=sys.stderr)
    return 0


def _warn_exclusion_violations(args, week: dict) -> None:
    excluded_names = resolve_excluded_names(args.exclude_exercise, args.exclude_pattern)
    violations = find_exclusion_violations(week, excluded_names)
    if violations:
        print(
            "Warning: couldn't fully honor your exclusions -- some blocks have no "
            f"substitute exercise: {', '.join(violations)}",
            file=sys.stderr,
        )


def _cmd_list(args) -> int:
    history = History.load(_resolve_history_file(args))
    if not history.weeks:
        print("No weeks generated yet.")
        return 0
    for week in history.weeks:
        titles = ", ".join(day["title"] for day in week["days"])
        rating = week.get("rating")
        rating_suffix = f", {'*' * rating} rated" if rating else ""
        deload_suffix = ", deload week" if week.get("deload") else ""
        print(
            f"Week {week['week_index']} ({week['generated_at']}, {len(week['days'])} days"
            f"{rating_suffix}{deload_suffix}): {titles}"
        )
    return 0


def _cmd_delete(args) -> int:
    removed = delete_week(args.week, history_path=_resolve_history_file(args), output_dir=_resolve_output_dir(args))
    if not removed:
        print(f"Week {args.week} doesn't exist.", file=sys.stderr)
        return 1
    print(f"Deleted week {args.week}.")
    return 0


def _cmd_regenerate(args) -> int:
    history_file = _resolve_history_file(args)
    result = regenerate_week(
        args.week,
        history_path=history_file,
        output_dir=_resolve_output_dir(args),
        num_days=args.days,
        avoid_weeks=args.avoid_weeks,
        seed=args.seed,
        save=not args.dry_run,
        excluded_exercises=args.exclude_exercise,
        excluded_patterns=args.exclude_pattern,
        deload=_resolve_deload(args),
    )
    if result is None:
        print(f"Week {args.week} doesn't exist -- nothing to regenerate.", file=sys.stderr)
        return 1

    week, markdown, out_path = result
    print(markdown)
    _warn_exclusion_violations(args, week)
    if out_path is not None:
        print(f"Saved to {out_path}", file=sys.stderr)
        print(f"History updated at {history_file}", file=sys.stderr)
    return 0


def _cmd_rate(args) -> int:
    rating = None if args.clear else args.stars
    updated = rate_week(args.week, rating, history_path=_resolve_history_file(args))
    if not updated:
        print(f"Week {args.week} doesn't exist.", file=sys.stderr)
        return 1
    print(f"Cleared week {args.week}'s rating." if rating is None else f"Rated week {args.week}: {rating} stars.")
    return 0


def _cmd_streaks(args) -> int:
    history = History.load(_resolve_history_file(args))
    stats = history.streaks()
    print(f"Current streak: {stats['current_streak']} day(s)")
    print(f"Longest streak: {stats['longest_streak']} day(s)")
    print(f"Total workouts logged: {stats['total_active_days']}")

    stale_days = history.days_since_last_week_generated()
    if stale_days is not None and stale_days >= DEFAULT_STALE_DAYS:
        print(f"It's been {stale_days} days since you generated a new week -- ready for the next one?")
    return 0


def _cmd_copy(args) -> int:
    if getattr(args, "user", None) and users.normalize_username(args.user) == users.normalize_username(args.to):
        print("--to must be a different account than --user.", file=sys.stderr)
        return 1

    result = copy_week(
        args.week,
        source_history_path=_resolve_history_file(args),
        target_history_path=user_paths.user_history_path(args.to),
        target_output_dir=user_paths.user_output_dir(args.to),
    )
    if result is None:
        print(f"Week {args.week} doesn't exist.", file=sys.stderr)
        return 1

    week, markdown, out_path = result
    print(markdown)
    print(f"Copied to {args.to}'s history as their Week {week['week_index']}.", file=sys.stderr)
    if out_path is not None:
        print(f"Saved to {out_path}", file=sys.stderr)
    return 0


def _cmd_export(args) -> int:
    history = History.load(_resolve_history_file(args))
    csv_text = history_to_csv(history)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(csv_text, encoding="utf-8")
        print(f"Exported {len(history.weeks)} week(s) to {args.out}", file=sys.stderr)
    else:
        print(csv_text, end="")
    return 0


def _cmd_log(args) -> int:
    if not args.complete and not args.incomplete and args.notes is None:
        print("Nothing to log -- pass --complete/--incomplete and/or --notes.", file=sys.stderr)
        return 1

    completed = True if args.complete else (False if args.incomplete else None)
    updated = log_day(
        args.week, args.day - 1,
        history_path=_resolve_history_file(args),
        completed=completed, notes=args.notes,
    )
    if not updated:
        print(f"Week {args.week}, day {args.day} doesn't exist.", file=sys.stderr)
        return 1
    print(f"Logged Week {args.week}, Day {args.day}.")
    return 0


def _cmd_balance(args) -> int:
    history = History.load(_resolve_history_file(args))
    rows = pattern_rows(history)
    if not any(r["count"] for r in rows):
        print("No weeks generated yet.")
        return 0

    push_total, pull_total = push_pull_totals(rows)
    print(f"Push: {push_total}   Pull: {pull_total}")
    print()

    max_count = max(r["count"] for r in rows)
    bar_width = 30
    for r in rows:
        filled = round((r["count"] / max_count) * bar_width) if max_count else 0
        bar = "#" * filled + "-" * (bar_width - filled)
        tag = " (every day)" if r["every_day"] else ""
        print(f"{r['label']:<38} {bar} {r['count']}{tag}")
    return 0


def _cmd_family(args) -> int:
    users_path = args.users_file or users.DEFAULT_USERS_PATH
    data_root = args.data_dir or user_paths.DEFAULT_DATA_ROOT
    rows = household_rows(users_path, data_root)
    if not rows:
        print("No accounts yet -- see 'python web_main.py --add-user'.")
        return 0

    print(f"{'Name':<22} {'This week':<11} {'Current':<9} {'Longest':<9} {'Total':<7}")
    for r in rows:
        print(
            f"{r['display_name']:<22} {r['completed_this_week']:<11} "
            f"{r['current_streak']:<9} {r['longest_streak']:<9} {r['total_active_days']:<7}"
        )
    return 0


def _cmd_backups(args) -> int:
    history_path = Path(_resolve_history_file(args))
    backups_dir = history_path.parent / "backups"
    files = sorted(backups_dir.glob(f"{history_path.stem}_*.json")) if backups_dir.exists() else []
    if not files:
        print("No backups yet -- one is taken automatically each time history.json changes "
              f"(keeping the most recent {DEFAULT_KEEP}).")
        return 0
    for f in files:
        print(f"{f.name} ({f.stat().st_size} bytes)")
    return 0


_HANDLERS = {
    "generate": _cmd_generate,
    "list": _cmd_list,
    "delete": _cmd_delete,
    "regenerate": _cmd_regenerate,
    "rate": _cmd_rate,
    "streaks": _cmd_streaks,
    "copy": _cmd_copy,
    "export": _cmd_export,
    "log": _cmd_log,
    "balance": _cmd_balance,
    "family": _cmd_family,
    "backups": _cmd_backups,
}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    args = build_arg_parser().parse_args(_normalize_argv(argv))
    return _HANDLERS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
