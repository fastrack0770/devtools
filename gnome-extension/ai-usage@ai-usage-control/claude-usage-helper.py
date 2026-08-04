#!/usr/bin/env python3
"""Fetch Claude Code session usage for the GNOME panel indicator.

Prints a single JSON line to stdout:
  {"ok": true, "percent": 43, "resets_at": "2026-07-24T18:00:00Z",
   "seven_day_percent": 12, "seven_day_resets_at": "...",
   "model_name": "Fable", "model_percent": 89, "model_resets_at": "...",
   "cli_version": "2.1.218", "config_source": "cache"}
or
  {"ok": false, "error": "<reason>"}

Every *_percent is the used share of that limit (0-100), not the remainder.

Reads the OAuth token from ~/.claude/.credentials.json (same source the
claude CLI uses for /usage). If the access token is expired, refreshes it
via the refresh token and writes the new tokens back atomically, preserving
every other key in the file. Tokens are never printed or logged.

Endpoints, OAuth client id and CLI version are read out of the installed
claude binary (see resolve_config) so that a CLI update carries them along;
the constants below are only the fallback.

Debug override: CU_FAKE_PERCENT env var or a number in
~/.cache/claude-usage-control/fake_percent replaces the session percent.
Env: CU_CLAUDE_BIN points at a specific claude binary,
CU_NO_CLI_DISCOVERY=1 skips the scan and uses the fallback constants.
"""

import fcntl
import json
import mmap
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

CREDS_PATH = os.path.expanduser("~/.claude/.credentials.json")
# shared with the codex helper and the indicator, hence the neutral name
CACHE_DIR = os.path.expanduser("~/.cache/ai-usage-control")
LOCK_PATH = os.path.join(CACHE_DIR, "creds.lock")
CLI_META_PATH = os.path.join(CACHE_DIR, "cli-meta.json")
BACKUP_PATH = CREDS_PATH + ".bak-claude-usage"

# Fallback config: what claude-cli 2.1.218 used. resolve_config() overrides
# each field it can read from the installed CLI.
DEFAULT_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
DEFAULT_TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
# Public OAuth client id of the Claude Code CLI itself
DEFAULT_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
DEFAULT_CLI_VERSION = "2.1.218"

OAUTH_BETA = "oauth-2025-04-20"

# A URL scraped out of a binary is only trusted if it stays on Anthropic's
# own domains — the refresh token is posted to token_url.
ALLOWED_DOMAINS = ("anthropic.com", "claude.com", "claude.ai")

EXPIRY_MARGIN_MS = 120 * 1000  # refresh if the token dies within 2 minutes


def fail(reason):
    out = {"ok": False, "error": reason}
    if _CONFIG is not None:  # which endpoints were tried, for debugging
        out["cli_version"] = _CONFIG["version"]
        out["config_source"] = _CONFIG["source"]
    print(json.dumps(out))
    sys.exit(0)


# --- CLI discovery -------------------------------------------------------
#
# The claude CLI ships as one big bundled binary with its OAuth config
# inlined as a literal object:
#
#   {BASE_API_URL:"https://api.anthropic.com", … ,
#    TOKEN_URL:"https://platform.claude.com/v1/oauth/token", … ,
#    CLIENT_ID:"9d1c250a-…"}
#
# plus a separate `"/api/oauth/usage"` path and a
# `PACKAGE_URL:"@anthropic-ai/claude-code",…,VERSION:"x.y.z"` pair. All three
# are matched as single anchored windows so the values are guaranteed to come
# from the same object — the binary also contains a templated staging block
# with a different client id.

VERSIONED_NAME_RE = re.compile(r"^\d+\.\d+\.\d+$")
BLOCK_RE = re.compile(
    rb'BASE_API_URL:"(https://[^"]{1,200})".{0,4000}?'
    rb'TOKEN_URL:"(https://[^"]{1,200})".{0,4000}?'
    rb'CLIENT_ID:"([0-9a-fA-F-]{36})"',
    re.S,
)
USAGE_PATH_RE = re.compile(rb'"(/[a-z0-9/_-]{0,60}oauth/usage)"')
VERSION_RE = re.compile(rb'VERSION:"(\d+\.\d+\.\d+)"')

PACKAGE_ANCHOR = b'PACKAGE_URL:"@anthropic-ai/claude-code"'


def find_cli():
    """Path of the claude binary, or None."""
    override = os.environ.get("CU_CLAUDE_BIN")
    if override:
        return os.path.realpath(override) if os.path.exists(override) else None

    found = shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")
    if os.path.exists(found):
        return os.path.realpath(found)

    # No launcher on PATH: fall back to the newest installed version.
    versions_dir = os.path.expanduser("~/.local/share/claude/versions")
    try:
        entries = [os.path.join(versions_dir, n) for n in os.listdir(versions_dir)]
    except OSError:
        return None
    entries = [p for p in entries if os.path.isfile(p)]
    if not entries:
        return None
    return max(entries, key=lambda p: os.stat(p).st_mtime)


def url_allowed(url):
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host:
        return False
    return any(host == d or host.endswith("." + d) for d in ALLOWED_DOMAINS)


def window_search(mm, anchor, pattern, before=0, after=4096):
    """Run `pattern` on a bounded window around each occurrence of `anchor`.

    Scanning the whole 250+ MB blob with a regex is slow; memchr-backed
    mm.find() is not, so anchor first and only then match.
    """
    pos = mm.find(anchor)
    while pos != -1:
        start = max(0, pos - before)
        m = pattern.search(mm[start:pos + len(anchor) + after])
        if m:
            return m
        pos = mm.find(anchor, pos + 1)
    return None


def scan_cli(path):
    """Extract {usage_url, token_url, client_id, version} from the binary.

    Returns only the fields it could read and validate; the caller fills the
    rest in from the defaults.
    """
    meta = {}
    name = os.path.basename(path)
    if VERSIONED_NAME_RE.match(name):
        meta["version"] = name  # ~/.local/share/claude/versions/<x.y.z>

    with open(path, "rb") as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            block = window_search(mm, b'BASE_API_URL:"', BLOCK_RE)
            if block:
                base, token_url, client_id = (g.decode() for g in block.groups())
                usage = window_search(mm, b"oauth/usage", USAGE_PATH_RE, before=80, after=8)
                if usage:
                    usage_url = base.rstrip("/") + usage.group(1).decode()
                    if url_allowed(usage_url):
                        meta["usage_url"] = usage_url
                # client_id only travels with a token_url we trust: the two
                # are posted together along with the refresh token.
                if url_allowed(token_url):
                    meta["token_url"] = token_url
                    meta["client_id"] = client_id
            if "version" not in meta:
                found = window_search(mm, PACKAGE_ANCHOR, VERSION_RE, after=400)
                if found:
                    meta["version"] = found.group(1).decode()
    return meta


def load_cli_meta(path, stamp):
    try:
        with open(CLI_META_PATH) as f:
            cached = json.load(f)
    except (OSError, ValueError):
        return None
    if cached.get("path") == path and cached.get("stamp") == stamp:
        return cached.get("meta")
    return None


def save_cli_meta(path, stamp, meta):
    try:
        os.makedirs(CACHE_DIR, mode=0o700, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=CACHE_DIR, prefix=".cli-meta-")
        with os.fdopen(fd, "w") as f:
            json.dump({"path": path, "stamp": stamp, "meta": meta}, f)
        os.replace(tmp, CLI_META_PATH)
    except OSError:
        pass  # a stale-free cache is nice to have, not required


def resolve_config():
    """Endpoints to use: the installed CLI's, falling back to the constants.

    The scan result is cached under the binary's path+mtime+size, so it only
    re-runs after the CLI is updated or reinstalled.
    """
    config = {
        "usage_url": DEFAULT_USAGE_URL,
        "token_url": DEFAULT_TOKEN_URL,
        "client_id": DEFAULT_CLIENT_ID,
        "version": DEFAULT_CLI_VERSION,
        "source": "defaults",
    }
    if os.environ.get("CU_NO_CLI_DISCOVERY"):
        return config

    path = find_cli()
    if not path:
        return config
    try:
        st = os.stat(path)
    except OSError:
        return config
    stamp = "%d:%d" % (st.st_mtime_ns, st.st_size)

    meta = load_cli_meta(path, stamp)
    source = "cache"
    if meta is None:
        try:
            meta = scan_cli(path)
        except (OSError, ValueError):
            return config
        save_cli_meta(path, stamp, meta)
        source = "cli"

    if meta:
        config.update(meta)
        config["source"] = source
    return config


_CONFIG = None


def config():
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = resolve_config()
    return _CONFIG


def user_agent():
    return "claude-cli/%s (external, cli)" % config()["version"]


# --- usage ---------------------------------------------------------------


def read_creds():
    with open(CREDS_PATH) as f:
        return json.load(f)


def token_valid(oauth):
    return oauth.get("expiresAt", 0) > time.time() * 1000 + EXPIRY_MARGIN_MS


def http_json(url, data=None, headers=None):
    body = json.dumps(data).encode() if data is not None else None
    all_headers = {"User-Agent": user_agent(), "Accept": "application/json"}
    all_headers.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=all_headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def refresh_token():
    """Refresh the access token and persist it back to credentials.json.

    The lock only serializes concurrent runs of this helper; the claude CLI
    rewrites the file independently, so re-read under the lock and skip the
    refresh if the CLI already did it.
    """
    os.makedirs(CACHE_DIR, mode=0o700, exist_ok=True)
    with open(LOCK_PATH, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)

        creds = read_creds()
        oauth = creds.get("claudeAiOauth") or {}
        if token_valid(oauth):
            return oauth  # someone else refreshed while we waited

        refresh = oauth.get("refreshToken")
        if not refresh:
            fail("no_refresh_token")
        if oauth.get("refreshTokenExpiresAt", float("inf")) < time.time() * 1000:
            fail("refresh_token_expired")

        try:
            resp = http_json(
                config()["token_url"],
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                    "client_id": config()["client_id"],
                },
                headers={"Content-Type": "application/json"},
            )
        except urllib.error.HTTPError as e:
            # The body carries the reason; invalid_grant means the refresh
            # token is dead (expired, revoked, or already rotated on another
            # machine) and only a new `claude /login` brings it back.
            try:
                detail = json.loads(e.read().decode()).get("error")
            except (ValueError, OSError):
                detail = None
            if detail == "invalid_grant":
                fail("refresh_token_expired")
            fail("refresh_http_%d" % e.code)
        except OSError:
            fail("network")

        oauth["accessToken"] = resp["access_token"]
        if resp.get("refresh_token"):
            oauth["refreshToken"] = resp["refresh_token"]
        oauth["expiresAt"] = int(time.time() * 1000 + resp.get("expires_in", 3600) * 1000)
        creds["claudeAiOauth"] = oauth

        if not os.path.exists(BACKUP_PATH):
            shutil.copy2(CREDS_PATH, BACKUP_PATH)
            os.chmod(BACKUP_PATH, 0o600)

        creds_dir = os.path.dirname(CREDS_PATH)
        fd, tmp = tempfile.mkstemp(dir=creds_dir, prefix=".credentials-")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(creds, f)
            os.chmod(tmp, 0o600)
            os.replace(tmp, CREDS_PATH)
        except BaseException:
            os.unlink(tmp)
            raise
        return oauth


def get_usage(access_token):
    return http_json(
        config()["usage_url"],
        headers={
            "Authorization": "Bearer " + access_token,
            "anthropic-beta": OAUTH_BETA,
            "Content-Type": "application/json",
        },
    )


def find_window(data, name):
    """Locate a usage window (dict with 'utilization') for key `name`,
    searching nested dicts defensively since the response shape is unversioned."""
    if isinstance(data, dict):
        for k, v in data.items():
            if name in str(k) and isinstance(v, dict) and "utilization" in v:
                return v
        for v in data.values():
            found = find_window(v, name)
            if found:
                return found
    return None


def fake_percent():
    val = os.environ.get("CU_FAKE_PERCENT")
    if val is None:
        try:
            with open(os.path.join(CACHE_DIR, "fake_percent")) as f:
                val = f.read().strip()
        except OSError:
            return None
    try:
        return max(0.0, min(100.0, float(val)))
    except ValueError:
        return None


def main():
    try:
        creds = read_creds()
    except (OSError, ValueError):
        fail("no_credentials")

    oauth = creds.get("claudeAiOauth")
    if not oauth or not oauth.get("accessToken"):
        fail("not_logged_in")

    if not token_valid(oauth):
        oauth = refresh_token()

    try:
        data = get_usage(oauth["accessToken"])
    except urllib.error.HTTPError as e:
        if e.code == 401:
            # token was marked valid but rejected: force one refresh and retry
            oauth["expiresAt"] = 0
            creds["claudeAiOauth"] = oauth
            oauth = refresh_token()
            try:
                data = get_usage(oauth["accessToken"])
            except (urllib.error.HTTPError, OSError):
                fail("unauthorized")
        else:
            fail("usage_http_%d" % e.code)
    except OSError:
        fail("network")

    # Primary source: the `limits` array (has session, weekly_all and
    # model-scoped weekly limits like Fable). Fall back to the legacy
    # five_hour/seven_day windows if it is absent.
    session = week = model = None
    for lim in data.get("limits") or []:
        if not isinstance(lim, dict):
            continue
        kind = lim.get("kind")
        if kind == "session":
            session = lim
        elif kind == "weekly_all":
            week = lim
        else:
            scope = lim.get("scope") or {}
            name = (scope.get("model") or {}).get("display_name")
            if name and model is None:
                model = dict(lim, model_name=name)

    if not session:
        w = find_window(data, "five_hour")
        if w:
            session = {"percent": w.get("utilization", 0), "resets_at": w.get("resets_at")}
    if not week:
        w = find_window(data, "seven_day")
        if w:
            week = {"percent": w.get("utilization", 0), "resets_at": w.get("resets_at")}
    if not session:
        fail("no_session_window")

    percent = fake_percent()
    if percent is None:
        percent = float(session.get("percent", 0))
    percent = max(0.0, min(100.0, percent))

    out = {
        "ok": True,
        "percent": round(percent, 1),
        "resets_at": session.get("resets_at"),
        "cli_version": config()["version"],
        "config_source": config()["source"],
    }
    if week:
        out["seven_day_percent"] = round(float(week.get("percent", 0)), 1)
        out["seven_day_resets_at"] = week.get("resets_at")
    if model:
        out["model_name"] = model["model_name"]
        out["model_percent"] = round(float(model.get("percent", 0)), 1)
        out["model_resets_at"] = model.get("resets_at")
    print(json.dumps(out))


if __name__ == "__main__":
    main()
