"""Turns a logged exercise entry into a plain-language "what to do next
time" suggestion. The free-text `actual` field ("20 lb x10") isn't reliably
parseable into a number to compute a suggested weight from -- people log it
in all sorts of formats -- so this stays qualitative, driven by the `feel`
rating (easy/right/hard) captured alongside it. See History.last_log and
History.update_day_log.
"""

FEEL_NUDGES = {
    "easy": "felt easy -- try going heavier or adding reps",
    "right": "felt just right -- repeat, or nudge up slightly",
    "hard": "felt hard -- repeat this before increasing",
}


def suggestion_for(last_log: dict) -> str:
    """`last_log` is a History.last_log() result (or None/empty). Returns a
    short "last time" suggestion string, or "" if there's nothing to base
    one on."""
    if not last_log:
        return ""
    actual = last_log.get("actual") or ""
    feel = last_log.get("feel") or ""
    if not actual and not feel:
        return ""

    parts = []
    if actual:
        parts.append(f'last time: "{actual}"')
    if feel in FEEL_NUDGES:
        parts.append(FEEL_NUDGES[feel])
    return " -- ".join(parts)
