"""What both adapters do the same way: failure classification and backoff.

A provider that was never set up is not a fault the user needs to act on, so it
is reported as `unavailable` and rendered without an alarm. Anything else that
stopped a fetch is an `error`, and a rate limit additionally carries the time
the next automatic attempt is allowed.
"""

DEFAULT_BACKOFF_SECONDS = 300
MAX_BACKOFF_SECONDS = 3600

# Reasons that mean "this CLI is not set up here", not "something went wrong".
UNAVAILABLE_REASONS = (
    "no_credentials",
    "not_logged_in",
    "no_codex_cli",
)


def is_rate_limit(reason):
    """Both Claude endpoints report a 429 under their own code; match the shape."""
    return isinstance(reason, str) and reason.endswith("_http_429")


def backoff_seconds(retry_after):
    """Prefer the server's own Retry-After; cap it so one absurd header cannot freeze polling."""
    try:
        value = float(retry_after)
    except (TypeError, ValueError):
        return DEFAULT_BACKOFF_SECONDS
    if value <= 0:
        return DEFAULT_BACKOFF_SECONDS
    return min(int(value), MAX_BACKOFF_SECONDS)


def failure_state(reason):
    return "unavailable" if reason in UNAVAILABLE_REASONS else "error"


def next_retry_at(reason, retry_after, now):
    if not is_rate_limit(reason):
        return None
    return int(now) + backoff_seconds(retry_after)
