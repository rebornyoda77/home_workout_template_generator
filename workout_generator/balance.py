"""Aggregates History.use_count by movement pattern -- how many times each
pattern has appeared across every generated week, lifetime. Shared by the
web Balance page and the CLI `balance` subcommand so the two never drift
apart, the same way generate.py is shared for build/rate/copy/etc.
"""

from . import exercises as ex_pool
from .day_builder import EVERY_DAY_PATTERNS


def pattern_rows(history) -> list:
    """One dict per movement pattern, in Glossary/day-template order:
    key, label, count (lifetime use_count summed across that pattern's
    exercises), every_day (see day_builder.EVERY_DAY_PATTERNS), and pct
    (0-100, this pattern's count relative to the busiest one -- 0 if
    nothing has been generated yet)."""
    rows = []
    for pattern in ex_pool.ALL_PATTERNS:
        count = sum(history.use_count.get(e.name, 0) for e in ex_pool.by_pattern(pattern))
        rows.append({
            "key": pattern,
            "label": ex_pool.PATTERN_LABELS[pattern],
            "count": count,
            "every_day": pattern in EVERY_DAY_PATTERNS,
        })
    max_count = max((r["count"] for r in rows), default=0)
    for r in rows:
        r["pct"] = round(r["count"] / max_count * 100, 1) if max_count else 0
    return rows


def push_pull_totals(rows) -> tuple:
    """(push_total, pull_total) -- Horizontal + Vertical push vs. pull,
    the single clearest balance signal in this pattern set."""
    push_total = sum(r["count"] for r in rows if r["key"] in (ex_pool.PUSH_H, ex_pool.PUSH_V))
    pull_total = sum(r["count"] for r in rows if r["key"] in (ex_pool.PULL_H, ex_pool.PULL_V))
    return push_total, pull_total
