import io
import json
import random
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from workout_generator import blocks, exercises as ex_pool
from workout_generator import generate as generate_module
from workout_generator.backup import backup_history
from workout_generator.cli import main as cli_main
from workout_generator.day_builder import DAY_TEMPLATES, exercise_names
from workout_generator.history import History
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
