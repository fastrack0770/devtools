"""Claude Code usage: the helper's reply turned into schema-v1 windows.

The bar tracks the 5-hour session window — the shortest one Claude reports —
and the weekly and model-scoped quotas follow it in order. This ordering used
to live in the extension's aiusagelib/claude.js.
"""

from .. import format, schema
from . import common

ID = "claude"
TITLE = "Claude"
HELPER = "claude-usage-helper.py"

SESSION_MINUTES = 300
WEEK_MINUTES = 10080


def normalise(raw, fetched_at, now=None):
    """One provider entry from one helper reply."""
    now = fetched_at if now is None else now
    if not raw.get("ok"):
        reason = raw.get("error") or "helper"
        return schema.provider_result(
            state=common.failure_state(reason),
            error=reason,
            next_retry_at=common.next_retry_at(reason, raw.get("retry_after"), now),
        )

    windows = [schema.window(
        "session", "session", "Session (5 h)",
        format.clamp_percent(raw.get("percent")),
        format.iso_to_unix(raw.get("resets_at")),
        minutes=SESSION_MINUTES,
    )]

    if raw.get("seven_day_percent") is not None:
        windows.append(schema.window(
            "weekly_all", "weekly", "Week",
            format.clamp_percent(raw.get("seven_day_percent")),
            format.iso_to_unix(raw.get("seven_day_resets_at")),
            minutes=WEEK_MINUTES,
        ))

    if raw.get("model_percent") is not None:
        name = raw.get("model_name") or "model"
        windows.append(schema.window(
            "model:%s" % name.lower().replace(" ", "-"), "model", name,
            format.clamp_percent(raw.get("model_percent")),
            format.iso_to_unix(raw.get("model_resets_at")),
            minutes=WEEK_MINUTES,
        ))

    return schema.provider_result(
        state="ok", windows=windows, source="usage-endpoint", fetched_at=int(fetched_at))
