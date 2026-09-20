"""Flask web interface: generate a week from the browser, and browse past
weeks. Same shape as the budget tool's web interface -- single passcode
gate held in the session cookie, CSRF token on the one form that mutates
anything -- sized down for this tool's single form and single data file.
"""

from __future__ import annotations

import secrets
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, session, url_for

from . import web_config
from .generate import DEFAULT_OUTPUT_DIR, generate_week
from .history import DEFAULT_HISTORY_PATH, History

DEFAULT_PORT = 5050


def _new_csrf_token() -> str:
    token = secrets.token_hex(16)
    session["csrf_token"] = token
    return token


def _check_csrf(form) -> bool:
    token = session.get("csrf_token")
    submitted = form.get("csrf_token")
    return bool(token) and bool(submitted) and secrets.compare_digest(token, submitted)


def create_app(
    *,
    history_path: Path = DEFAULT_HISTORY_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    web_config_path: Path = web_config.DEFAULT_CONFIG_PATH,
) -> Flask:
    """Paths are resolved once here (not left as function-default lookups
    on the route handlers below) so a caller -- production code or a test --
    can point a whole app instance at its own data files without any
    global/module-level state to juggle."""
    app = Flask(__name__)
    app.secret_key = secrets.token_hex(32)
    app.config["HISTORY_PATH"] = Path(history_path)
    app.config["OUTPUT_DIR"] = Path(output_dir)
    app.config["WEB_CONFIG_PATH"] = Path(web_config_path)

    @app.before_request
    def require_login():
        if request.endpoint in ("login", "static"):
            return None
        if not session.get("authed"):
            return redirect(url_for("login"))
        return None

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if session.get("authed"):
            return redirect(url_for("dashboard"))
        error = None
        if request.method == "POST":
            passcode = request.form.get("passcode", "")
            if web_config.verify_web_passcode(passcode, app.config["WEB_CONFIG_PATH"]):
                session["authed"] = True
                return redirect(url_for("dashboard"))
            error = "Incorrect passcode."
        return render_template("login.html", error=error)

    @app.route("/logout")
    def logout():
        session.pop("authed", None)
        return redirect(url_for("login"))

    @app.route("/")
    def dashboard():
        history = History.load(app.config["HISTORY_PATH"])
        latest_week = history.weeks[-1] if history.weeks else None
        return render_template(
            "dashboard.html", active_page="dashboard", latest_week=latest_week,
            csrf_token=_new_csrf_token(),
        )

    @app.route("/generate", methods=["POST"])
    def generate():
        if not _check_csrf(request.form):
            return "Your session expired -- go back and try again.", 400

        try:
            days = int(request.form.get("days", 4))
        except ValueError:
            days = 4
        if days not in (3, 4):
            days = 4

        try:
            avoid_weeks = int(request.form.get("avoid_weeks", 2))
        except ValueError:
            avoid_weeks = 2
        avoid_weeks = max(0, avoid_weeks)

        week, _markdown, _out_path = generate_week(
            days,
            history_path=app.config["HISTORY_PATH"],
            output_dir=app.config["OUTPUT_DIR"],
            avoid_weeks=avoid_weeks,
        )
        flash(f"Generated Week {week['week_index']}.")
        return redirect(url_for("view_week", week_index=week["week_index"]))

    @app.route("/week/<int:week_index>")
    def view_week(week_index: int):
        history = History.load(app.config["HISTORY_PATH"])
        entry = history.week_by_index(week_index)
        if entry is None:
            return "That week hasn't been generated.", 404
        return render_template("week.html", active_page="weeks", week=entry)

    @app.route("/history")
    def history_page():
        history = History.load(app.config["HISTORY_PATH"])
        return render_template(
            "history.html", active_page="history", weeks=list(reversed(history.weeks)),
        )

    return app
