import re
import tempfile
import unittest
from pathlib import Path

from workout_generator import web_config, web_server
from workout_generator.history import History


CSRF_RE = re.compile(rb'name="csrf_token" value="([0-9a-f]+)"')


class WebConfigTests(unittest.TestCase):
    def test_passcode_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "web_config.json"
            self.assertFalse(web_config.has_web_passcode(path))

            web_config.set_web_passcode("correct-horse", path)
            self.assertTrue(web_config.has_web_passcode(path))
            self.assertTrue(web_config.verify_web_passcode("correct-horse", path))
            self.assertFalse(web_config.verify_web_passcode("wrong", path))


class WebServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        tmp_path = Path(self.tmp_dir.name)

        config_path = tmp_path / "web_config.json"
        web_config.set_web_passcode("test-pass", config_path)

        self.app = web_server.create_app(
            history_path=tmp_path / "history.json",
            output_dir=tmp_path / "output",
            web_config_path=config_path,
        )
        self.app.testing = True
        self.client = self.app.test_client()

    def _login(self):
        return self.client.post("/login", data={"passcode": "test-pass"}, follow_redirects=True)

    def _csrf_from(self, response):
        match = CSRF_RE.search(response.data)
        self.assertIsNotNone(match, response.data[:500])
        return match.group(1).decode()

    def test_root_redirects_to_login_when_unauthenticated(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_wrong_passcode_is_rejected(self):
        response = self.client.post("/login", data={"passcode": "nope"})
        self.assertIn(b"Incorrect passcode", response.data)

    def test_login_then_dashboard_shows_empty_state(self):
        response = self._login()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No weeks generated yet", response.data)

    def test_generate_requires_valid_csrf_token(self):
        self._login()
        response = self.client.post("/generate", data={"days": "4", "csrf_token": "bogus"})
        self.assertEqual(response.status_code, 400)

    def test_generate_then_view_week_and_history(self):
        dashboard = self._login()
        csrf = self._csrf_from(dashboard)

        response = self.client.post(
            "/generate", data={"days": "4", "avoid_weeks": "2", "csrf_token": csrf},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Week 1", response.data)
        self.assertIn(b"Day 1", response.data)
        self.assertIn(b"Drop Set", response.data)

        history_response = self.client.get("/history")
        self.assertEqual(history_response.status_code, 200)
        self.assertIn(b"Lower-Body Power", history_response.data)
        self.assertIn(b'href="/week/1"', history_response.data)

        missing = self.client.get("/week/999")
        self.assertEqual(missing.status_code, 404)

    def test_week_page_has_a_print_button(self):
        self._generate_week()
        response = self.client.get("/week/1")
        self.assertIn(b'onclick="window.print()"', response.data)
        self.assertIn(b"Print This Week", response.data)

    def test_dashboard_print_button_excludes_the_generate_form_from_print(self):
        self._generate_week()
        response = self.client.get("/")
        self.assertIn(b'onclick="window.print()"', response.data)
        # the generate form must be wrapped so it's hidden by the @media print rule,
        # not left sitting on top of the printed week
        self.assertIn(b'<div class="no-print">', response.data)

    def test_logout_returns_to_login(self):
        self._login()
        response = self.client.get("/logout", follow_redirects=True)
        self.assertIn(b"Passcode", response.data)

    def _generate_week(self):
        dashboard = self._login()
        csrf = self._csrf_from(dashboard)
        return self.client.post(
            "/generate", data={"days": "4", "avoid_weeks": "2", "csrf_token": csrf},
            follow_redirects=True,
        )

    def test_delete_week_requires_valid_csrf_token(self):
        self._generate_week()
        response = self.client.post("/week/1/delete", data={"csrf_token": "bogus"})
        self.assertEqual(response.status_code, 400)

    def test_delete_week_removes_it(self):
        week_response = self._generate_week()
        csrf = self._csrf_from(week_response)

        response = self.client.post(
            "/week/1/delete", data={"csrf_token": csrf}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Deleted Week 1", response.data)

        missing = self.client.get("/week/1")
        self.assertEqual(missing.status_code, 404)

    def test_delete_unknown_week_flashes_message(self):
        dashboard = self._login()
        csrf = self._csrf_from(dashboard)

        response = self.client.post(
            "/week/999/delete", data={"csrf_token": csrf}, follow_redirects=True,
        )
        self.assertIn(b"doesn&#39;t exist", response.data)

    def test_regenerate_week_requires_valid_csrf_token(self):
        self._generate_week()
        response = self.client.post("/week/1/regenerate", data={"csrf_token": "bogus"})
        self.assertEqual(response.status_code, 400)

    def test_regenerate_week_changes_content_but_keeps_index(self):
        week_response = self._generate_week()
        csrf = self._csrf_from(week_response)

        response = self.client.post(
            "/week/1/regenerate", data={"csrf_token": csrf}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Regenerated Week 1", response.data)
        self.assertIn(b"Week 1", response.data)

        history_response = self.client.get("/history")
        self.assertIn(b'href="/week/1"', history_response.data)
        self.assertNotIn(b'href="/week/2"', history_response.data)

    def test_regenerate_unknown_week_flashes_message(self):
        dashboard = self._login()
        csrf = self._csrf_from(dashboard)

        response = self.client.post(
            "/week/999/regenerate", data={"csrf_token": csrf}, follow_redirects=True,
        )
        self.assertIn(b"doesn&#39;t exist", response.data)

    def test_rate_week_requires_valid_csrf_token(self):
        self._generate_week()
        response = self.client.post("/week/1/rate", data={"rating": "4", "csrf_token": "bogus"})
        self.assertEqual(response.status_code, 400)

    def test_rate_week_sets_and_shows_the_rating(self):
        week_response = self._generate_week()
        csrf = self._csrf_from(week_response)

        response = self.client.post(
            "/week/1/rate", data={"rating": "4", "csrf_token": csrf}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Rated Week 1", response.data)
        self.assertIn(b'class="star-button star-filled"', response.data)

    def test_rate_week_can_be_cleared(self):
        week_response = self._generate_week()
        csrf = self._csrf_from(week_response)
        self.client.post("/week/1/rate", data={"rating": "4", "csrf_token": csrf})

        response = self.client.post(
            "/week/1/rate", data={"rating": "", "csrf_token": csrf}, follow_redirects=True,
        )
        self.assertIn(b"Cleared Week 1", response.data)
        self.assertNotIn(b'class="star-button star-filled"', response.data)

    def test_rate_unknown_week_flashes_message(self):
        dashboard = self._login()
        csrf = self._csrf_from(dashboard)

        response = self.client.post(
            "/week/999/rate", data={"rating": "3", "csrf_token": csrf}, follow_redirects=True,
        )
        self.assertIn(b"doesn&#39;t exist", response.data)

    def test_history_page_shows_rating_column(self):
        week_response = self._generate_week()
        csrf = self._csrf_from(week_response)
        self.client.post("/week/1/rate", data={"rating": "3", "csrf_token": csrf})

        response = self.client.get("/history")
        self.assertIn("★★★".encode(), response.data)

    def test_glossary_requires_login(self):
        response = self.client.get("/glossary")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_glossary_lists_every_pattern_and_exercise(self):
        self._login()
        response = self.client.get("/glossary")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Exercise Glossary", response.data)
        # spot-check a pattern label and a couple of exercises from different groups
        self.assertIn(b"Boxing Bag", response.data)
        self.assertIn(b"Goblet Squat", response.data)
        self.assertIn(b"Jab-Cross Combo", response.data)

    def test_glossary_has_a_search_box_with_searchable_items(self):
        self._login()
        response = self.client.get("/glossary")
        self.assertIn(b'id="glossary-search"', response.data)
        # every item must carry a data-search attribute with its own name in it,
        # so the client-side filter has something to match against
        self.assertIn(b'data-search="goblet squat', response.data.lower())
        self.assertIn(b"Hike a kettlebell back between the legs", response.data)

    def test_glossary_shows_never_used_before_any_week_is_generated(self):
        self._login()
        response = self.client.get("/glossary")
        self.assertIn(b"Never used", response.data)
        self.assertNotIn(b"Used ", response.data)

    def test_glossary_shows_use_count_and_last_used_week_after_generating(self):
        self._generate_week()
        response = self.client.get("/glossary")
        self.assertIn(b"Used 1x", response.data)
        self.assertIn(b"last Week 1", response.data)
        # some patterns (e.g. calves, with only 1 exercise not used by every
        # template) may still show "Never used" for at least one exercise
        self.assertIn(b"Never used", response.data)

    def test_dashboard_and_week_forms_offer_pattern_exclusion_checkboxes(self):
        dashboard = self._login()
        self.assertIn(b'name="exclude_patterns"', dashboard.data)
        self.assertIn(b"Boxing Bag", dashboard.data)  # a pattern label, from PATTERN_LABELS

    def test_generate_with_excluded_pattern_flashes_violation_warning_when_unavoidable(self):
        # In a 4-day week every day template is always included, and
        # "loaded_carry" is a single-option buy-out pattern (no alternative)
        # in two of them -- excluding it entirely is always unavoidable.
        dashboard = self._login()
        csrf = self._csrf_from(dashboard)

        response = self.client.post(
            "/generate",
            data={
                "days": "4", "avoid_weeks": "0", "csrf_token": csrf,
                "exclude_patterns": ["loaded_carry"],
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"couldn&#39;t fully honor", response.data.lower())

    def test_regenerate_with_excluded_pattern_posts_through_cleanly(self):
        week_response = self._generate_week()
        csrf = self._csrf_from(week_response)

        response = self.client.post(
            "/week/1/regenerate",
            data={"csrf_token": csrf, "exclude_patterns": ["push_horizontal"]},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Regenerated Week 1", response.data)

    def test_week_page_has_logging_form_fields(self):
        week_response = self._generate_week()
        self.assertIn(b'name="completed"', week_response.data)
        self.assertIn(b'name="notes"', week_response.data)
        self.assertIn(b'name="actual_b0_e0"', week_response.data)
        self.assertIn(b'name="feel_b0_e0"', week_response.data)

    def test_log_day_requires_valid_csrf_token(self):
        self._generate_week()
        response = self.client.post("/week/1/day/0/log", data={"csrf_token": "bogus"})
        self.assertEqual(response.status_code, 400)

    def test_log_day_saves_completion_notes_and_exercise_log(self):
        week_response = self._generate_week()
        csrf = self._csrf_from(week_response)

        response = self.client.post(
            "/week/1/day/0/log",
            data={
                "csrf_token": csrf,
                "completed": "on",
                "notes": "solid session",
                "actual_b0_e0": "20 lb x10",
                "feel_b0_e0": "right",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Saved log for Day 1", response.data)
        self.assertIn(b"Completed", response.data)  # the day-card badge
        self.assertIn(b"solid session", response.data)
        self.assertIn(b"20 lb x10", response.data)

    def test_log_day_unchecked_completed_box_clears_it(self):
        week_response = self._generate_week()
        csrf = self._csrf_from(week_response)
        self.client.post(
            "/week/1/day/0/log",
            data={"csrf_token": csrf, "completed": "on"},
            follow_redirects=True,
        )

        week_response2 = self.client.get("/week/1")
        csrf2 = self._csrf_from(week_response2)
        response = self.client.post(
            "/week/1/day/0/log",
            data={"csrf_token": csrf2},  # box not included -> unchecked
            follow_redirects=True,
        )
        self.assertNotIn(b"Completed</span>", response.data)

    def test_log_day_returns_404_for_unknown_week_or_day(self):
        self._generate_week()
        dashboard = self.client.get("/week/1")
        csrf = self._csrf_from(dashboard)

        missing_week = self.client.post("/week/999/day/0/log", data={"csrf_token": csrf})
        self.assertEqual(missing_week.status_code, 404)

        missing_day = self.client.post("/week/1/day/999/log", data={"csrf_token": csrf})
        self.assertEqual(missing_day.status_code, 404)

    def test_no_suggestion_shown_before_anything_is_logged(self):
        response = self._generate_week()
        self.assertNotIn(b'class="exercise-suggestion"', response.data)

    def test_logged_exercise_suggestion_appears_next_time_it_is_scheduled(self):
        week_response = self._generate_week()
        csrf = self._csrf_from(week_response)

        first_exercise_name = re.search(
            rb'<span class="exercise-name">([^<]+?)(?: \(each side\))?</span>', week_response.data,
        ).group(1).decode()

        self.client.post(
            "/week/1/day/0/log",
            data={"csrf_token": csrf, "actual_b0_e0": "20 lb x10", "feel_b0_e0": "easy"},
            follow_redirects=True,
        )

        # generate a second week -- if that same exercise gets picked again,
        # its suggestion (built from the week-1 log) should show up next to it
        dashboard = self.client.get("/")
        csrf2 = self._csrf_from(dashboard)
        self.client.post(
            "/generate", data={"days": "4", "avoid_weeks": "0", "csrf_token": csrf2}, follow_redirects=True,
        )

        week2 = self.client.get("/week/2")
        if first_exercise_name.encode() in week2.data:
            self.assertIn(b'class="exercise-suggestion"', week2.data)
            self.assertIn(b"20 lb x10", week2.data)
            self.assertIn(b"heavier", week2.data)

    def test_glossary_shows_suggestion_after_logging(self):
        week_response = self._generate_week()
        csrf = self._csrf_from(week_response)

        self.client.post(
            "/week/1/day/0/log",
            data={"csrf_token": csrf, "actual_b0_e0": "20 lb x10", "feel_b0_e0": "hard"},
            follow_redirects=True,
        )

        response = self.client.get("/glossary")
        self.assertIn(b"20 lb x10", response.data)
        self.assertIn(b"repeat this before increasing", response.data)

    def test_today_redirects_to_login_when_unauthenticated(self):
        response = self.client.get("/today")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_today_redirects_to_dashboard_when_nothing_generated(self):
        self._login()
        response = self.client.get("/today", follow_redirects=True)
        self.assertIn(b"No weeks generated yet", response.data)

    def test_today_redirects_to_first_day_of_latest_week(self):
        self._generate_week()
        response = self.client.get("/today")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/week/1/day/0/today", response.headers["Location"])

    def test_today_skips_completed_days(self):
        week_response = self._generate_week()
        csrf = self._csrf_from(week_response)
        self.client.post("/week/1/day/0/log", data={"csrf_token": csrf, "completed": "on"})

        response = self.client.get("/today")
        self.assertIn("/week/1/day/1/today", response.headers["Location"])

    def test_today_day_view_shows_day_content_and_nav_links(self):
        self._generate_week()
        response = self.client.get("/week/1/day/0/today")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Day 1 of 4", response.data)
        self.assertNotIn(b"Previous Day", response.data)  # first day, no prev
        self.assertIn(b"Next Day", response.data)
        self.assertIn(b'name="completed"', response.data)

    def test_today_day_view_404s_for_unknown_week_or_day(self):
        self._generate_week()
        self.assertEqual(self.client.get("/week/999/day/0/today").status_code, 404)
        self.assertEqual(self.client.get("/week/1/day/999/today").status_code, 404)

    def test_logging_from_today_view_stays_on_today_view(self):
        self._generate_week()
        today_response = self.client.get("/week/1/day/0/today")
        csrf = self._csrf_from(today_response)

        response = self.client.post(
            "/week/1/day/0/log",
            data={"csrf_token": csrf, "next": "today", "completed": "on"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/week/1/day/0/today", response.headers["Location"])

    def test_focus_mode_link_present_on_week_page(self):
        response = self._generate_week()
        self.assertIn(b"Open in Focus Mode", response.data)
        self.assertIn(b'href="/week/1/day/0/today"', response.data)

    def test_manifest_is_served_without_login_and_has_required_fields(self):
        response = self.client.get("/static/manifest.json")
        self.assertEqual(response.status_code, 200)
        manifest = response.get_json()
        self.assertEqual(manifest["name"], "Home Workout Generator")
        self.assertEqual(manifest["start_url"], "/today")
        self.assertEqual(manifest["display"], "standalone")
        sizes = {icon["sizes"] for icon in manifest["icons"]}
        self.assertEqual(sizes, {"192x192", "512x512"})
        for icon in manifest["icons"]:
            icon_response = self.client.get(icon["src"])
            self.assertEqual(icon_response.status_code, 200, icon["src"])
            self.assertEqual(icon_response.mimetype, "image/png")

    def test_service_worker_is_served_without_login(self):
        response = self.client.get("/static/sw.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"addEventListener", response.data)

    def test_login_page_links_manifest_and_apple_touch_icon(self):
        response = self.client.get("/login")
        self.assertIn(b'rel="manifest"', response.data)
        self.assertIn(b'rel="apple-touch-icon"', response.data)
        self.assertIn(b'name="apple-mobile-web-app-capable" content="yes"', response.data)

    def test_dashboard_links_manifest_and_registers_service_worker(self):
        self._login()
        response = self.client.get("/")
        self.assertIn(b'rel="manifest"', response.data)
        self.assertIn(b"serviceWorker.register", response.data)

    def test_legacy_week_without_timer_field_still_renders(self):
        # Weeks generated before the interval-timer feature don't have a
        # "timer" key on their blocks (see week_builder.serialize_day) --
        # the page must render around that instead of crashing on
        # `{{ block.timer | tojson }}` with a real 500.
        history = History()
        history.begin_week()
        legacy_day = {
            "title": "Legacy Day",
            "completed": False,
            "notes": "",
            "blocks": [
                {
                    "type": "superset",
                    "title": "Block A - Strength Superset",
                    "structure": "4 rounds: 40s work / 20s rest per exercise",
                    "exercises": [
                        {
                            "name": "Goblet Squat", "pattern": "squat",
                            "equipment": ["kettlebell", "dumbbell"], "unilateral": False,
                            "load_hint": "1x KB/DB, 15-25 lb", "note": "", "tags": [],
                            "description": "", "actual": "", "feel": "",
                        },
                    ],
                },
            ],
        }
        history.record_week("2026-01-01", [legacy_day])
        history.save(self.app.config["HISTORY_PATH"])

        self._login()

        # the CSS block always defines `.start-timer-btn { ... }` regardless
        # of whether any button uses it, so check for the rendered button's
        # own class attribute rather than the bare class-name substring.
        rendered_button = b'class="button start-timer-btn'

        dashboard = self.client.get("/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertNotIn(rendered_button, dashboard.data)

        week_response = self.client.get("/week/1")
        self.assertEqual(week_response.status_code, 200)
        self.assertNotIn(rendered_button, week_response.data)

        today_response = self.client.get("/week/1/day/0/today")
        self.assertEqual(today_response.status_code, 200)
        self.assertNotIn(rendered_button, today_response.data)


if __name__ == "__main__":
    unittest.main()
