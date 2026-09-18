"""No credential ever reaches a renderer (spec: Общий безопасный контракт данных).

The Godot Shell is not given API keys, and the usage document is the only thing
it reads. So a helper that leaks a token into its reply — by adding a debug
field, or by echoing the upstream body — must not get that token any further
than the helper's own process. Markers are planted in every credential-shaped
field the helpers are known to touch and searched for in stdout, stderr and the
on-disk cache.
"""

import json
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent

ACCESS_MARKER = "MARKER-ACCESS-TOKEN-6f1a"
REFRESH_MARKER = "MARKER-REFRESH-TOKEN-9c2b"
APIKEY_MARKER = "MARKER-API-KEY-3d7e"
MARKERS = (ACCESS_MARKER, REFRESH_MARKER, APIKEY_MARKER)

CREDENTIAL_FIELDS = (
    "accessToken", "access_token", "refreshToken", "refresh_token",
    "apiKey", "api_key", "claudeAiOauth", "credentials", "authorization",
    "Authorization", "id_token", "client_secret",
)

LEAKY_SUCCESS = {
    "ok": True,
    "percent": 74.0,
    "resets_at": "2026-09-11T15:00:00Z",
    "access_token": ACCESS_MARKER,
    "refreshToken": REFRESH_MARKER,
    "apiKey": APIKEY_MARKER,
    "claudeAiOauth": {"accessToken": ACCESS_MARKER},
}

LEAKY_FAILURE = {
    "ok": False,
    "error": "unauthorized",
    "detail": "rejected token %s" % ACCESS_MARKER,
    "credentials": {"refresh_token": REFRESH_MARKER, "api_key": APIKEY_MARKER},
}

LEAKY_CODEX = {
    "ok": True,
    "source": "app-server",
    "age_seconds": 0,
    "windows": [{"minutes": 300, "percent": 42.0, "resets_at": 1789138800,
                 "authorization": "Bearer %s" % ACCESS_MARKER}],
    "auth": {"id_token": REFRESH_MARKER},
}


class LeakTest(unittest.TestCase):
    def setUp(self):
        self.helpers = tempfile.mkdtemp()
        self.cache = tempfile.mkdtemp()

    def write_helper(self, name, payload):
        path = pathlib.Path(self.helpers, name)
        path.write_text("#!/usr/bin/env python3\nimport sys\nsys.stdout.write(%r)\n"
                        % json.dumps(payload))
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def run_command(self):
        env = dict(os.environ,
                   AI_USAGE_HELPER_DIR=self.helpers,
                   AI_USAGE_CACHE_DIR=self.cache,
                   PYTHONPATH=str(REPO))
        done = subprocess.run([sys.executable, "-m", "ai_usage"],
                              capture_output=True, text=True, env=env, cwd=str(REPO))
        cached = ""
        snapshot = pathlib.Path(self.cache, "usage-v1.json")
        if snapshot.exists():
            cached = snapshot.read_text()
        return done.stdout, done.stderr, cached

    def assert_clean(self, *streams):
        for label, text in zip(("stdout", "stderr", "cache"), streams):
            for marker in MARKERS:
                self.assertNotIn(marker, text, "%s carried %s" % (label, marker))
            for field in CREDENTIAL_FIELDS:
                self.assertNotIn(field, text, "%s carried the field %s" % (label, field))

    def test_a_successful_reply_carries_no_credentials_onward(self):
        self.write_helper("claude-usage-helper.py", LEAKY_SUCCESS)
        self.write_helper("codex-usage-helper.py", LEAKY_CODEX)
        stdout, stderr, cached = self.run_command()
        self.assertEqual(json.loads(stdout)["providers"]["claude"]["state"], "ok")
        self.assert_clean(stdout, stderr, cached)

    def test_an_error_reply_carries_no_credentials_onward(self):
        self.write_helper("claude-usage-helper.py", LEAKY_FAILURE)
        self.write_helper("codex-usage-helper.py", LEAKY_FAILURE)
        stdout, stderr, cached = self.run_command()
        self.assertEqual(json.loads(stdout)["providers"]["claude"]["state"], "error")
        self.assert_clean(stdout, stderr, cached)

    def test_a_stale_fallback_carries_no_credentials_onward(self):
        self.write_helper("claude-usage-helper.py", LEAKY_SUCCESS)
        self.write_helper("codex-usage-helper.py", LEAKY_CODEX)
        self.run_command()
        # Same cache, now failing: the kept numbers must stay just as clean.
        self.write_helper("claude-usage-helper.py", LEAKY_FAILURE)
        snapshot = pathlib.Path(self.cache, "usage-v1.json")
        document = json.loads(snapshot.read_text())
        document["generated_at"] = 0          # force the next run past the freshness window
        snapshot.write_text(json.dumps(document))
        stdout, stderr, cached = self.run_command()
        self.assertEqual(json.loads(stdout)["providers"]["claude"]["state"], "stale")
        self.assert_clean(stdout, stderr, cached)


if __name__ == "__main__":
    unittest.main()
