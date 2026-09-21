"""Flask web interface: generate a week from the browser, and browse past
weeks. Each person has their own login and their own completely separate
history -- session-based auth keyed on a username (see users.py for
account storage, user_paths.py for how a username maps to that person's
own history/output files), CSRF token on every form that mutates anything.
"""

from __future__ import annotations

import secrets
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, session, url_for

from . import exercises as ex_pool
from . import users
from .generate import (
    delete_week, find_exclusion_violations, generate_week,
    log_day, rate_week, regenerate_week, resolve_excluded_names,
)
from .history import History
from .progression import suggestion_for
from .user_paths import DEFAULT_DATA_ROOT, DEFAULT_OUTPUT_ROOT, user_history_path, user_output_dir

DEFAULT_PORT = 5050


def _new_csrf_token() -> str:
    token = secrets.token_hex(16)
    session["csrf_token"] = token
    return token


def _check_csrf(form) -> bool:
    token = session.get("csrf_token")
    submitted = form.get("csrf_token")
    return bool(token) and bool(submitted) and secrets.compare_digest(token, submitted)


def _pattern_options():
    return [{"key": p, "label": ex_pool.PATTERN_LABELS[p]} for p in ex_pool.ALL_PATTERNS]


def _parse_exclude_patterns(form) -> list:
    return [p for p in form.getlist("exclude_patterns") if p in ex_pool.ALL_PATTERNS]


def _exercise_suggestions(history: History, week: dict) -> dict:
    """name -> "last time" progression hint, for every exercise appearing
    in this week -- computed once per page render rather than as a Jinja
    filter so the (cheap, but O(weeks)) history.last_log scan runs once
    per distinct exercise instead of once per template render call."""
    names = {
        exercise["name"]
        for day in week["days"]
        for block in day["blocks"]
        for exercise in block["exercises"]
    }
    return {name: suggestion_for(history.last_log(name)) for name in names}


def _flash_exclusion_violations(week: dict, excluded_patterns: list) -> None:
    if not excluded_patterns:
        return
    excluded_names = resolve_excluded_names(excluded_patterns=excluded_patterns)
    violations = find_exclusion_violations(week, excluded_names)
    if violations:
        flash(
            "Couldn't fully honor your exclusions -- some blocks have no substitute exercise: "
            + ", ".join(violations)
        )


def create_app(
    *,
    data_root: Path = DEFAULT_DATA_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    users_path: Path = users.DEFAULT_USERS_PATH,
) -> Flask:
    """Paths are resolved once here (not left as function-default lookups
    on the route handlers below) so a caller -- production code or a test --
    can point a whole app instance at its own data files without any
    global/module-level state to juggle. Unlike the old single-passcode
    version, HISTORY_PATH/OUTPUT_DIR aren't fixed here -- each request
    resolves its own from session["username"] via _history_path()/
    _output_dir() below, since every person's data lives separately."""
    app = Flask(__name__)
    app.secret_key = secrets.token_hex(32)
    app.config["DATA_ROOT"] = Path(data_root)
    app.config["OUTPUT_ROOT"] = Path(output_root)
    app.config["USERS_PATH"] = Path(users_path)

    def _history_path() -> Path:
        return user_history_path(session["username"], app.config["DATA_ROOT"])

    def _output_dir() -> Path:
        return user_output_dir(session["username"], app.config["OUTPUT_ROOT"])

    @app.context_processor
    def _inject_current_user():
        username = session.get("username")
        if not username:
            return {}
        return {"current_display_name": users.display_name_for(username, app.config["USERS_PATH"])}

    @app.before_request
    def require_login():
        if request.endpoint in ("login", "static"):
            return None
        username = session.get("username")
        if not username or not users.user_exists(username, app.config["USERS_PATH"]):
            session.pop("username", None)
            return redirect(url_for("login"))
        return None

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if session.get("username"):
            return redirect(url_for("dashboard"))
        error = None
        if request.method == "POST":
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            if users.verify_user(username, password, app.config["USERS_PATH"]):
                session["username"] = users.normalize_username(username)
                return redirect(url_for("dashboard"))
            error = "Incorrect username or password."
        return render_template(
            "login.html", error=error, accounts=users.list_users(app.config["USERS_PATH"]),
        )

    @app.route("/logout")
    def logout():
        session.pop("username", None)
        return redirect(url_for("login"))

    @app.route("/")
    def dashboard():
        history = History.load(_history_path())
        latest_week = history.weeks[-1] if history.weeks else None
        suggestions = _exercise_suggestions(history, latest_week) if latest_week else {}
        return render_template(
            "dashboard.html", active_page="dashboard", latest_week=latest_week,
            suggestions=suggestions, pattern_options=_pattern_options(), csrf_token=_new_csrf_token(),
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

        excluded_patterns = _parse_exclude_patterns(request.form)

        week, _markdown, _out_path = generate_week(
            days,
            history_path=_history_path(),
            output_dir=_output_dir(),
            avoid_weeks=avoid_weeks,
            excluded_patterns=excluded_patterns,
        )
        flash(f"Generated Week {week['week_index']}.")
        _flash_exclusion_violations(week, excluded_patterns)
        return redirect(url_for("view_week", week_index=week["week_index"]))

    @app.route("/week/<int:week_index>")
    def view_week(week_index: int):
        history = History.load(_history_path())
        entry = history.week_by_index(week_index)
        if entry is None:
            return "That week hasn't been generated.", 404
        return render_template(
            "week.html", active_page="weeks", week=entry,
            suggestions=_exercise_suggestions(history, entry),
            pattern_options=_pattern_options(), csrf_token=_new_csrf_token(),
        )

    @app.route("/week/<int:week_index>/delete", methods=["POST"])
    def delete_week_route(week_index: int):
        if not _check_csrf(request.form):
            return "Your session expired -- go back and try again.", 400

        removed = delete_week(
            week_index,
            history_path=_history_path(),
            output_dir=_output_dir(),
        )
        if removed:
            flash(f"Deleted Week {week_index}.")
        else:
            flash(f"Week {week_index} doesn't exist.")
        return redirect(url_for("history_page"))

    @app.route("/week/<int:week_index>/regenerate", methods=["POST"])
    def regenerate_week_route(week_index: int):
        if not _check_csrf(request.form):
            return "Your session expired -- go back and try again.", 400

        days_raw = request.form.get("days", "").strip()
        days = None
        if days_raw:
            try:
                parsed = int(days_raw)
                if parsed in (3, 4):
                    days = parsed
            except ValueError:
                pass

        try:
            avoid_weeks = int(request.form.get("avoid_weeks", 2))
        except ValueError:
            avoid_weeks = 2
        avoid_weeks = max(0, avoid_weeks)

        excluded_patterns = _parse_exclude_patterns(request.form)

        result = regenerate_week(
            week_index,
            history_path=_history_path(),
            output_dir=_output_dir(),
            num_days=days,
            avoid_weeks=avoid_weeks,
            excluded_patterns=excluded_patterns,
        )
        if result is None:
            flash(f"Week {week_index} doesn't exist.")
            return redirect(url_for("history_page"))

        week, _markdown, _out_path = result
        flash(f"Regenerated Week {week_index}.")
        _flash_exclusion_violations(week, excluded_patterns)
        return redirect(url_for("view_week", week_index=week_index))

    @app.route("/week/<int:week_index>/rate", methods=["POST"])
    def rate_week_route(week_index: int):
        if not _check_csrf(request.form):
            return "Your session expired -- go back and try again.", 400

        rating_raw = request.form.get("rating", "").strip()
        rating = None
        if rating_raw:
            try:
                parsed = int(rating_raw)
            except ValueError:
                parsed = None
            if parsed in (1, 2, 3, 4, 5):
                rating = parsed

        updated = rate_week(week_index, rating, history_path=_history_path())
        if not updated:
            flash(f"Week {week_index} doesn't exist.")
            return redirect(url_for("history_page"))
        flash(f"Rated Week {week_index}." if rating else f"Cleared Week {week_index}'s rating.")
        return redirect(url_for("view_week", week_index=week_index))

    @app.route("/week/<int:week_index>/day/<int:day_index>/log", methods=["POST"])
    def log_day_route(week_index: int, day_index: int):
        if not _check_csrf(request.form):
            return "Your session expired -- go back and try again.", 400

        history_path = _history_path()
        history = History.load(history_path)
        entry = history.week_by_index(week_index)
        if entry is None or not (0 <= day_index < len(entry["days"])):
            return "That day doesn't exist.", 404

        day = entry["days"][day_index]
        completed = request.form.get("completed") == "on"
        notes = request.form.get("notes", "").strip()

        exercise_logs = {}
        for bi, block in enumerate(day["blocks"]):
            for ei in range(len(block["exercises"])):
                actual = request.form.get(f"actual_b{bi}_e{ei}")
                feel = request.form.get(f"feel_b{bi}_e{ei}")
                if actual is not None or feel is not None:
                    exercise_logs[(bi, ei)] = {
                        "actual": (actual or "").strip(),
                        "feel": feel if feel in ("easy", "right", "hard") else "",
                    }

        log_day(
            week_index, day_index,
            history_path=history_path,
            completed=completed, notes=notes, exercise_logs=exercise_logs,
        )
        flash(f"Saved log for Day {day_index + 1}.")
        if request.form.get("next") == "today":
            return redirect(url_for("today_day", week_index=week_index, day_index=day_index))
        return redirect(url_for("view_week", week_index=week_index))

    @app.route("/today")
    def today():
        history = History.load(_history_path())
        if not history.weeks:
            flash("No weeks generated yet.")
            return redirect(url_for("dashboard"))
        latest = history.weeks[-1]
        day_index = next((i for i, d in enumerate(latest["days"]) if not d.get("completed")), 0)
        return redirect(url_for("today_day", week_index=latest["week_index"], day_index=day_index))

    @app.route("/week/<int:week_index>/day/<int:day_index>/today")
    def today_day(week_index: int, day_index: int):
        history = History.load(_history_path())
        entry = history.week_by_index(week_index)
        if entry is None or not (0 <= day_index < len(entry["days"])):
            return "That day doesn't exist.", 404

        day = entry["days"][day_index]
        total_days = len(entry["days"])
        day_suggestions = {
            exercise["name"]: suggestion_for(history.last_log(exercise["name"]))
            for block in day["blocks"] for exercise in block["exercises"]
        }
        return render_template(
            "today.html", active_page="today", week=entry, day=day, day_index=day_index,
            day_number=day_index + 1, total_days=total_days,
            prev_day_index=(day_index - 1 if day_index > 0 else None),
            next_day_index=(day_index + 1 if day_index < total_days - 1 else None),
            suggestions=day_suggestions, csrf_token=_new_csrf_token(),
        )

    @app.route("/history")
    def history_page():
        history = History.load(_history_path())
        return render_template(
            "history.html", active_page="history", weeks=list(reversed(history.weeks)),
            csrf_token=_new_csrf_token(),
        )

    @app.route("/glossary")
    def glossary():
        history = History.load(_history_path())
        groups = []
        for pattern in ex_pool.ALL_PATTERNS:
            entries = [
                {
                    "exercise": exercise,
                    "last_used_week": history.last_used.get(exercise.name),
                    "use_count": history.use_count.get(exercise.name, 0),
                    "suggestion": suggestion_for(history.last_log(exercise.name)),
                }
                for exercise in ex_pool.by_pattern(pattern)
            ]
            groups.append({"key": pattern, "label": ex_pool.PATTERN_LABELS[pattern], "exercises": entries})
        return render_template("glossary.html", active_page="glossary", groups=groups)

    return app
