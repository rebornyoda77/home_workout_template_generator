"""Tracks which exercises were used in past generated weeks.

The generator consults this history to avoid repeating the same exercise
(or the same movement-pattern pairing) too often from one week to the next.
History is persisted as plain JSON so it survives between runs.
"""

import json
import math
from datetime import date
from pathlib import Path

from . import exercises as ex_pool


DEFAULT_HISTORY_PATH = Path(__file__).resolve().parent.parent / "data" / "history.json"


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

    def record_week(self, generated_at: str, days, week_index: int = None, deload: bool = False) -> None:
        """`days` is the full serialized day list (see week_builder.serialize_day):
        each entry has a title and its blocks (with exercises), not just a title,
        so a past week can be redisplayed later without being regenerated.

        `week_index` defaults to the counter's current value (the normal,
        brand-new-week path). regenerate_week passes an explicit value to
        overwrite a specific past week's slot instead of appending a new one
        -- record_day's staleness stamps still use the live counter (see
        `staleness`/`used_within`) so a regenerated week's picks are treated
        as freshly used *now*, not backdated to whichever slot they land in.

        `deload` just records whether week_builder built this as a lighter
        recovery week (see week_builder.is_deload_week) -- purely
        informational here, for display; it doesn't change any History
        behavior. A week loaded from before this field existed simply has
        no "deload" key, which templates treat as falsy.
        """
        stored_index = self.week_index if week_index is None else week_index
        self.weeks.append(
            {
                "week_index": stored_index,
                "generated_at": generated_at,
                "deload": bool(deload),
                "days": list(days),
            }
        )
        self.weeks.sort(key=lambda w: w["week_index"])
        self.week_index = max(self.week_index, stored_index)

    def week_by_index(self, week_index: int):
        return next((w for w in self.weeks if w["week_index"] == week_index), None)

    def rate_week(self, week_index: int, rating) -> bool:
        """Sets (or, with rating=None, clears) a week's 1-5 star rating --
        how it actually felt to train, as opposed to the per-exercise
        "feel" logged on individual sets. Returns True if the week existed.
        See week_builder._template_bias for how this feeds back into
        which day templates get favored in future weeks."""
        if rating is not None and rating not in (1, 2, 3, 4, 5):
            raise ValueError("rating must be 1-5 or None")
        week = self.week_by_index(week_index)
        if week is None:
            return False
        week["rating"] = rating
        return True

    def template_average_ratings(self) -> dict:
        """Maps each day-template title to the average rating (1-5) across
        every rated week that included a day using that title. A title with
        no rated weeks behind it is left out entirely -- callers should
        treat a missing title as neutral rather than as a rating of 0."""
        totals = {}
        counts = {}
        for week in self.weeks:
            rating = week.get("rating")
            if rating is None:
                continue
            for title in {day["title"] for day in week["days"]}:
                totals[title] = totals.get(title, 0) + rating
                counts[title] = counts.get(title, 0) + 1
        return {title: totals[title] / counts[title] for title in totals}

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
                        name = ex_pool.exercise_name(exercise)
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

    def update_day_log(
        self,
        week_index: int,
        day_index: int,
        *,
        completed: bool = None,
        notes: str = None,
        exercise_logs: dict = None,
    ) -> bool:
        """Records what actually happened on one day of a generated week:
        whether it was completed, free-text notes, and per-exercise "actual"
        (what was really used, e.g. "20 lb x10") + "feel" (easy/right/hard).
        `exercise_logs` can also carry a "load_hint" -- unlike actual/feel
        (a log of what happened that session), this edits the *prescribed*
        load stored on this week's own copy of the exercise, e.g. so a week
        copied from someone else's history (see generate.copy_week) can be
        retargeted to different weights/reps without touching the shared
        exercise pool or the account it was copied from.
        Any argument left as None is left unchanged. `exercise_logs` maps
        (block_index, exercise_index) -> {"actual": str, "feel": str,
        "load_hint": str}. Returns True if the week/day existed and was
        updated."""
        week = self.week_by_index(week_index)
        if week is None or not (0 <= day_index < len(week["days"])):
            return False

        day = week["days"][day_index]
        if completed is not None:
            if completed and not day.get("completed"):
                # Stamped only on the False->True transition, so re-saving
                # notes on an already-completed day doesn't shift its date.
                day["completed_at"] = date.today().isoformat()
            elif not completed:
                day["completed_at"] = ""
            day["completed"] = completed
        if notes is not None:
            day["notes"] = notes
        for (block_index, exercise_index), log in (exercise_logs or {}).items():
            if not (0 <= block_index < len(day["blocks"])):
                continue
            exercises = day["blocks"][block_index]["exercises"]
            if not (0 <= exercise_index < len(exercises)):
                continue
            exercise = exercises[exercise_index]
            if "actual" in log:
                exercise["actual"] = log["actual"]
            if "feel" in log:
                exercise["feel"] = log["feel"]
            if "load_hint" in log:
                exercise["load_hint"] = log["load_hint"]
        return True

    def completed_dates(self) -> list:
        """Sorted list of distinct calendar dates (ISO strings) on which at
        least one day was logged as completed. A day only gets a
        completed_at stamp on the False->True transition (see
        update_day_log), so this reflects when workouts actually happened,
        not when they were generated or scheduled."""
        dates = {
            day["completed_at"]
            for week in self.weeks
            for day in week["days"]
            if day.get("completed_at")
        }
        return sorted(dates)

    def streaks(self, today: date = None) -> dict:
        """Day-streak stats derived from completed_at dates:
        - current_streak: consecutive calendar days with a completed
          workout, ending at the most recent completed date -- treated as
          still "current" (not yet broken) if that date is today or
          yesterday, so it doesn't drop to 0 just because today's workout
          hasn't been logged yet.
        - longest_streak: the best such run ever recorded.
        - total_active_days: distinct days with at least one completed
          workout, lifetime.
        """
        today = today or date.today()
        dates = [date.fromisoformat(d) for d in self.completed_dates()]
        if not dates:
            return {"current_streak": 0, "longest_streak": 0, "total_active_days": 0}

        longest = run = 1
        for prev, curr in zip(dates, dates[1:]):
            run = run + 1 if (curr - prev).days == 1 else 1
            longest = max(longest, run)

        current = 0
        if (today - dates[-1]).days <= 1:
            current = 1
            for prev, curr in zip(reversed(dates[:-1]), reversed(dates[1:])):
                if (curr - prev).days == 1:
                    current += 1
                else:
                    break

        return {"current_streak": current, "longest_streak": longest, "total_active_days": len(dates)}

    def last_log(self, exercise_name: str) -> dict:
        """The most recent *logged* occurrence of this exercise -- one with
        actual/feel actually filled in, not just scheduled -- most recent
        week first. Returns None if it's never been logged. Used to surface
        "last time" progression hints the next time this exercise comes up."""
        for week in sorted(self.weeks, key=lambda w: w["week_index"], reverse=True):
            for day in week["days"]:
                for block in day["blocks"]:
                    for exercise in block["exercises"]:
                        if exercise.get("name") != exercise_name:
                            continue
                        actual = exercise.get("actual", "")
                        feel = exercise.get("feel", "")
                        if actual or feel:
                            return {"week_index": week["week_index"], "actual": actual, "feel": feel}
        return None
