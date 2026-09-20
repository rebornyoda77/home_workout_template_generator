import re
import tempfile
import unittest
from pathlib import Path

from workout_generator import web_config, web_server


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


if __name__ == "__main__":
    unittest.main()
