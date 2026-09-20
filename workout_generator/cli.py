import argparse
import random
import sys
from pathlib import Path

from .formatter import week_to_markdown
from .history import DEFAULT_HISTORY_PATH, History
from .week_builder import build_week

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Generate a weekly home workout template (OTF-style blocks).",
    )
    parser.add_argument(
        "--days", type=int, default=4, choices=(3, 4),
        help="Number of workout days to generate this week (default: 4).",
    )
    parser.add_argument(
        "--avoid-weeks", type=int, default=2,
        help="Try not to repeat an exercise used within this many past weeks (default: 2).",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed, for reproducible output (mainly for testing).",
    )
    parser.add_argument(
        "--history-file", type=Path, default=DEFAULT_HISTORY_PATH,
        help=f"Path to the history JSON file (default: {DEFAULT_HISTORY_PATH}).",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to write the generated Markdown file to (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the plan without saving history or writing a file.",
    )
    return parser


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    rng = random.Random(args.seed)

    history = History.load(args.history_file)
    week = build_week(args.days, history, rng=rng, avoid_weeks=args.avoid_weeks)
    markdown = week_to_markdown(week)

    print(markdown)

    if not args.dry_run:
        history.save(args.history_file)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        out_path = args.output_dir / f"week-{week['week_index']:02d}-{week['generated_at']}.md"
        out_path.write_text(markdown, encoding="utf-8")
        print(f"Saved to {out_path}", file=sys.stderr)
        print(f"History updated at {args.history_file}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
