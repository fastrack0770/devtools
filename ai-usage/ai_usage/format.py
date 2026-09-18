"""Naming and timestamp helpers shared by the provider adapters.

Window labels match the extension's previous JavaScript formatWindow(), so the
panel keeps reading exactly as it did before the move into Python.
"""

import datetime


def iso_to_unix(stamp):
    """Unix seconds of an ISO-8601 timestamp, or None when missing or unparseable."""
    if not stamp:
        return None
    text = stamp.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return int(parsed.timestamp())


def window_label(minutes):
    """A window named by its length: the providers do not agree on which windows exist."""
    if not minutes:
        return "Window"
    if minutes == 300:
        return "5 h"
    if minutes == 10080:
        return "Week"
    if minutes % (24 * 60) == 0:
        return "%d d" % (minutes // (24 * 60))
    if minutes % 60 == 0:
        return "%d h" % (minutes // 60)
    return "%d min" % minutes


def clamp_percent(value):
    """A share of a limit, or None when there is no trustworthy number."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(100.0, round(number, 1)))
