import argparse
import sys
from pathlib import Path

from . import exercises as ex_pool
from .generate import (
    DEFAULT_OUTPUT_DIR, delete_week, find_exclusion_violations, generate_week,
    regenerate_week, resolve_excluded_names,
)
from .history import DEFAULT_HISTORY_PATH, History

COMMANDS = ("generate", "list", "delete", "regenerate")


def _common_paths(parser):
    parser.add_argument(
        "--history-file", type=Path, default=DEFAULT_HISTORY_PATH,
        help=f"Path to the history JSON file (default: {DEFAULT_HISTORY_PATH}).",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
        help=f"Directory holding generated Markdown files (default: {DEFAULT_OUTPUT_DIR}).",
    )


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
    _common_paths(regenerate_parser)

    return parser


def _normalize_argv(argv):
    """Lets `generate`'s flags be used with no subcommand at all, for
    backward compatibility with the original flat CLI (`main.py --days 3`)."""
    if not argv or (argv[0] not in COMMANDS and argv[0] not in ("-h", "--help")):
        return ["generate", *argv]
    return list(argv)


def _cmd_generate(args) -> int:
    week, markdown, out_path = generate_week(
        args.days,
        history_path=args.history_file,
        output_dir=args.output_dir,
        avoid_weeks=args.avoid_weeks,
        seed=args.seed,
        save=not args.dry_run,
        excluded_exercises=args.exclude_exercise,
        excluded_patterns=args.exclude_pattern,
    )
    print(markdown)
    _warn_exclusion_violations(args, week)
    if out_path is not None:
        print(f"Saved to {out_path}", file=sys.stderr)
        print(f"History updated at {args.history_file}", file=sys.stderr)
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
    history = History.load(args.history_file)
    if not history.weeks:
        print("No weeks generated yet.")
        return 0
    for week in history.weeks:
        titles = ", ".join(day["title"] for day in week["days"])
        print(f"Week {week['week_index']} ({week['generated_at']}, {len(week['days'])} days): {titles}")
    return 0


def _cmd_delete(args) -> int:
    removed = delete_week(args.week, history_path=args.history_file, output_dir=args.output_dir)
    if not removed:
        print(f"Week {args.week} doesn't exist.", file=sys.stderr)
        return 1
    print(f"Deleted week {args.week}.")
    return 0


def _cmd_regenerate(args) -> int:
    result = regenerate_week(
        args.week,
        history_path=args.history_file,
        output_dir=args.output_dir,
        num_days=args.days,
        avoid_weeks=args.avoid_weeks,
        seed=args.seed,
        save=not args.dry_run,
        excluded_exercises=args.exclude_exercise,
        excluded_patterns=args.exclude_pattern,
    )
    if result is None:
        print(f"Week {args.week} doesn't exist -- nothing to regenerate.", file=sys.stderr)
        return 1

    week, markdown, out_path = result
    print(markdown)
    _warn_exclusion_violations(args, week)
    if out_path is not None:
        print(f"Saved to {out_path}", file=sys.stderr)
        print(f"History updated at {args.history_file}", file=sys.stderr)
    return 0


_HANDLERS = {
    "generate": _cmd_generate,
    "list": _cmd_list,
    "delete": _cmd_delete,
    "regenerate": _cmd_regenerate,
}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    args = build_arg_parser().parse_args(_normalize_argv(argv))
    return _HANDLERS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
