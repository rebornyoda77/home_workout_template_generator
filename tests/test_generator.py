import json
import random
import tempfile
import unittest
from pathlib import Path

from workout_generator import blocks, exercises as ex_pool
from workout_generator.cli import main as cli_main
from workout_generator.day_builder import DAY_TEMPLATES, exercise_names
from workout_generator.history import History
from workout_generator.week_builder import build_week

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


if __name__ == "__main__":
    unittest.main()
