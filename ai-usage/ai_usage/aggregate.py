"""Fetch every provider once, concurrently, and answer with one document.

Sequential fetching would add the providers' timeouts together: Codex alone can
spend 20 seconds waiting for its app-server, and there is no reason for Claude's
answer to wait behind it. Each provider therefore runs in its own thread, and an
exception or a hang is contained in that provider's entry (design.md D4).
"""

import json
import os
import pathlib
import subprocess
import sys
import threading
import time

from . import schema
from .providers import claude, codex

PROVIDERS = (claude, codex)

DEFAULT_TIMEOUT = 25.0

# Installed next to the entry point; overridable for tests and development.
_DEFAULT_HELPER_DIR = pathlib.Path(__file__).resolve().parent / "helpers"


def default_helper_dir():
    return os.environ.get("AI_USAGE_HELPER_DIR") or str(_DEFAULT_HELPER_DIR)


def run_helper(path, timeout):
    """Run one vendor helper and return its reply as a dict.

    Failures are returned in the helpers' own `{"ok": false, "error": …}` shape
    so the adapter classifies them exactly as it classifies the helper's own
    reported failures.
    """
    if not os.path.exists(path):
        return {"ok": False, "error": "no_credentials"}
    try:
        done = subprocess.run(
            [sys.executable, path],
            capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    except OSError:
        return {"ok": False, "error": "helper"}

    text = (done.stdout or "").strip()
    if not text:
        return {"ok": False, "error": "helper"}
    try:
        reply = json.loads(text)
    except ValueError:
        return {"ok": False, "error": "parse"}
    if not isinstance(reply, dict):
        return {"ok": False, "error": "parse"}
    return reply


def collect(helper_dir=None, timeout=DEFAULT_TIMEOUT, now=None, skip=()):
    """One schema-v1 document covering every provider.

    `skip` names providers whose rate-limit pause has not expired; the caller
    fills those entries from the cache instead of asking upstream again.
    """
    directory = helper_dir or default_helper_dir()
    moment = time.time() if now is None else now
    skipped = set(skip or ())
    results = {}

    def fetch(module):
        path = os.path.join(directory, module.HELPER)
        try:
            raw = run_helper(path, timeout)
            results[module.ID] = module.normalise(raw, fetched_at=int(moment), now=int(moment))
        except Exception as exc:   # a broken adapter must not take the run down
            print("ai-usage: %s adapter failed: %s" % (module.ID, exc), file=sys.stderr)
            results[module.ID] = schema.provider_result(state="error", error="adapter")

    wanted = [m for m in PROVIDERS if m.ID not in skipped]
    threads = [threading.Thread(target=fetch, args=(m,), daemon=True) for m in wanted]
    for thread in threads:
        thread.start()
    for thread in threads:
        # Each fetch already carries its own timeout; this bound only covers a
        # thread that never returns at all.
        thread.join(timeout + 5)

    for module in wanted:
        results.setdefault(module.ID, schema.provider_result(state="error", error="timeout"))

    return schema.document(results, int(moment))
