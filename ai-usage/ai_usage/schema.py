"""The provider-neutral usage document: version 1.

One JSON document carries every provider, because a renderer that has to merge
two independent replies ends up reimplementing the merge twice — once in
JavaScript and once in GDScript. Each provider carries its own state, so a
partial success is an ordinary valid document rather than an error.

The document is display data only. Access tokens, refresh tokens, API keys and
the contents of credential files never appear here; tests/test_security.py holds
that line.
"""

VERSION = 1

STATES = ("ok", "stale", "unavailable", "error")
WINDOW_KINDS = ("session", "weekly", "model", "other")

_PROVIDER_FIELDS = (
    "state", "source", "fetched_at", "next_retry_at", "error", "age_seconds", "windows",
)
_WINDOW_FIELDS = ("id", "kind", "label", "minutes", "used_percent", "resets_at")


class ContractError(ValueError):
    """The document does not match version 1 and must not reach a renderer."""


def _require(condition, message):
    if not condition:
        raise ContractError(message)


def _unix_or_none(value, field):
    if value is None:
        return None
    # bool is an int in Python and would sail through an isinstance check.
    _require(isinstance(value, int) and not isinstance(value, bool),
             "%s must be Unix seconds or null, got %r" % (field, value))
    _require(value >= 0, "%s must not be negative, got %r" % (field, value))
    return value


def _percent_or_none(value):
    if value is None:
        return None
    _require(isinstance(value, (int, float)) and not isinstance(value, bool),
             "used_percent must be a number or null, got %r" % (value,))
    _require(0 <= value <= 100,
             "used_percent must be within 0..100, got %r" % (value,))
    return float(value)


def _validate_window(raw):
    _require(isinstance(raw, dict), "each entry of windows must be an object")
    for field in _WINDOW_FIELDS:
        _require(field in raw, "window is missing %s" % field)
    _require(isinstance(raw["id"], str) and raw["id"], "window id must be a non-empty string")
    _require(raw["kind"] in WINDOW_KINDS,
             "window kind must be one of %s, got %r" % (", ".join(WINDOW_KINDS), raw["kind"]))
    _require(isinstance(raw["label"], str) and raw["label"], "window label must be a non-empty string")
    minutes = raw["minutes"]
    if minutes is not None:
        _require(isinstance(minutes, int) and not isinstance(minutes, bool) and minutes > 0,
                 "window minutes must be a positive integer or null, got %r" % (minutes,))
    return {
        "id": raw["id"],
        "kind": raw["kind"],
        "label": raw["label"],
        "minutes": minutes,
        "used_percent": _percent_or_none(raw["used_percent"]),
        "resets_at": _unix_or_none(raw["resets_at"], "resets_at"),
    }


def _validate_provider(name, raw):
    _require(isinstance(raw, dict), "provider %s must be an object" % name)
    for field in _PROVIDER_FIELDS:
        _require(field in raw, "provider %s is missing %s" % (name, field))
    _require(raw["state"] in STATES,
             "provider %s has state %r, expected one of %s"
             % (name, raw["state"], ", ".join(STATES)))
    _require(isinstance(raw["windows"], list),
             "provider %s: windows must be a list" % name)
    # A provider claiming fresh numbers with nothing to show would render as a
    # confident blank; that is a producer bug, not something a renderer guesses at.
    _require(raw["state"] != "ok" or raw["windows"],
             "provider %s is ok but carries no windows" % name)
    source = raw["source"]
    _require(source is None or isinstance(source, str),
             "provider %s: source must be a string or null" % name)
    error = raw["error"]
    _require(error is None or isinstance(error, str),
             "provider %s: error must be a string or null" % name)
    details = raw.get("details") or []
    _require(isinstance(details, list) and all(isinstance(d, str) for d in details),
             "provider %s: details must be a list of strings" % name)
    age = raw["age_seconds"]
    _require(isinstance(age, int) and not isinstance(age, bool) and age >= 0,
             "provider %s: age_seconds must be a non-negative integer" % name)
    return {
        "state": raw["state"],
        "source": source,
        "fetched_at": _unix_or_none(raw["fetched_at"], "fetched_at"),
        "next_retry_at": _unix_or_none(raw["next_retry_at"], "next_retry_at"),
        "error": error,
        "age_seconds": age,
        "details": list(details),
        "windows": [_validate_window(w) for w in raw["windows"]],
    }


def validate(document):
    """Return the document reduced to the fields version 1 defines.

    Raises ContractError on anything a renderer must not trust. Unknown extra
    fields are dropped rather than rejected: a newer producer may add them, and
    a reader of this version has no use for them either way.
    """
    _require(isinstance(document, dict), "the usage document must be an object")
    _require(document.get("schema_version") == VERSION,
             "schema_version must be %d, got %r" % (VERSION, document.get("schema_version")))
    providers = document.get("providers")
    _require(isinstance(providers, dict), "providers must be an object")
    return {
        "schema_version": VERSION,
        "generated_at": _unix_or_none(document.get("generated_at"), "generated_at"),
        "providers": {name: _validate_provider(name, raw) for name, raw in providers.items()},
    }


def window(window_id, kind, label, used_percent, resets_at, minutes=None):
    """Build one window entry. Providers use this so the field set stays in one place."""
    return {
        "id": window_id,
        "kind": kind,
        "label": label,
        "minutes": minutes,
        "used_percent": used_percent,
        "resets_at": resets_at,
    }


def provider_result(state, windows=(), source=None, fetched_at=None,
                    next_retry_at=None, error=None, age_seconds=0, details=()):
    """Build one provider entry.

    `details` are extra display-only lines a provider happens to report — a
    Codex plan or credit balance — that belong to no window. Renderers are free
    to ignore them; the compact Godot HUD does.
    """
    return {
        "state": state,
        "source": source,
        "fetched_at": fetched_at,
        "next_retry_at": next_retry_at,
        "error": error,
        "age_seconds": int(max(0, age_seconds)),
        "details": list(details),
        "windows": list(windows),
    }


def document(providers, generated_at):
    return {
        "schema_version": VERSION,
        "generated_at": int(generated_at),
        "providers": providers,
    }
