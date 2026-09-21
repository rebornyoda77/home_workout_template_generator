import argparse
import io
import json
import random
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path

from workout_generator import blocks, exercises as ex_pool, migrate, progression, user_paths, users
from workout_generator import cli as cli_module
from workout_generator import generate as generate_module
from workout_generator.backup import backup_history
from workout_generator.cli import main as cli_main
from workout_generator.day_builder import DAY_TEMPLATES, exercise_names
from workout_generator.history import History
from workout_generator import week_builder as week_builder_module
from workout_generator.week_builder import build_week, regenerate_week

ALLOWED_EQUIPMENT = {"kettlebell", "dumbbell", "band", "bench", "treadmill", "bag", "mat"}


class ExercisePoolTests(unittest.TestCase):
    def test_all_equipment_is_available_at_home(self):
        for exercise in ex_pool.EXERCISES:
            unexpected = set(exercise.equipment) - ALLOWED_EQUIPMENT
            self.assertFalse(
                unexpected,
                f"{exercise.name} uses unavailable equipment: {unexpected}",
            )

    def test_every_pattern_used_by_a_day_template_has_exercises(self):
        used_patterns = {ex_pool.BAG}  # every day gets a bag finisher, not part of any template dict
        for template in DAY_TEMPLATES:
            used_patterns.update(template["block_a_patterns"])
            used_patterns.update(template["block_b_patterns"])
            used_patterns.update(template["buyout_1_patterns"])
            used_patterns.update(template["buyout_2_patterns"])
            used_patterns.add(template["drop_set_pattern"])
            used_patterns.update(template["core_finisher_patterns"])
        for pattern in used_patterns:
            self.assertTrue(ex_pool.by_pattern(pattern), f"No exercises for pattern {pattern}")

    def test_every_exercise_has_a_glossary_description(self):
        for exercise in ex_pool.EXERCISES:
            self.assertTrue(
                exercise.description and exercise.description.strip(),
                f"{exercise.name} has no glossary description",
            )

    def test_every_pattern_has_a_glossary_label(self):
        for pattern in ex_pool.ALL_PATTERNS:
            self.assertIn(pattern, ex_pool.PATTERN_LABELS)


class HistoryTests(unittest.TestCase):
    def test_unused_exercise_is_maximally_stale(self):
        history = History()
        history.begin_week()
        self.assertEqual(history.staleness("Goblet Squat"), float("inf"))

    def test_used_within_reflects_recent_weeks(self):
        history = History()
        history.begin_week()  # week 1
        history.record_day("Day", ["Goblet Squat"])
        history.begin_week()  # week 2
        self.assertTrue(history.used_within("Goblet Squat", weeks=2))
        history.begin_week()  # week 3
        self.assertFalse(history.used_within("Goblet Squat", weeks=1))
        self.assertTrue(history.used_within("Goblet Squat", weeks=2))

    def test_save_and_load_round_trip(self):
        history = History()
        history.begin_week()
        history.record_day("Day 1", ["Goblet Squat", "Push-Up"])
        history.record_week("2026-09-20", ["Day 1"])

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "history_test.json"
            history.save(tmp_path)
            reloaded = History.load(tmp_path)

        self.assertEqual(reloaded.week_index, history.week_index)
        self.assertEqual(reloaded.last_used, history.last_used)
        self.assertEqual(reloaded.use_count, history.use_count)
        self.assertEqual(reloaded.weeks, history.weeks)

    def test_delete_week_removes_entry_and_recomputes_aggregates(self):
        history = History()
        build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")  # week 1
        build_week(4, history, rng=random.Random(2), generated_at="2026-09-13")  # week 2

        self.assertTrue(history.delete_week(1))
        self.assertIsNone(history.week_by_index(1))
        self.assertIsNotNone(history.week_by_index(2))
        # nothing should still claim to have last been used in week 1
        self.assertNotIn(1, history.last_used.values())

    def test_delete_week_returns_false_for_unknown_index(self):
        history = History()
        self.assertFalse(history.delete_week(999))

    def test_deleting_latest_week_frees_its_index(self):
        history = History()
        build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")  # week 1
        build_week(4, history, rng=random.Random(2), generated_at="2026-09-13")  # week 2
        self.assertEqual(history.week_index, 2)

        history.delete_week(2)
        self.assertEqual(history.week_index, 1)

    def test_deleting_a_middle_week_does_not_shrink_the_counter(self):
        history = History()
        build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")  # week 1
        build_week(4, history, rng=random.Random(2), generated_at="2026-09-13")  # week 2
        build_week(4, history, rng=random.Random(3), generated_at="2026-09-20")  # week 3

        history.delete_week(2)
        self.assertEqual(history.week_index, 3)
        self.assertEqual([w["week_index"] for w in history.weeks], [1, 3])

    def test_new_weeks_seed_default_log_fields(self):
        history = History()
        week = build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")
        stored = history.week_by_index(week["week_index"])

        for day in stored["days"]:
            self.assertEqual(day["completed"], False)
            self.assertEqual(day["notes"], "")
            for block in day["blocks"]:
                for exercise in block["exercises"]:
                    self.assertEqual(exercise["actual"], "")
                    self.assertEqual(exercise["feel"], "")

    def test_update_day_log_sets_completed_and_notes(self):
        history = History()
        build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")

        updated = history.update_day_log(1, 0, completed=True, notes="felt great")
        self.assertTrue(updated)

        day = history.week_by_index(1)["days"][0]
        self.assertTrue(day["completed"])
        self.assertEqual(day["notes"], "felt great")

    def test_update_day_log_sets_per_exercise_actual_and_feel(self):
        history = History()
        build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")

        updated = history.update_day_log(1, 0, exercise_logs={(0, 0): {"actual": "20 lb x10", "feel": "easy"}})
        self.assertTrue(updated)

        exercise = history.week_by_index(1)["days"][0]["blocks"][0]["exercises"][0]
        self.assertEqual(exercise["actual"], "20 lb x10")
        self.assertEqual(exercise["feel"], "easy")

    def test_update_day_log_leaves_unspecified_fields_untouched(self):
        history = History()
        build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")

        history.update_day_log(1, 0, completed=True, notes="first pass")
        history.update_day_log(1, 0, exercise_logs={(0, 0): {"actual": "25 lb x8"}})

        day = history.week_by_index(1)["days"][0]
        self.assertTrue(day["completed"])  # still set from the first call
        self.assertEqual(day["notes"], "first pass")
        self.assertEqual(day["blocks"][0]["exercises"][0]["actual"], "25 lb x8")

    def test_update_day_log_returns_false_for_unknown_week_or_day(self):
        history = History()
        build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")

        self.assertFalse(history.update_day_log(999, 0, completed=True))
        self.assertFalse(history.update_day_log(1, 999, completed=True))

    def test_update_day_log_ignores_out_of_range_exercise_indices(self):
        history = History()
        build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")

        # must not raise -- an out-of-range block/exercise index is just skipped
        updated = history.update_day_log(1, 0, exercise_logs={(999, 0): {"actual": "x"}, (0, 999): {"actual": "y"}})
        self.assertTrue(updated)  # the call itself still succeeds (week/day existed)

    def test_update_day_log_stamps_completed_at_on_first_completion(self):
        history = History()
        build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")

        history.update_day_log(1, 0, completed=True)
        day = history.week_by_index(1)["days"][0]
        self.assertEqual(day["completed_at"], date.today().isoformat())

    def test_update_day_log_does_not_restamp_completed_at_on_resave(self):
        history = History()
        build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")

        history.update_day_log(1, 0, completed=True)
        history.week_by_index(1)["days"][0]["completed_at"] = "2020-01-01"  # simulate an older completion
        history.update_day_log(1, 0, completed=True, notes="still done")  # re-saving shouldn't move the date
        self.assertEqual(history.week_by_index(1)["days"][0]["completed_at"], "2020-01-01")

    def test_update_day_log_clears_completed_at_when_uncompleted(self):
        history = History()
        build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")

        history.update_day_log(1, 0, completed=True)
        history.update_day_log(1, 0, completed=False)
        self.assertEqual(history.week_by_index(1)["days"][0]["completed_at"], "")

    def test_completed_dates_returns_sorted_unique_dates(self):
        history = History()
        build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")

        history.update_day_log(1, 0, completed=True)
        history.week_by_index(1)["days"][0]["completed_at"] = "2026-09-10"
        history.update_day_log(1, 1, completed=True)
        history.week_by_index(1)["days"][1]["completed_at"] = "2026-09-08"

        self.assertEqual(history.completed_dates(), ["2026-09-08", "2026-09-10"])

    def test_streaks_on_empty_history(self):
        history = History()
        self.assertEqual(
            history.streaks(), {"current_streak": 0, "longest_streak": 0, "total_active_days": 0}
        )

    def test_streaks_current_streak_counts_consecutive_days_ending_today(self):
        history = History()
        build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")
        days = history.week_by_index(1)["days"]

        for day_index, completed_at in enumerate(["2026-09-18", "2026-09-19", "2026-09-20"]):
            history.update_day_log(1, day_index, completed=True)
            days[day_index]["completed_at"] = completed_at

        stats = history.streaks(today=date(2026, 9, 20))
        self.assertEqual(stats["current_streak"], 3)
        self.assertEqual(stats["longest_streak"], 3)
        self.assertEqual(stats["total_active_days"], 3)

    def test_streaks_current_streak_survives_a_one_day_gap_from_today(self):
        history = History()
        build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")

        history.update_day_log(1, 0, completed=True)
        history.week_by_index(1)["days"][0]["completed_at"] = "2026-09-19"

        # yesterday's workout is logged, today's isn't yet -- still current
        stats = history.streaks(today=date(2026, 9, 20))
        self.assertEqual(stats["current_streak"], 1)

    def test_streaks_current_streak_resets_after_a_missed_day(self):
        history = History()
        build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")

        history.update_day_log(1, 0, completed=True)
        history.week_by_index(1)["days"][0]["completed_at"] = "2026-09-17"

        stats = history.streaks(today=date(2026, 9, 20))  # 3 days ago -- streak broken
        self.assertEqual(stats["current_streak"], 0)
        self.assertEqual(stats["longest_streak"], 1)

    def test_streaks_longest_streak_tracks_best_historical_run_even_after_it_breaks(self):
        history = History()
        build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")
        days = history.week_by_index(1)["days"]

        dates = ["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-10"]
        for day_index, completed_at in enumerate(dates):
            history.update_day_log(1, day_index, completed=True)
            days[day_index]["completed_at"] = completed_at

        stats = history.streaks(today=date(2026, 9, 20))
        self.assertEqual(stats["longest_streak"], 3)
        self.assertEqual(stats["current_streak"], 0)
        self.assertEqual(stats["total_active_days"], 4)

    def test_last_log_returns_none_when_never_logged(self):
        history = History()
        build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")
        self.assertIsNone(history.last_log("Goblet Squat"))

    def test_last_log_finds_a_logged_occurrence(self):
        history = History()
        build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")

        name = history.weeks[0]["days"][0]["blocks"][0]["exercises"][0]["name"]
        history.update_day_log(1, 0, exercise_logs={(0, 0): {"actual": "20 lb x10", "feel": "easy"}})

        result = history.last_log(name)
        self.assertIsNotNone(result)
        self.assertEqual(result["actual"], "20 lb x10")
        self.assertEqual(result["feel"], "easy")
        self.assertEqual(result["week_index"], 1)

    def test_last_log_prefers_the_most_recent_week(self):
        history = History()
        build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")  # week 1
        build_week(4, history, rng=random.Random(2), generated_at="2026-09-13")  # week 2

        name = history.weeks[0]["days"][0]["blocks"][0]["exercises"][0]["name"]
        history.update_day_log(1, 0, exercise_logs={(0, 0): {"actual": "old log", "feel": "hard"}})

        # only log it in week 2 if that same exercise happens to appear there;
        # otherwise just confirm week 1's log is still the one returned
        found_in_week_2 = False
        for di, day in enumerate(history.weeks[1]["days"]):
            for bi, block in enumerate(day["blocks"]):
                for ei, exercise in enumerate(block["exercises"]):
                    if exercise["name"] == name:
                        history.update_day_log(2, di, exercise_logs={(bi, ei): {"actual": "new log", "feel": "easy"}})
                        found_in_week_2 = True

        result = history.last_log(name)
        if found_in_week_2:
            self.assertEqual(result["actual"], "new log")
            self.assertEqual(result["week_index"], 2)
        else:
            self.assertEqual(result["actual"], "old log")
            self.assertEqual(result["week_index"], 1)

    def test_last_log_ignores_scheduling_without_a_log(self):
        history = History()
        build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")  # week 1
        build_week(4, history, rng=random.Random(1), generated_at="2026-09-13")  # week 2, same seed

        name = history.weeks[0]["days"][0]["blocks"][0]["exercises"][0]["name"]
        # log it only in week 1; week 2 (however it re-picks exercises) is never logged
        history.update_day_log(1, 0, exercise_logs={(0, 0): {"actual": "logged here", "feel": "right"}})

        result = history.last_log(name)
        self.assertIsNotNone(result)
        self.assertEqual(result["week_index"], 1)  # not silently overridden by an unlogged week 2

    def test_rate_week_sets_and_clears_rating(self):
        history = History()
        build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")

        self.assertTrue(history.rate_week(1, 4))
        self.assertEqual(history.week_by_index(1)["rating"], 4)

        self.assertTrue(history.rate_week(1, None))
        self.assertIsNone(history.week_by_index(1)["rating"])

    def test_rate_week_rejects_out_of_range_rating(self):
        history = History()
        build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")
        with self.assertRaises(ValueError):
            history.rate_week(1, 0)
        with self.assertRaises(ValueError):
            history.rate_week(1, 6)

    def test_rate_week_returns_false_for_unknown_week(self):
        history = History()
        self.assertFalse(history.rate_week(999, 5))

    def test_template_average_ratings_ignores_unrated_weeks(self):
        history = History()
        build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")  # week 1, unrated
        self.assertEqual(history.template_average_ratings(), {})

    def test_template_average_ratings_averages_across_rated_weeks(self):
        history = History()
        week1 = build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")
        week2 = build_week(4, history, rng=random.Random(2), generated_at="2026-09-13")
        history.rate_week(week1["week_index"], 5)
        history.rate_week(week2["week_index"], 3)

        # both weeks used all 4 templates (4-day weeks), so every title
        # averages the two ratings together
        averages = history.template_average_ratings()
        self.assertEqual(set(averages), {t["title"] for t in DAY_TEMPLATES})
        for avg in averages.values():
            self.assertAlmostEqual(avg, 4.0)


class ProgressionTests(unittest.TestCase):
    def test_suggestion_for_none_is_empty(self):
        self.assertEqual(progression.suggestion_for(None), "")
        self.assertEqual(progression.suggestion_for({}), "")

    def test_suggestion_for_includes_actual_and_feel(self):
        text = progression.suggestion_for({"actual": "20 lb x10", "feel": "easy"})
        self.assertIn("20 lb x10", text)
        self.assertIn("heavier", text)

    def test_suggestion_for_actual_only(self):
        text = progression.suggestion_for({"actual": "20 lb x10", "feel": ""})
        self.assertIn("20 lb x10", text)
        self.assertNotIn("--", text.replace('"20 lb x10"', ""))  # no dangling separator with nothing after it

    def test_suggestion_for_unknown_feel_value_is_ignored(self):
        text = progression.suggestion_for({"actual": "20 lb x10", "feel": "sideways"})
        self.assertIn("20 lb x10", text)
        self.assertNotIn("sideways", text)


class BackupTests(unittest.TestCase):
    def test_no_backup_when_history_file_does_not_exist_yet(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            self.assertIsNone(backup_history(history_path))
            self.assertFalse((Path(tmp_dir) / "backups").exists())

    def test_backup_creates_a_timestamped_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            history_path.write_text('{"a": 1}', encoding="utf-8")

            backup_path = backup_history(history_path)
            self.assertIsNotNone(backup_path)
            self.assertTrue(backup_path.exists())
            self.assertEqual(backup_path.read_text(encoding="utf-8"), '{"a": 1}')
            self.assertEqual(backup_path.parent, Path(tmp_dir) / "backups")

    def test_backup_skips_when_content_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            history_path.write_text('{"a": 1}', encoding="utf-8")

            first = backup_history(history_path)
            second = backup_history(history_path)  # nothing changed
            self.assertIsNotNone(first)
            self.assertIsNone(second)

            backups_dir = Path(tmp_dir) / "backups"
            self.assertEqual(len(list(backups_dir.glob("*.json"))), 1)

    def test_backup_snapshots_again_once_content_changes(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            history_path.write_text('{"a": 1}', encoding="utf-8")
            backup_history(history_path)

            history_path.write_text('{"a": 2}', encoding="utf-8")
            second = backup_history(history_path)
            self.assertIsNotNone(second)

            backups_dir = Path(tmp_dir) / "backups"
            self.assertEqual(len(list(backups_dir.glob("*.json"))), 2)

    def test_backup_prunes_to_the_keep_limit(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            backups_dir = Path(tmp_dir) / "backups"

            for i in range(6):
                history_path.write_text(f'{{"a": {i}}}', encoding="utf-8")
                backup_history(history_path, keep=3)

            remaining = sorted(backups_dir.glob("*.json"))
            self.assertEqual(len(remaining), 3)
            # the survivors should be the 3 most recently written
            contents = [f.read_text(encoding="utf-8") for f in remaining]
            self.assertEqual(contents, ['{"a": 3}', '{"a": 4}', '{"a": 5}'])


class UsersTests(unittest.TestCase):
    def _path(self, tmp_dir):
        return Path(tmp_dir) / "users.json"

    def test_add_and_verify_user(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._path(tmp_dir)
            users.add_user("Dad", "hunter2", "Dad", path=path)
            self.assertTrue(users.verify_user("dad", "hunter2", path=path))  # case-insensitive username
            self.assertTrue(users.verify_user("Dad", "hunter2", path=path))
            self.assertFalse(users.verify_user("dad", "wrong", path=path))

    def test_verify_unknown_user_returns_false(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.assertFalse(users.verify_user("nobody", "x", path=self._path(tmp_dir)))

    def test_add_user_rejects_invalid_username(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._path(tmp_dir)
            with self.assertRaises(ValueError):
                users.add_user("D", "hunter2", path=path)  # too short
            with self.assertRaises(ValueError):
                users.add_user("has spaces", "hunter2", path=path)
            with self.assertRaises(ValueError):
                users.add_user("Dad!", "hunter2", path=path)

    def test_add_user_rejects_blank_password(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(ValueError):
                users.add_user("dad", "", path=self._path(tmp_dir))

    def test_add_user_overwrites_existing_account(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._path(tmp_dir)
            users.add_user("dad", "old-pass", path=path)
            users.add_user("dad", "new-pass", path=path)
            self.assertFalse(users.verify_user("dad", "old-pass", path=path))
            self.assertTrue(users.verify_user("dad", "new-pass", path=path))

    def test_list_users_sorted_with_display_names(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._path(tmp_dir)
            users.add_user("mom", "pw1", "Mom", path=path)
            users.add_user("dad", "pw2", "Dad", path=path)
            self.assertEqual(
                users.list_users(path=path),
                [{"username": "dad", "display_name": "Dad"}, {"username": "mom", "display_name": "Mom"}],
            )

    def test_list_users_defaults_display_name_to_username(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._path(tmp_dir)
            users.add_user("kiddo", "pw", path=path)
            self.assertEqual(users.list_users(path=path), [{"username": "kiddo", "display_name": "kiddo"}])

    def test_has_any_users(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._path(tmp_dir)
            self.assertFalse(users.has_any_users(path=path))
            users.add_user("dad", "pw", path=path)
            self.assertTrue(users.has_any_users(path=path))

    def test_user_exists(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._path(tmp_dir)
            users.add_user("dad", "pw", path=path)
            self.assertTrue(users.user_exists("Dad", path=path))
            self.assertFalse(users.user_exists("mom", path=path))

    def test_remove_user(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._path(tmp_dir)
            users.add_user("dad", "pw", path=path)
            self.assertTrue(users.remove_user("dad", path=path))
            self.assertFalse(users.user_exists("dad", path=path))
            self.assertFalse(users.remove_user("dad", path=path))  # already gone

    def test_display_name_for(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._path(tmp_dir)
            users.add_user("dad", "pw", "Dad", path=path)
            self.assertEqual(users.display_name_for("dad", path=path), "Dad")
            self.assertEqual(users.display_name_for("nobody", path=path), "nobody")

    def test_is_valid_username(self):
        self.assertTrue(users.is_valid_username("dad"))
        self.assertTrue(users.is_valid_username("kid_2"))
        self.assertFalse(users.is_valid_username("a"))
        self.assertFalse(users.is_valid_username("Has Caps And Spaces"))
        self.assertFalse(users.is_valid_username("x" * 33))


class UserPathsTests(unittest.TestCase):
    def test_user_history_path_is_namespaced_by_username(self):
        path = user_paths.user_history_path("Dad", data_root=Path("/tmp/data"))
        self.assertEqual(path, Path("/tmp/data/users/dad/history.json"))

    def test_user_output_dir_is_namespaced_by_username(self):
        path = user_paths.user_output_dir("Mom", output_root=Path("/tmp/output"))
        self.assertEqual(path, Path("/tmp/output/mom"))

    def test_different_users_get_different_paths(self):
        root = Path("/tmp/data")
        self.assertNotEqual(
            user_paths.user_history_path("dad", data_root=root),
            user_paths.user_history_path("mom", data_root=root),
        )


class MigrateTests(unittest.TestCase):
    def test_migrate_moves_history_backups_and_output(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            legacy_history = tmp_path / "history.json"
            legacy_history.write_text('{"weeks": []}', encoding="utf-8")
            (tmp_path / "backups").mkdir()
            (tmp_path / "backups" / "history_20260101.json").write_text("{}", encoding="utf-8")
            legacy_output = tmp_path / "output"
            legacy_output.mkdir()
            (legacy_output / "week-01-2026-01-01.md").write_text("# Week 1", encoding="utf-8")
            (legacy_output / "not-a-week-file.txt").write_text("ignore me", encoding="utf-8")

            data_root = tmp_path / "data"
            summary = migrate.migrate_legacy_data(
                "dad",
                legacy_history_path=legacy_history,
                legacy_output_dir=legacy_output,
                data_root=data_root,
                output_root=tmp_path / "new_output",
            )

            self.assertEqual(summary, {"moved_history": True, "moved_backups": True, "moved_output_files": 1})
            self.assertFalse(legacy_history.exists())
            new_history = user_paths.user_history_path("dad", data_root=data_root)
            self.assertTrue(new_history.exists())
            self.assertEqual(new_history.read_text(encoding="utf-8"), '{"weeks": []}')
            self.assertTrue((new_history.parent / "backups" / "history_20260101.json").exists())
            new_output_dir = user_paths.user_output_dir("dad", output_root=tmp_path / "new_output")
            self.assertTrue((new_output_dir / "week-01-2026-01-01.md").exists())
            # non-week files aren't part of the migration
            self.assertFalse((new_output_dir / "not-a-week-file.txt").exists())

    def test_migrate_raises_when_no_legacy_history_exists(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            with self.assertRaises(ValueError):
                migrate.migrate_legacy_data(
                    "dad",
                    legacy_history_path=tmp_path / "history.json",
                    data_root=tmp_path / "data",
                )

    def test_migrate_refuses_to_overwrite_existing_user_data(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            legacy_history = tmp_path / "history.json"
            legacy_history.write_text("{}", encoding="utf-8")

            data_root = tmp_path / "data"
            existing = user_paths.user_history_path("dad", data_root=data_root)
            existing.parent.mkdir(parents=True)
            existing.write_text('{"already": "here"}', encoding="utf-8")

            with self.assertRaises(ValueError):
                migrate.migrate_legacy_data("dad", legacy_history_path=legacy_history, data_root=data_root)
            # neither file should have been touched
            self.assertTrue(legacy_history.exists())
            self.assertEqual(existing.read_text(encoding="utf-8"), '{"already": "here"}')


class BlockSelectionTests(unittest.TestCase):
    def test_pick_exercise_avoids_recently_used_when_alternatives_exist(self):
        history = History()
        history.begin_week()  # week 1
        pool_names = [e.name for e in ex_pool.by_pattern(ex_pool.ARMS)]
        # Use every arm exercise except the last one in week 1.
        history.record_day("Day", pool_names[:-1])
        history.begin_week()  # week 2, generating now

        rng = random.Random(1)
        for _ in range(10):
            choice = blocks.pick_exercise(
                ex_pool.ARMS, history, used_this_week=set(), rng=rng, avoid_weeks=2,
            )
            self.assertEqual(choice.name, pool_names[-1])

    def test_used_this_week_is_never_reselected_while_alternatives_remain(self):
        history = History()
        history.begin_week()
        used_this_week = set()
        rng = random.Random(2)
        pool_size = len(ex_pool.by_pattern(ex_pool.CORE_FLEX))
        picks = [
            blocks.pick_exercise(ex_pool.CORE_FLEX, history, used_this_week, rng)
            for _ in range(pool_size)
        ]
        self.assertEqual(len({p.name for p in picks}), pool_size)

    def test_pick_exercise_avoids_excluded_names_when_alternatives_exist(self):
        history = History()
        history.begin_week()
        pool_names = [e.name for e in ex_pool.by_pattern(ex_pool.ARMS)]
        excluded = frozenset(pool_names[:-1])  # exclude every arm exercise but one

        rng = random.Random(4)
        for _ in range(10):
            choice = blocks.pick_exercise(
                ex_pool.ARMS, history, used_this_week=set(), rng=rng, excluded_names=excluded,
            )
            self.assertEqual(choice.name, pool_names[-1])

    def test_pick_exercise_falls_back_to_excluded_pool_rather_than_crash(self):
        history = History()
        history.begin_week()
        pool_names = [e.name for e in ex_pool.by_pattern(ex_pool.GLUTES)]
        excluded = frozenset(pool_names)  # exclude every exercise in the pattern

        choice = blocks.pick_exercise(
            ex_pool.GLUTES, history, used_this_week=set(), rng=random.Random(5), excluded_names=excluded,
        )
        self.assertIn(choice.name, pool_names)  # had no choice but to include one

    def test_build_buyout_steers_away_from_a_fully_excluded_pattern_when_an_alternative_exists(self):
        history = History()
        history.begin_week()
        excluded = frozenset(e.name for e in ex_pool.by_pattern(ex_pool.POWER))

        rng = random.Random(6)
        for _ in range(10):
            block = blocks.build_buyout(
                (ex_pool.POWER, ex_pool.CARDIO), history, used_this_week=set(), rng=rng,
                excluded_names=excluded,
            )
            self.assertEqual(block["exercises"][0].pattern, ex_pool.CARDIO)


class TimerSpecTests(unittest.TestCase):
    """Every block builder must attach a machine-readable `timer` spec
    alongside its human-readable `structure` text, for the web interval
    timer. These checks make sure the two never drift out of sync and that
    every timer kind has the fields the client-side player expects."""

    def _history_and_rng(self, seed):
        history = History()
        history.begin_week()
        return history, random.Random(seed)

    def _assert_valid_timer(self, timer, exercise_count):
        self.assertIn(timer["kind"], ("intervals", "amrap", "continuous", "rounds_with_rest"))
        if timer["kind"] == "intervals":
            self.assertGreater(timer["rounds"], 0)
            self.assertGreater(timer["work_seconds"], 0)
            self.assertGreaterEqual(timer["rest_seconds"], 0)
            self.assertEqual(timer["exercise_count"], exercise_count)
        elif timer["kind"] == "amrap":
            self.assertGreater(timer["total_seconds"], 0)
            self.assertGreater(timer["segment_seconds"], 0)
            self.assertEqual(timer["exercise_count"], exercise_count)
        elif timer["kind"] == "continuous":
            self.assertGreater(timer["seconds"], 0)
            self.assertEqual(timer["exercise_count"], exercise_count)
        elif timer["kind"] == "rounds_with_rest":
            self.assertGreater(timer["rounds"], 0)
            self.assertGreaterEqual(timer["rest_seconds"], 0)
            self.assertEqual(len(timer["rep_labels"]), timer["rounds"])

    def test_superset_timer_matches_exercise_count_across_many_rolls(self):
        history, rng = self._history_and_rng(1)
        for _ in range(30):
            block = blocks.build_superset(
                (ex_pool.SQUAT, ex_pool.PUSH_H), history, used_this_week=set(), rng=rng,
            )
            self._assert_valid_timer(block["timer"], exercise_count=2)

    def test_buyout_timer_is_continuous_two_minutes(self):
        history, rng = self._history_and_rng(2)
        block = blocks.build_buyout(ex_pool.CARDIO, history, used_this_week=set(), rng=rng)
        self.assertEqual(block["timer"], {"kind": "continuous", "seconds": 120, "exercise_count": 1})

    def test_drop_set_timer_is_rounds_with_rest_and_matches_reps(self):
        history, rng = self._history_and_rng(3)
        block = blocks.build_drop_set(ex_pool.ARMS, history, used_this_week=set(), rng=rng)
        self._assert_valid_timer(block["timer"], exercise_count=1)
        self.assertEqual(block["timer"]["kind"], "rounds_with_rest")
        self.assertEqual(block["timer"]["rep_labels"], ["10", "8", "6"])

    def test_core_finisher_timer_across_many_rolls(self):
        history, rng = self._history_and_rng(4)
        for _ in range(30):
            block = blocks.build_core_finisher(
                (ex_pool.CORE_FLEX, ex_pool.CORE_ANTI), history, used_this_week=set(), rng=rng,
            )
            self._assert_valid_timer(block["timer"], exercise_count=2)
            self.assertEqual(block["timer"]["kind"], "intervals")

    def test_bag_round_timer_across_many_rolls(self):
        history, rng = self._history_and_rng(5)
        for _ in range(30):
            block = blocks.build_bag_round(ex_pool.BAG, history, used_this_week=set(), rng=rng)
            self._assert_valid_timer(block["timer"], exercise_count=1)

    def test_every_week_block_has_a_timer_after_serialization(self):
        history = History()
        week = build_week(4, history, rng=random.Random(9), generated_at="2026-09-20")
        stored = history.week_by_index(week["week_index"])
        for day in stored["days"]:
            for block in day["blocks"]:
                self.assertIn("timer", block)
                self.assertIn("kind", block["timer"])


class WeekBuilderTests(unittest.TestCase):
    def test_four_day_week_structure(self):
        history = History()
        week = build_week(4, history, rng=random.Random(42), generated_at="2026-09-20")

        self.assertEqual(len(week["days"]), 4)
        for day in week["days"]:
            self.assertEqual(len(day["blocks"]), 7)
            types = [b["type"] for b in day["blocks"]]
            self.assertEqual(
                types,
                ["superset", "buyout", "superset", "buyout", "drop_set", "core_finisher", "bag_round"],
            )

    def test_three_day_week_uses_distinct_templates(self):
        history = History()
        week = build_week(3, history, rng=random.Random(7), generated_at="2026-09-20")
        titles = [day["title"] for day in week["days"]]
        self.assertEqual(len(set(titles)), 3)

    def test_history_accumulates_across_multiple_weeks(self):
        history = History()
        build_week(4, history, rng=random.Random(1), generated_at="2026-09-06")
        build_week(4, history, rng=random.Random(2), generated_at="2026-09-13")

        self.assertEqual(history.week_index, 2)
        self.assertEqual(len(history.weeks), 2)
        self.assertGreater(len(history.last_used), 0)

    def test_starting_template_rotates_week_to_week(self):
        history = History()
        week1 = build_week(3, history, rng=random.Random(3), generated_at="2026-09-06")
        week2 = build_week(3, history, rng=random.Random(4), generated_at="2026-09-13")
        self.assertNotEqual(week1["days"][0]["title"], week2["days"][0]["title"])

    def test_select_templates_with_no_bias_is_plain_rotation(self):
        # start_offset=2, 3 of 4 templates: {2, 3, 0} in rotation order --
        # the same result the old rotation-only implementation gave, since
        # an empty/neutral bias must never change which templates are picked.
        chosen = week_builder_module._select_templates(3, start_offset=2, rating_bias={})
        expected = [DAY_TEMPLATES[2], DAY_TEMPLATES[3], DAY_TEMPLATES[0]]
        self.assertEqual(chosen, expected)

    def test_select_templates_favors_a_highly_rated_template(self):
        # DAY_TEMPLATES[3] is last in this rotation (weakest rotation
        # position) but a strong +3 bias should still pull it into a
        # 3-of-4 selection ahead of a neutral template earlier in rotation.
        bias = {DAY_TEMPLATES[3]["title"]: 3.0}
        chosen = week_builder_module._select_templates(3, start_offset=0, rating_bias=bias)
        titles = {t["title"] for t in chosen}
        self.assertIn(DAY_TEMPLATES[3]["title"], titles)
        self.assertNotIn(DAY_TEMPLATES[2]["title"], titles)

    def test_select_templates_penalizes_a_poorly_rated_template(self):
        # start_offset=1 puts DAY_TEMPLATES[0] last in rotation (weakest
        # position already); a -3 bias on top of that should knock it out
        # of a 3-of-4 selection outright.
        bias = {DAY_TEMPLATES[0]["title"]: -3.0}
        chosen = week_builder_module._select_templates(3, start_offset=1, rating_bias=bias)
        titles = {t["title"] for t in chosen}
        self.assertNotIn(DAY_TEMPLATES[0]["title"], titles)

    def test_select_templates_still_uses_every_template_for_a_four_day_week(self):
        bias = {DAY_TEMPLATES[0]["title"]: -3.0, DAY_TEMPLATES[2]["title"]: 3.0}
        chosen = week_builder_module._select_templates(4, start_offset=0, rating_bias=bias)
        self.assertEqual({t["title"] for t in chosen}, {t["title"] for t in DAY_TEMPLATES})

    def test_template_bias_is_neutral_without_a_rating(self):
        self.assertEqual(week_builder_module._template_bias(None), 0.0)

    def test_template_bias_scales_with_rating(self):
        self.assertGreater(week_builder_module._template_bias(5), 0)
        self.assertLess(week_builder_module._template_bias(1), 0)
        self.assertEqual(week_builder_module._template_bias(3), 0.0)

    def test_build_week_includes_a_never_rated_template_over_poorly_rated_ones(self):
        # 1-star feeds a -3 bias, exactly offsetting the +/-3 spread rotation
        # position can produce on its own -- so a template that's never been
        # part of a rated week can never lose out to three 1-star ones,
        # whatever the rotation alignment happens to be that week.
        history = History()
        week1 = build_week(3, history, rng=random.Random(1), generated_at="2026-09-06")
        history.rate_week(week1["week_index"], 1)

        all_titles = {t["title"] for t in DAY_TEMPLATES}
        never_used_title = (all_titles - {d["title"] for d in week1["days"]}).pop()

        week2 = build_week(3, history, rng=random.Random(2), generated_at="2026-09-13")
        self.assertIn(never_used_title, [d["title"] for d in week2["days"]])

    def test_rejects_out_of_range_day_counts(self):
        history = History()
        with self.assertRaises(ValueError):
            build_week(2, history)
        with self.assertRaises(ValueError):
            build_week(5, history)

    def test_recorded_week_is_json_serializable_and_lookupable(self):
        history = History()
        week = build_week(4, history, rng=random.Random(11), generated_at="2026-09-20")

        stored = history.week_by_index(week["week_index"])
        self.assertIsNotNone(stored)
        json.dumps(stored)  # must not raise -- everything is plain dict/list/str

        self.assertEqual(len(stored["days"]), 4)
        first_exercise = stored["days"][0]["blocks"][0]["exercises"][0]
        self.assertIsInstance(first_exercise, dict)
        self.assertIn("name", first_exercise)
        self.assertIn("load_hint", first_exercise)

    def test_every_day_gets_a_varied_bag_finisher(self):
        history = History()
        week = build_week(4, history, rng=random.Random(13), generated_at="2026-09-20")

        bag_names = []
        for day in week["days"]:
            bag_blocks = [b for b in day["blocks"] if b["type"] == "bag_round"]
            self.assertEqual(len(bag_blocks), 1)
            bag_block = bag_blocks[0]
            self.assertEqual(len(bag_block["exercises"]), 1)
            self.assertEqual(bag_block["exercises"][0].pattern, ex_pool.BAG)
            bag_names.append(bag_block["exercises"][0].name)

        # 4 days, 7 distinct bag combos in the pool -- no repeats within the week
        self.assertEqual(len(set(bag_names)), len(bag_names))

        self.assertIsNone(history.week_by_index(999))

    def test_regenerate_week_keeps_index_but_changes_content(self):
        history = History()
        original = build_week(4, history, rng=random.Random(21), generated_at="2026-09-06")

        regenerated = regenerate_week(
            1, 4, history, rng=random.Random(99), avoid_weeks=0, generated_at="2026-09-20",
        )

        self.assertEqual(regenerated["week_index"], 1)
        self.assertEqual(regenerated["generated_at"], "2026-09-20")
        self.assertEqual(len(history.weeks), 1)  # replaced, not appended
        self.assertEqual(history.week_by_index(1)["generated_at"], "2026-09-20")

        def names(week):
            return sorted(
                e.name for day in week["days"] for block in day["blocks"] for e in block["exercises"]
            )

        self.assertNotEqual(names(original), names(regenerated))

    def test_regenerate_week_can_change_day_count(self):
        history = History()
        build_week(4, history, rng=random.Random(5), generated_at="2026-09-06")

        regenerated = regenerate_week(1, 3, history, rng=random.Random(6), generated_at="2026-09-20")
        self.assertEqual(len(regenerated["days"]), 3)
        self.assertEqual(len(history.week_by_index(1)["days"]), 3)

    def test_build_week_honors_excluded_names_where_a_substitute_exists(self):
        history = History()
        # Exclude only 2 of ARMS' 5 exercises -- 3 candidates comfortably
        # cover the pattern's 2 uses across the week (one per day template
        # that has an ARMS drop set) without ever forcing a reuse.
        excluded = frozenset(e.name for e in ex_pool.by_pattern(ex_pool.ARMS)[:2])
        week = build_week(4, history, rng=random.Random(8), generated_at="2026-09-20", excluded_names=excluded)

        used = {e.name for day in week["days"] for block in day["blocks"] for e in block["exercises"]}
        self.assertFalse(used & excluded)


class GenerateModuleTests(unittest.TestCase):
    def test_log_day_persists_and_backs_up(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            week, _markdown, _out = generate_module.generate_week(4, history_path=history_path, seed=1)

            updated = generate_module.log_day(
                week["week_index"], 0, history_path=history_path,
                completed=True, notes="good session",
                exercise_logs={(0, 0): {"actual": "20 lb x10", "feel": "right"}},
            )
            self.assertTrue(updated)

            reloaded = History.load(history_path)
            day = reloaded.week_by_index(week["week_index"])["days"][0]
            self.assertTrue(day["completed"])
            self.assertEqual(day["notes"], "good session")
            self.assertEqual(day["blocks"][0]["exercises"][0]["actual"], "20 lb x10")

            backups = list((Path(tmp_dir) / "backups").glob("*.json"))
            self.assertEqual(len(backups), 2)  # one from generate, one from logging

    def test_log_day_returns_false_and_does_not_backup_for_unknown_week(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            generate_module.generate_week(4, history_path=history_path, seed=1)

            updated = generate_module.log_day(999, 0, history_path=history_path, completed=True)
            self.assertFalse(updated)

            backups = list((Path(tmp_dir) / "backups").glob("*.json"))
            self.assertEqual(len(backups), 1)  # only the one from generate

    def test_rate_week_persists_and_backs_up(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            week, _markdown, _out = generate_module.generate_week(4, history_path=history_path, seed=1)

            updated = generate_module.rate_week(week["week_index"], 4, history_path=history_path)
            self.assertTrue(updated)

            reloaded = History.load(history_path)
            self.assertEqual(reloaded.week_by_index(week["week_index"])["rating"], 4)

            backups = list((Path(tmp_dir) / "backups").glob("*.json"))
            self.assertEqual(len(backups), 2)  # one from generate, one from rating

    def test_rate_week_returns_false_for_unknown_week(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            generate_module.generate_week(4, history_path=history_path, seed=1)

            updated = generate_module.rate_week(999, 5, history_path=history_path)
            self.assertFalse(updated)

    def test_generate_week_creates_a_backup(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            generate_module.generate_week(4, history_path=history_path, seed=1)
            backups = list((Path(tmp_dir) / "backups").glob("*.json"))
            self.assertEqual(len(backups), 1)

    def test_generate_week_dry_run_does_not_create_a_backup(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            generate_module.generate_week(4, history_path=history_path, seed=1, save=False)
            self.assertFalse((Path(tmp_dir) / "backups").exists())

    def test_regenerate_and_delete_each_create_their_own_backup(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            week, _markdown, _out = generate_module.generate_week(4, history_path=history_path, seed=1)
            generate_module.regenerate_week(week["week_index"], history_path=history_path, seed=2)
            generate_module.delete_week(week["week_index"], history_path=history_path)

            backups = list((Path(tmp_dir) / "backups").glob("*.json"))
            self.assertEqual(len(backups), 3)  # generate, regenerate, delete each changed the content

    def test_delete_week_removes_history_entry_and_output_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            output_dir = Path(tmp_dir) / "output"

            week, _markdown, out_path = generate_module.generate_week(
                4, history_path=history_path, output_dir=output_dir, seed=1,
            )
            self.assertTrue(out_path.exists())

            removed = generate_module.delete_week(
                week["week_index"], history_path=history_path, output_dir=output_dir,
            )
            self.assertTrue(removed)
            self.assertFalse(out_path.exists())

            history = History.load(history_path)
            self.assertIsNone(history.week_by_index(week["week_index"]))

    def test_delete_week_returns_false_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            removed = generate_module.delete_week(999, history_path=history_path)
            self.assertFalse(removed)

    def test_regenerate_week_replaces_output_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            output_dir = Path(tmp_dir) / "output"

            week, _markdown, old_path = generate_module.generate_week(
                4, history_path=history_path, output_dir=output_dir, seed=1,
                avoid_weeks=0,
            )

            result = generate_module.regenerate_week(
                week["week_index"], history_path=history_path, output_dir=output_dir,
                seed=2, avoid_weeks=0,
            )
            self.assertIsNotNone(result)
            new_week, _markdown, new_path = result

            self.assertEqual(new_week["week_index"], week["week_index"])
            self.assertTrue(new_path.exists())
            written_files = list(output_dir.glob("week-*.md"))
            self.assertEqual(len(written_files), 1)  # old file cleaned up, not left orphaned

    def test_regenerate_week_returns_none_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            result = generate_module.regenerate_week(999, history_path=history_path)
            self.assertIsNone(result)

    def test_resolve_excluded_names_expands_patterns_and_merges_exercises(self):
        names = generate_module.resolve_excluded_names(
            excluded_exercises=["Goblet Squat"], excluded_patterns=[ex_pool.CALVES],
        )
        self.assertIn("Goblet Squat", names)
        self.assertIn("Lunge-to-Calf-Raise Combo", names)  # CALVES pattern's only exercise

    def test_resolve_excluded_names_handles_no_exclusions(self):
        self.assertEqual(generate_module.resolve_excluded_names(), frozenset())

    def test_find_exclusion_violations_empty_when_fully_honored(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            excluded = generate_module.resolve_excluded_names(excluded_exercises=["Goblet Squat"])
            week, _markdown, _out = generate_module.generate_week(
                4, history_path=history_path, seed=10, excluded_exercises=["Goblet Squat"],
            )
            self.assertEqual(generate_module.find_exclusion_violations(week, excluded), [])

    def test_find_exclusion_violations_flags_unavoidable_pattern_exclusion(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            # Horizontal Push is mandatory (no substitute) in Block A/B of
            # several day templates -- excluding it entirely can't always be honored.
            excluded = generate_module.resolve_excluded_names(excluded_patterns=[ex_pool.PUSH_H])
            week, _markdown, _out = generate_module.generate_week(
                4, history_path=history_path, seed=3, excluded_patterns=[ex_pool.PUSH_H],
            )
            violations = generate_module.find_exclusion_violations(week, excluded)
            self.assertTrue(violations)
            for name in violations:
                self.assertIn(name, excluded)


class CliTests(unittest.TestCase):
    def test_dry_run_does_not_write_history_or_output(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            output_dir = Path(tmp_dir) / "output"

            rc = cli_main([
                "--days", "3",
                "--seed", "5",
                "--dry-run",
                "--history-file", str(history_path),
                "--output-dir", str(output_dir),
            ])

            self.assertEqual(rc, 0)
            self.assertFalse(history_path.exists())
            self.assertFalse(output_dir.exists())

    def test_run_writes_history_and_output_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            output_dir = Path(tmp_dir) / "output"

            rc = cli_main([
                "--days", "4",
                "--seed", "9",
                "--history-file", str(history_path),
                "--output-dir", str(output_dir),
            ])

            self.assertEqual(rc, 0)
            self.assertTrue(history_path.exists())
            written_files = list(output_dir.glob("week-*.md"))
            self.assertEqual(len(written_files), 1)

    def test_generate_subcommand_matches_flat_form(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            output_dir = Path(tmp_dir) / "output"

            rc = cli_main([
                "generate", "--days", "4", "--seed", "9",
                "--history-file", str(history_path), "--output-dir", str(output_dir),
            ])
            self.assertEqual(rc, 0)
            self.assertTrue(history_path.exists())

    def test_list_reports_no_weeks_then_generated_weeks(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            output_dir = Path(tmp_dir) / "output"
            common = ["--history-file", str(history_path), "--output-dir", str(output_dir)]

            rc = cli_main(["list", *common])
            self.assertEqual(rc, 0)

            cli_main(["generate", "--days", "3", "--seed", "1", *common])
            rc = cli_main(["list", *common])
            self.assertEqual(rc, 0)

            history = History.load(history_path)
            self.assertEqual(len(history.weeks), 1)

    def test_delete_subcommand(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            output_dir = Path(tmp_dir) / "output"
            common = ["--history-file", str(history_path), "--output-dir", str(output_dir)]

            cli_main(["generate", "--days", "3", "--seed", "1", *common])

            rc = cli_main(["delete", "--week", "1", *common])
            self.assertEqual(rc, 0)
            self.assertIsNone(History.load(history_path).week_by_index(1))

            rc = cli_main(["delete", "--week", "1", *common])
            self.assertEqual(rc, 1)  # already gone

    def test_regenerate_subcommand(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            output_dir = Path(tmp_dir) / "output"
            common = ["--history-file", str(history_path), "--output-dir", str(output_dir)]

            cli_main(["generate", "--days", "4", "--seed", "1", *common])

            rc = cli_main(["regenerate", "--week", "1", "--seed", "2", *common])
            self.assertEqual(rc, 0)
            self.assertEqual(len(History.load(history_path).weeks), 1)

            rc = cli_main(["regenerate", "--week", "999", *common])
            self.assertEqual(rc, 1)

    def test_rate_subcommand_sets_and_clears_a_rating(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            output_dir = Path(tmp_dir) / "output"
            common = ["--history-file", str(history_path), "--output-dir", str(output_dir)]

            cli_main(["generate", "--days", "3", "--seed", "1", *common])

            rc = cli_main(["rate", "--week", "1", "--stars", "4", *common])
            self.assertEqual(rc, 0)
            self.assertEqual(History.load(history_path).week_by_index(1)["rating"], 4)

            rc = cli_main(["rate", "--week", "1", "--clear", *common])
            self.assertEqual(rc, 0)
            self.assertIsNone(History.load(history_path).week_by_index(1)["rating"])

            rc = cli_main(["rate", "--week", "999", "--stars", "5", *common])
            self.assertEqual(rc, 1)

    def test_rate_subcommand_requires_stars_or_clear(self):
        with self.assertRaises(SystemExit):
            with redirect_stderr(io.StringIO()):
                cli_main(["rate", "--week", "1"])

    def test_resolve_history_file_prefers_explicit_flag_over_user(self):
        args = argparse.Namespace(history_file=Path("/explicit/history.json"), user="dad")
        self.assertEqual(cli_module._resolve_history_file(args), Path("/explicit/history.json"))

    def test_resolve_history_file_derives_from_user_when_no_explicit_flag(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir) / "data"
            args = argparse.Namespace(history_file=None, user="Dad")
            self.assertEqual(
                cli_module._resolve_history_file(args, data_root=data_root),
                data_root / "users" / "dad" / "history.json",
            )

    def test_resolve_history_file_falls_back_to_shared_default_without_user(self):
        args = argparse.Namespace(history_file=None, user=None)
        self.assertEqual(cli_module._resolve_history_file(args), cli_module.DEFAULT_HISTORY_PATH)

    def test_resolve_output_dir_derives_from_user_when_no_explicit_flag(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_root = Path(tmp_dir) / "output"
            args = argparse.Namespace(output_dir=None, user="mom")
            self.assertEqual(
                cli_module._resolve_output_dir(args, output_root=output_root),
                output_root / "mom",
            )

    def test_user_flag_scopes_generate_and_list_to_that_users_history(self):
        # --user with no --history-file/--output-dir override resolves against
        # the *real* data/output roots (that's the whole point -- it's meant
        # to be usable without spelling out a path every time), so use a
        # throwaway username and clean up afterward rather than mocking the
        # roots (already covered directly by the _resolve_* unit tests above).
        username = "test_cli_user_5f3a"
        history_path = user_paths.user_history_path(username)
        output_dir = user_paths.user_output_dir(username)
        self.addCleanup(lambda: shutil.rmtree(history_path.parent, ignore_errors=True))
        self.addCleanup(lambda: shutil.rmtree(output_dir, ignore_errors=True))

        rc = cli_main(["generate", "--days", "3", "--seed", "1", "--user", username])
        self.assertEqual(rc, 0)
        self.assertTrue(history_path.exists())
        self.assertEqual(len(History.load(history_path).weeks[0]["days"]), 3)

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            cli_main(["list", "--user", username])
        self.assertIn("Week 1", stdout.getvalue())

    def test_generate_exclude_flags_keep_excluded_names_out_of_output(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            output_dir = Path(tmp_dir) / "output"

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli_main([
                    "generate", "--days", "4", "--seed", "15",
                    "--exclude-exercise", "Goblet Squat", "--exclude-exercise", "Two-Hand Dumbbell Squat",
                    "--history-file", str(history_path), "--output-dir", str(output_dir),
                ])
            self.assertEqual(rc, 0)
            self.assertNotIn("Goblet Squat", stdout.getvalue())
            self.assertNotIn("Two-Hand Dumbbell Squat", stdout.getvalue())

    def test_generate_warns_on_stderr_when_exclusion_cannot_be_fully_honored(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            output_dir = Path(tmp_dir) / "output"

            stderr = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
                cli_main([
                    "generate", "--days", "4", "--seed", "3",
                    "--exclude-pattern", "push_horizontal",
                    "--history-file", str(history_path), "--output-dir", str(output_dir),
                ])
            self.assertIn("couldn't fully honor", stderr.getvalue().lower())

    def test_exclude_flags_reject_unknown_values(self):
        with self.assertRaises(SystemExit):
            with redirect_stderr(io.StringIO()):
                cli_main(["generate", "--exclude-exercise", "Not A Real Exercise"])
        with self.assertRaises(SystemExit):
            with redirect_stderr(io.StringIO()):
                cli_main(["generate", "--exclude-pattern", "not_a_real_pattern"])

    def test_streaks_subcommand_reports_current_and_longest(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            output_dir = Path(tmp_dir) / "output"
            common = ["--history-file", str(history_path), "--output-dir", str(output_dir)]

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli_main(["streaks", *common])
            self.assertEqual(rc, 0)
            self.assertIn("Current streak: 0", stdout.getvalue())

            cli_main(["generate", "--days", "3", "--seed", "1", *common])
            history = History.load(history_path)
            history.update_day_log(1, 0, completed=True)
            history.save(history_path)

            stdout2 = io.StringIO()
            with redirect_stdout(stdout2):
                rc = cli_main(["streaks", *common])
            self.assertEqual(rc, 0)
            self.assertIn("Current streak: 1", stdout2.getvalue())
            self.assertIn("Total workouts logged: 1", stdout2.getvalue())

    def test_backups_subcommand_reports_none_then_lists_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.json"
            output_dir = Path(tmp_dir) / "output"
            common = ["--history-file", str(history_path), "--output-dir", str(output_dir)]

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli_main(["backups", "--history-file", str(history_path)])
            self.assertEqual(rc, 0)
            self.assertIn("No backups yet", stdout.getvalue())

            cli_main(["generate", "--days", "3", "--seed", "1", *common])

            stdout2 = io.StringIO()
            with redirect_stdout(stdout2):
                rc = cli_main(["backups", "--history-file", str(history_path)])
            self.assertEqual(rc, 0)
            self.assertIn("history_", stdout2.getvalue())
            self.assertIn("bytes)", stdout2.getvalue())


if __name__ == "__main__":
    unittest.main()
