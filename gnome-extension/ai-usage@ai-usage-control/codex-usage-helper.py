#!/usr/bin/env python3
"""Fetch Codex CLI subscription rate limits for the GNOME panel indicator.

Prints a single JSON line to stdout:
  {"ok": true, "source": "app-server", "age_seconds": 0,
   "windows": [{"minutes": 10080, "percent": 2.0, "resets_at": 1786436609}],
   "plan": "plus", "credits": {"balance": "0", "unlimited": false},
   "limit_reached": null, "codex_version": "0.146.0"}
or
  {"ok": false, "error": "<reason>"}

Every percent is the used share of that limit (0-100), not the remainder.
`resets_at` is Unix seconds. `windows` carries whatever windows the server
actually sent — Codex reports one or two, and which ones depends on the
plan, so nothing here assumes a fixed 5-hour/weekly pair.

Two sources, in order:

1. `codex app-server --stdio`, JSON-RPC method `account/rateLimits/read`.
   Authoritative and current. Codex itself owns the OAuth token and its
   refresh, so this helper never reads or rewrites ~/.codex/auth.json —
   the refresh token there rotates, and a second writer racing the CLI
   can log the user out of Codex. The call reaches a usage endpoint, not
   the model, so it costs no inference tokens. A one-shot spawn answers
   in ~1 s, which is why no long-lived child process is needed.

2. The newest `token_count` event carrying `rate_limits` in
   ~/.codex/sessions/**/rollout-*.jsonl. Free and local, but only written
   while Codex is running, so it is a stale snapshot — `age_seconds` says
   how stale, and the panel dims the bar accordingly.

Env: CU_CODEX_BIN points at a specific codex binary,
CU_CODEX_NO_APPSERVER=1 skips source 1 (to exercise the fallback),
CU_CODEX_FAKE_PERCENT overrides the percent of every window.
"""

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

CODEX_HOME = os.path.expanduser("~/.codex")
AUTH_PATH = os.path.join(CODEX_HOME, "auth.json")
SESSIONS_DIR = os.path.join(CODEX_HOME, "sessions")

RPC_TIMEOUT = 20.0
# Enough of a rollout file's tail to hold a token_count event; they are
# appended to for the whole session, so reading all of it would be waste.
TAIL_BYTES = 512 * 1024
ROLLOUT_FILES_CHECKED = 8

USER_AGENT_VERSION_RE = re.compile(r"/(\d+\.\d+\.\d+)")


def emit(obj):
    print(json.dumps(obj))
    sys.exit(0)


def fail(reason):
    emit({"ok": False, "error": reason})


def find_codex():
    """Path of the codex binary, or None."""
    override = os.environ.get("CU_CODEX_BIN")
    if override:
        return override if os.path.exists(override) else None
    found = shutil.which("codex")
    if found:
        return found
    fallback = os.path.expanduser("~/.local/bin/codex")
    return fallback if os.path.exists(fallback) else None


def fake_percent():
    val = os.environ.get("CU_CODEX_FAKE_PERCENT")
    if val is None:
        return None
    try:
        return max(0.0, min(100.0, float(val)))
    except ValueError:
        return None


# --- source 1: app-server ------------------------------------------------


def query_app_server(binary):
    """{'rate_limits': …, 'version': …} from the app-server, or None.

    Newline-delimited JSON-RPC. Responses come back without the
    `"jsonrpc": "2.0"` member, so frames are matched on `id` alone, and
    unsolicited notifications (remoteControl/status/changed and friends)
    are simply skipped.
    """
    try:
        proc = subprocess.Popen(
            [binary, "app-server", "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
    except OSError:
        return None

    # Reading the child's stdout blocks, and a deadline checked inside the
    # loop would only be consulted once a line already arrived — i.e. never,
    # in the case that matters. An app-server that answers nothing and does
    # not exit would hang this helper forever and the panel would pile up one
    # stuck process per poll, so the timeout has to come from outside: kill
    # the child and the iteration below ends at EOF.
    watchdog = threading.Timer(RPC_TIMEOUT, proc.kill)
    watchdog.daemon = True
    watchdog.start()

    try:
        request = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"clientInfo": {"name": "ai-usage",
                                       "title": "AI Usage GNOME indicator",
                                       "version": "1.0.0"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "account/rateLimits/read",
             "params": {}},
        ]
        try:
            for msg in request:
                proc.stdin.write(json.dumps(msg) + "\n")
            proc.stdin.flush()
        except OSError:
            return None

        version = None
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg.get("id") == 1:
                agent = (msg.get("result") or {}).get("userAgent") or ""
                found = USER_AGENT_VERSION_RE.search(agent)
                if found:
                    version = found.group(1)
            elif msg.get("id") == 2:
                if "result" not in msg:
                    return None
                limits = (msg["result"] or {}).get("rateLimits")
                if not limits:
                    return None
                return {"rate_limits": limits, "version": version}
        return None
    finally:
        watchdog.cancel()
        # The app-server has no shutdown RPC; closing stdin and killing it
        # is the intended exit for a one-shot query.
        try:
            proc.stdin.close()
        except OSError:
            pass
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


# --- source 2: rollout journal -------------------------------------------


def parse_iso(stamp):
    """Unix seconds from an ISO-8601 timestamp, or None."""
    if not isinstance(stamp, str):
        return None
    text = stamp.strip().replace("Z", "+00:00")
    try:
        import datetime

        return datetime.datetime.fromisoformat(text).timestamp()
    except (ValueError, ImportError):
        return None


def read_rollout():
    """{'rate_limits': …, 'recorded_at': …} from the newest snapshot, or None."""
    pattern = os.path.join(SESSIONS_DIR, "**", "rollout-*.jsonl")
    try:
        files = glob.glob(pattern, recursive=True)
    except OSError:
        return None
    if not files:
        return None

    dated = []
    for path in files:
        try:
            dated.append((os.stat(path).st_mtime, path))
        except OSError:
            continue
    dated.sort(reverse=True)

    # The newest file does not necessarily hold the newest snapshot: a
    # rollout's mtime moves on every appended event, most of which are not
    # token_count, so a session that merely saw a user message last can
    # outrank one whose rate-limit snapshot is genuinely more recent. With
    # two Codex sessions open that picks the wrong numbers, so all the
    # candidates are scanned and compared on their own timestamps.
    best = None
    for mtime, path in dated[:ROLLOUT_FILES_CHECKED]:
        found = scan_rollout(path)
        if not found:
            continue
        if found["recorded_at"] is None:
            found["recorded_at"] = mtime
        if best is None or found["recorded_at"] > best["recorded_at"]:
            best = found
    return best


def scan_rollout(path):
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            if size > TAIL_BYTES:
                f.seek(size - TAIL_BYTES)
                f.readline()  # drop the partial line the seek landed in
            chunk = f.read()
    except OSError:
        return None

    for raw in reversed(chunk.splitlines()):
        try:
            event = json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict) or payload.get("type") != "token_count":
            continue
        limits = payload.get("rate_limits")
        if not limits:
            continue
        return {"rate_limits": limits, "recorded_at": parse_iso(event.get("timestamp"))}
    return None


# --- normalisation -------------------------------------------------------


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def read_window(raw):
    """One window in our own shape, or None.

    The app-server speaks camelCase (usedPercent/windowDurationMins/resetsAt)
    and the rollout journal snake_case (used_percent/window_minutes/
    resets_at); both spellings are accepted so the two sources produce
    identical output.
    """
    if not isinstance(raw, dict):
        return None
    percent = number(raw.get("usedPercent"))
    if percent is None:
        percent = number(raw.get("used_percent"))
    minutes = number(raw.get("windowDurationMins"))
    if minutes is None:
        minutes = number(raw.get("window_minutes"))
    if percent is None or not minutes:
        return None
    resets = number(raw.get("resetsAt"))
    if resets is None:
        resets = number(raw.get("resets_at"))
    return {
        "minutes": int(minutes),
        "percent": round(max(0.0, min(100.0, percent)), 1),
        "resets_at": int(resets) if resets else None,
    }


def read_credits(raw):
    if not isinstance(raw, dict):
        return None
    balance = raw.get("balance")
    unlimited = raw.get("unlimited")
    has_credits = raw.get("hasCredits")
    if has_credits is None:
        has_credits = raw.get("has_credits")
    if balance is None and not unlimited:
        return None
    return {
        "balance": str(balance) if balance is not None else "0",
        "unlimited": bool(unlimited),
        "has_credits": bool(has_credits),
    }


def normalise(limits, source, age_seconds, version):
    windows = []
    for key in ("primary", "secondary"):
        window = read_window(limits.get(key))
        if window:
            windows.append(window)
    if not windows:
        return None

    override = fake_percent()
    if override is not None:
        for window in windows:
            window["percent"] = override

    # shortest window first: that is the one the panel bar tracks
    windows.sort(key=lambda w: w["minutes"])

    plan = limits.get("planType")
    if plan is None:
        plan = limits.get("plan_type")
    reached = limits.get("rateLimitReachedType")
    if reached is None:
        reached = limits.get("rate_limit_reached_type")

    out = {
        "ok": True,
        "source": source,
        "age_seconds": int(max(0, age_seconds)),
        "windows": windows,
        "limit_reached": reached,
    }
    if plan:
        out["plan"] = plan
    credits = read_credits(limits.get("credits"))
    if credits:
        out["credits"] = credits
    if version:
        out["codex_version"] = version
    return out


def main():
    if not os.path.exists(AUTH_PATH):
        fail("no_credentials")

    binary = find_codex()

    if binary and not os.environ.get("CU_CODEX_NO_APPSERVER"):
        answer = query_app_server(binary)
        if answer:
            out = normalise(answer["rate_limits"], "app-server", 0, answer["version"])
            if out:
                emit(out)

    snapshot = read_rollout()
    if snapshot:
        age = time.time() - (snapshot["recorded_at"] or 0)
        out = normalise(snapshot["rate_limits"], "rollout", age, None)
        if out:
            emit(out)

    if not binary:
        fail("no_codex_cli")
    fail("no_usage_data")


if __name__ == "__main__":
    main()
