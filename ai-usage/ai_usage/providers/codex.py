"""Codex CLI usage: the helper's reply turned into schema-v1 windows.

Codex reports no fixed set of windows — a Plus account may return one weekly
limit and nothing else — so nothing here assumes a 5-hour window exists. The
helper already sorts them shortest-first and the first one is the primary.

The helper's second source is the session journal, a snapshot from whenever
Codex last ran; it is reported `stale`. A window of such a snapshot that has
already outlived its own reset loses its percentage rather than being shown as
a confident number, because it may have been spent from an IDE or the web since.
"""

from .. import format, schema
from . import common

ID = "codex"
TITLE = "Codex"
HELPER = "codex-usage-helper.py"

LIVE_SOURCE = "app-server"


def _kind(minutes):
    if minutes and minutes > 24 * 60:
        return "weekly"
    return "session"


def normalise(raw, fetched_at, now=None):
    now = fetched_at if now is None else now
    if not raw.get("ok"):
        reason = raw.get("error") or "helper"
        return schema.provider_result(
            state=common.failure_state(reason),
            error=reason,
            next_retry_at=common.next_retry_at(reason, raw.get("retry_after"), now),
        )

    source = raw.get("source") or LIVE_SOURCE
    stale = source != LIVE_SOURCE
    raw_windows = raw.get("windows") or []

    windows = []
    for index, entry in enumerate(raw_windows):
        minutes = entry.get("minutes")
        resets_at = entry.get("resets_at") or None
        expired = stale and bool(resets_at) and resets_at <= now
        windows.append(schema.window(
            "primary" if index == 0 else ("secondary" if index == 1 else "window-%d" % index),
            _kind(minutes),
            format.window_label(minutes),
            None if expired else format.clamp_percent(entry.get("percent")),
            resets_at,
            minutes=minutes,
        ))

    if not windows:
        return schema.provider_result(state="error", error="no_usage_data")

    # Lines that belong to no window but that the panel menu has always shown.
    details = []
    credits = raw.get("credits")
    if credits:
        details.append("Credits: %s" % (
            "unlimited" if credits.get("unlimited") else credits.get("balance")))
    if raw.get("limit_reached"):
        details.append("Limit reached: %s" % raw["limit_reached"])
    if raw.get("plan"):
        details.append("Plan: %s" % raw["plan"])

    return schema.provider_result(
        state="stale" if stale else "ok",
        windows=windows,
        source=source,
        fetched_at=int(fetched_at),
        age_seconds=raw.get("age_seconds") or 0,
        details=details,
    )
