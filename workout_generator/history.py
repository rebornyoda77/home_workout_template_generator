"""Tracks which exercises were used in past generated weeks.

The generator consults this history to avoid repeating the same exercise
(or the same movement-pattern pairing) too often from one week to the next.
History is persisted as plain JSON so it survives between runs.
"""

import json
import math
from pathlib import Path


DEFAULT_HISTORY_PATH = Path(__file__).resolve().parent.parent / "data" / "history.json"


def _exercise_name(exercise) -> str:
    return exercise["name"] if isinstance(exercise, dict) else exercise.name


class History:
    def __init__(self, data=None):
        data = data or {}
        # exercise name -> week_index it was last used in
        self.last_used = dict(data.get("last_used", {}))
        # exercise name -> total number of times it has been used
        self.use_count = dict(data.get("use_count", {}))
        # log of past generated weeks, most recent last
        self.weeks = list(data.get("weeks", []))
        # Always derived from self.weeks (never trusted from the file as its
        # own field) so deleting a week self-heals the counter instead of
        # needing separate bookkeeping to stay in sync.
        self.week_index = self._max_week_index()

    def _max_week_index(self) -> int:
        return max((w["week_index"] for w in self.weeks), default=0)

    @classmethod
    def load(cls, path: Path = DEFAULT_HISTORY_PATH) -> "History":
        path = Path(path)
        if not path.exists():
            return cls()
        with path.open("r", encoding="utf-8") as f:
            return cls(json.load(f))

    def save(self, path: Path = DEFAULT_HISTORY_PATH) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "week_index": self.week_index,
                    "last_used": self.last_used,
                    "use_count": self.use_count,
                    "weeks": self.weeks,
                },
                f,
                indent=2,
            )
            f.write("\n")

    def staleness(self, exercise_name: str) -> float:
        """Higher = has gone longer without being used (or never used)."""
        last = self.last_used.get(exercise_name)
        if last is None:
            return math.inf
        return self.week_index - last

    def used_within(self, exercise_name: str, weeks: int) -> bool:
        last = self.last_used.get(exercise_name)
        if last is None:
            return False
        return (self.week_index - last) <= weeks

    def begin_week(self) -> int:
        """Advance and return the index for the week about to be generated."""
        self.week_index += 1
        return self.week_index

    def record_day(self, day_title: str, exercise_names) -> None:
        for name in exercise_names:
            self.last_used[name] = self.week_index
            self.use_count[name] = self.use_count.get(name, 0) + 1

    def record_week(self, generated_at: str, days, week_index: int = None) -> None:
        """`days` is the full serialized day list (see week_builder.serialize_day):
        each entry has a title and its blocks (with exercises), not just a title,
        so a past week can be redisplayed later without being regenerated.

        `week_index` defaults to the counter's current value (the normal,
        brand-new-week path). regenerate_week passes an explicit value to
        overwrite a specific past week's slot instead of appending a new one
        -- record_day's staleness stamps still use the live counter (see
        `staleness`/`used_within`) so a regenerated week's picks are treated
        as freshly used *now*, not backdated to whichever slot they land in.
        """
        stored_index = self.week_index if week_index is None else week_index
        self.weeks.append(
            {
                "week_index": stored_index,
                "generated_at": generated_at,
                "days": list(days),
            }
        )
        self.weeks.sort(key=lambda w: w["week_index"])
        self.week_index = max(self.week_index, stored_index)

    def week_by_index(self, week_index: int):
        return next((w for w in self.weeks if w["week_index"] == week_index), None)

    def _recompute_aggregates(self) -> None:
        """Rebuilds last_used/use_count from scratch by replaying self.weeks
        in week_index order -- used after deleting a week, since last_used
        can't just be decremented (another week may have used the same
        exercise more recently anyway)."""
        self.last_used = {}
        self.use_count = {}
        for week in sorted(self.weeks, key=lambda w: w["week_index"]):
            wi = week["week_index"]
            for day in week["days"]:
                for block in day["blocks"]:
                    for exercise in block["exercises"]:
                        name = _exercise_name(exercise)
                        self.last_used[name] = wi
                        self.use_count[name] = self.use_count.get(name, 0) + 1

    def delete_week(self, week_index: int) -> bool:
        """Removes a generated week and recomputes exercise-use aggregates
        from what's left. Returns True if a week was actually removed."""
        before = len(self.weeks)
        self.weeks = [w for w in self.weeks if w["week_index"] != week_index]
        removed = len(self.weeks) < before
        if removed:
            self._recompute_aggregates()
            self.week_index = self._max_week_index()
        return removed
