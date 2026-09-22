"""Flattens a History into CSV rows -- one row per exercise instance across
every generated week -- for opening in a spreadsheet. Read-only: this never
touches history.json, it just reformats what's already there.
"""

import csv
import io

CSV_FIELDNAMES = [
    "week_index", "generated_at", "deload", "week_rating",
    "day_number", "day_title", "day_completed", "day_completed_at", "day_notes",
    "block_title", "block_type", "block_structure",
    "exercise_name", "load_hint", "weight", "actual", "feel",
]


def history_rows(history) -> list:
    """One dict per exercise instance, in week/day/block/exercise order --
    the same order the week itself is generated and displayed in."""
    rows = []
    for week in history.weeks:
        for day_number, day in enumerate(week["days"], start=1):
            for block in day["blocks"]:
                for exercise in block["exercises"]:
                    rows.append({
                        "week_index": week["week_index"],
                        "generated_at": week["generated_at"],
                        "deload": "yes" if week.get("deload") else "no",
                        "week_rating": week.get("rating") or "",
                        "day_number": day_number,
                        "day_title": day["title"],
                        "day_completed": "yes" if day.get("completed") else "no",
                        "day_completed_at": day.get("completed_at", ""),
                        "day_notes": day.get("notes", ""),
                        "block_title": block["title"],
                        "block_type": block["type"],
                        "block_structure": block["structure"],
                        "exercise_name": exercise["name"],
                        "load_hint": exercise.get("load_hint", ""),
                        "weight": exercise.get("weight", ""),
                        "actual": exercise.get("actual", ""),
                        "feel": exercise.get("feel", ""),
                    })
    return rows


def history_to_csv(history) -> str:
    """The full CSV text (header + one row per exercise instance), ready to
    write to a file or stream as a download. Empty history still produces
    just the header row, so the output always opens cleanly in a
    spreadsheet."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDNAMES)
    writer.writeheader()
    writer.writerows(history_rows(history))
    return buf.getvalue()
