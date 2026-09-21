"""Renders a generated week as readable Markdown."""


def _field(exercise, name):
    """`exercise` is a live Exercise dataclass instance for a just-built
    week (generate_week/regenerate_week), or a plain dict for one already
    serialized and read back from history (generate.copy_week) -- this
    reads either shape the same way."""
    return exercise[name] if isinstance(exercise, dict) else getattr(exercise, name)


def _format_exercise(exercise):
    bits = [_field(exercise, "name")]
    if _field(exercise, "unilateral"):
        bits.append("(each side)")
    line = " ".join(bits)
    return f"  - {line} — {_field(exercise, 'load_hint')}"


def _format_block(block):
    lines = [f"**{block['title']}** — _{block['structure']}_"]
    for exercise in block["exercises"]:
        lines.append(_format_exercise(exercise))
    return "\n".join(lines)


def _format_day(day_number, day):
    lines = [f"## Day {day_number}: {day['title']}", ""]
    for block in day["blocks"]:
        lines.append(_format_block(block))
        lines.append("")
    return "\n".join(lines)


def week_to_markdown(week):
    lines = [
        f"# Weekly Workout Template — Week {week['week_index']} ({week['generated_at']})",
        "",
    ]
    if week.get("deload"):
        lines.append(
            "**Deload / Recovery Week** — lighter volume, more rest, and no Power/Plyo work "
            "this week to help you recover."
        )
        lines.append("")
    lines += [
        "Home-equipment only: kettlebells (5/10/15 lb), dumbbells (5-30 lb), "
        "resistance bands, adjustable bench, treadmill, boxing bag, yoga mats.",
        "",
    ]
    for i, day in enumerate(week["days"], start=1):
        lines.append(_format_day(i, day))
    return "\n".join(lines).rstrip() + "\n"
