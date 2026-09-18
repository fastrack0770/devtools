"""One fetch per minute, shared by every client (design.md D3).

The GNOME extension and the Godot Shell poll on their own timers, so without a
shared cache the same minute costs two upstream requests per provider. The cache
lives on disk rather than in each UI's memory, and a file lock turns concurrent
callers into one actual fetch: the second one waits, then finds the first one's
answer already fresh and returns it.

The last good reading is kept separately from the last failure. A provider that
fails after a successful fetch keeps its previous windows, marked stale and aged,
instead of blanking a working panel — and a rate limit's Retry-After is stored as
an absolute time, so polling stays paused across processes.

Nothing here is a secret: the snapshot holds the same display data the clients
render. It is still written owner-only, because a usage history is nobody else's
business on a shared machine.
"""

import errno
import fcntl
import json
import os
import pathlib
import tempfile
import time

from . import aggregate, schema

FRESH_SECONDS = 60
LOCK_WAIT_SECONDS = 30

SNAPSHOT_NAME = "usage-v1.json"
LOCK_NAME = "fetch.lock"


def cache_dir():
    override = os.environ.get("AI_USAGE_CACHE_DIR")
    if override:
        return pathlib.Path(override)
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return pathlib.Path(base) / "ai-usage-control"


def _snapshot_path():
    return cache_dir() / SNAPSHOT_NAME


def read_snapshot():
    """The last stored document, or None when there is nothing usable on disk."""
    try:
        raw = json.loads(_snapshot_path().read_text())
    except (OSError, ValueError):
        return None
    try:
        return schema.validate(raw)
    except schema.ContractError:
        # Written by another version, or corrupted: fetch afresh rather than
        # render numbers whose meaning is unknown.
        return None


def write_snapshot(document):
    directory = cache_dir()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    handle, temporary = tempfile.mkstemp(dir=str(directory), prefix=".usage-")
    try:
        with os.fdopen(handle, "w") as stream:
            json.dump(document, stream)
        os.chmod(temporary, 0o600)
        os.replace(temporary, str(_snapshot_path()))
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def is_fresh(document, now):
    generated = (document or {}).get("generated_at")
    return bool(generated) and 0 <= now - generated < FRESH_SECONDS


def _in_backoff(entry, now):
    retry_at = (entry or {}).get("next_retry_at")
    return bool(retry_at) and now < retry_at


def _aged(entry, now):
    """A previous entry re-presented as stale, with its age brought up to date."""
    fetched = entry.get("fetched_at")
    aged = dict(entry)
    aged["state"] = "stale" if entry["windows"] else entry["state"]
    aged["age_seconds"] = int(max(0, now - fetched)) if fetched else entry.get("age_seconds", 0)
    return aged


def merge(previous, fresh, now):
    """Keep a provider's last good numbers when its new fetch failed."""
    merged = dict(fresh)
    merged["providers"] = dict(fresh["providers"])
    old = (previous or {}).get("providers") or {}
    for name, entry in merged["providers"].items():
        if entry["state"] in ("ok", "stale"):
            continue
        before = old.get(name)
        if not before or not before["windows"] or before["state"] == "unavailable":
            continue
        kept = _aged(before, now)
        kept["error"] = entry["error"]
        kept["next_retry_at"] = entry["next_retry_at"]
        merged["providers"][name] = kept
    return merged


class _Lock:
    """Hold the fetch lock, or give up and let the caller serve what it has."""

    def __init__(self, path):
        self._path = path
        self._handle = None

    def __enter__(self):
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            self._handle = open(self._path, "a+")
            os.chmod(self._path, 0o600)
            deadline = time.time() + LOCK_WAIT_SECONDS
            while True:
                try:
                    fcntl.flock(self._handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return True
                except OSError as exc:
                    if exc.errno not in (errno.EACCES, errno.EAGAIN):
                        raise
                    if time.time() >= deadline:
                        return False
                    time.sleep(0.05)
        except OSError:
            return False

    def __exit__(self, *_exc):
        if self._handle is not None:
            try:
                fcntl.flock(self._handle, fcntl.LOCK_UN)
            finally:
                self._handle.close()
                self._handle = None


def usage(force=False, now=None):
    """The current usage document, fetching upstream only when it has to.

    `force` is the manual "Refresh now" path: it skips the freshness check and a
    provider's rate-limit pause is still honoured, because ignoring a Retry-After
    only earns the next 429.
    """
    moment = time.time() if now is None else now
    previous = read_snapshot()
    if not force and is_fresh(previous, moment):
        return previous

    lock = _Lock(cache_dir() / LOCK_NAME)
    with lock as acquired:
        if not acquired:
            # Someone else is already fetching; whatever we have beats waiting.
            return previous or schema.document({}, int(moment))

        # Re-read under the lock: the process we queued behind has just written
        # an answer, and fetching again would be exactly the duplicate request
        # this lock exists to prevent.
        previous = read_snapshot()
        if not force and is_fresh(previous, moment):
            return previous

        skip = {name for name, entry in ((previous or {}).get("providers") or {}).items()
                if _in_backoff(entry, moment)}
        fresh = aggregate.collect(now=moment, skip=skip)
        for name in skip:
            fresh["providers"][name] = _aged(previous["providers"][name], moment)

        document = merge(previous, fresh, moment)
        try:
            write_snapshot(document)
        except OSError:
            pass   # an unwritable cache costs a fetch, not an answer
        return document
