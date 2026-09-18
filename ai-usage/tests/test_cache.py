"""Cache, lock and stale fallback (design.md D3).

The single-flight test is the one that matters: two clients polling the same
minute must cost one upstream request per provider, not two. It runs two real
processes against a helper that records every invocation.
"""

import json
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import unittest

from ai_usage import cache, schema

REPO = pathlib.Path(__file__).resolve().parent.parent

OK_DOC = {
    "schema_version": 1,
    "generated_at": 1757600000,
    "providers": {
        "claude": {
            "state": "ok", "source": "usage-endpoint", "fetched_at": 1757600000,
            "next_retry_at": None, "error": None, "age_seconds": 0,
            "windows": [{"id": "session", "kind": "session", "label": "Session (5 h)",
                         "minutes": 300, "used_percent": 74.0, "resets_at": 1757610000}],
        },
    },
}


def failed(error="network", next_retry_at=None):
    return schema.document(
        {"claude": schema.provider_result(state="error", error=error,
                                          next_retry_at=next_retry_at)},
        1757600100)


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        os.environ["AI_USAGE_CACHE_DIR"] = self.dir

    def tearDown(self):
        os.environ.pop("AI_USAGE_CACHE_DIR", None)

    def test_snapshot_survives_a_write_and_read_round_trip(self):
        cache.write_snapshot(OK_DOC)
        self.assertEqual(cache.read_snapshot(), schema.validate(OK_DOC))

    def test_snapshot_is_readable_only_by_its_owner(self):
        cache.write_snapshot(OK_DOC)
        mode = os.stat(os.path.join(self.dir, cache.SNAPSHOT_NAME)).st_mode
        self.assertEqual(stat.S_IMODE(mode), 0o600)

    def test_a_snapshot_of_another_version_is_ignored_rather_than_rendered(self):
        pathlib.Path(self.dir, cache.SNAPSHOT_NAME).write_text(
            json.dumps(dict(OK_DOC, schema_version=99)))
        self.assertIsNone(cache.read_snapshot())

    def test_a_corrupt_snapshot_is_ignored(self):
        pathlib.Path(self.dir, cache.SNAPSHOT_NAME).write_text("{ not json")
        self.assertIsNone(cache.read_snapshot())

    def test_freshness_window_is_sixty_seconds(self):
        self.assertTrue(cache.is_fresh(OK_DOC, 1757600059))
        self.assertFalse(cache.is_fresh(OK_DOC, 1757600060))


class MergeTest(unittest.TestCase):
    def test_a_failed_fetch_keeps_the_previous_numbers_as_stale(self):
        merged = cache.merge(schema.validate(OK_DOC), failed(), now=1757600100)
        entry = merged["providers"]["claude"]
        self.assertEqual(entry["state"], "stale")
        self.assertEqual(entry["windows"][0]["used_percent"], 74.0)
        self.assertEqual(entry["error"], "network")
        self.assertEqual(entry["age_seconds"], 100)

    def test_a_failure_before_any_success_stays_an_error(self):
        merged = cache.merge(None, failed(), now=1757600100)
        entry = merged["providers"]["claude"]
        self.assertEqual(entry["state"], "error")
        self.assertEqual(entry["windows"], [])

    def test_a_rate_limit_keeps_its_retry_time_on_the_kept_numbers(self):
        merged = cache.merge(schema.validate(OK_DOC),
                             failed("usage_http_429", next_retry_at=1757600400),
                             now=1757600100)
        self.assertEqual(merged["providers"]["claude"]["next_retry_at"], 1757600400)

    def test_a_fresh_reading_replaces_the_previous_one(self):
        newer = schema.validate(dict(OK_DOC, generated_at=1757600100))
        newer["providers"]["claude"]["windows"][0]["used_percent"] = 91.0
        merged = cache.merge(schema.validate(OK_DOC), newer, now=1757600100)
        self.assertEqual(merged["providers"]["claude"]["state"], "ok")
        self.assertEqual(merged["providers"]["claude"]["windows"][0]["used_percent"], 91.0)


class SingleFlightTest(unittest.TestCase):
    """Two clients, one minute, one upstream request per provider."""

    def setUp(self):
        self.helpers = tempfile.mkdtemp()
        self.cache = tempfile.mkdtemp()
        self.log = os.path.join(self.helpers, "calls.log")
        for name, payload in (
            ("claude-usage-helper.py",
             '{"ok": true, "percent": 74.0, "resets_at": "2026-09-11T15:00:00Z"}'),
            ("codex-usage-helper.py",
             '{"ok": true, "source": "app-server", "age_seconds": 0,'
             ' "windows": [{"minutes": 300, "percent": 42.0, "resets_at": 1789138800}]}'),
        ):
            path = pathlib.Path(self.helpers, name)
            path.write_text(
                "#!/usr/bin/env python3\n"
                "import sys, time\n"
                "open(%r, 'a').write(%r + '\\n')\n"
                "time.sleep(0.4)\n"
                "sys.stdout.write(%r)\n" % (self.log, name, payload))
            path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def run_clients(self, count):
        env = dict(os.environ,
                   AI_USAGE_HELPER_DIR=self.helpers,
                   AI_USAGE_CACHE_DIR=self.cache,
                   PYTHONPATH=str(REPO))
        running = [subprocess.Popen([sys.executable, "-m", "ai_usage"],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, env=env, cwd=str(REPO))
                   for _ in range(count)]
        return [p.communicate() for p in running]

    def calls(self, name):
        if not os.path.exists(self.log):
            return 0
        return open(self.log).read().split().count(name)

    def test_two_concurrent_clients_cost_one_upstream_call_each(self):
        answers = self.run_clients(2)
        for stdout, stderr in answers:
            document = schema.validate(json.loads(stdout))
            self.assertEqual(document["providers"]["claude"]["state"], "ok", stderr)
        self.assertEqual(self.calls("claude-usage-helper.py"), 1)
        self.assertEqual(self.calls("codex-usage-helper.py"), 1)

    def test_a_later_client_in_the_same_minute_adds_no_call(self):
        self.run_clients(1)
        self.run_clients(1)
        self.assertEqual(self.calls("claude-usage-helper.py"), 1)


if __name__ == "__main__":
    unittest.main()
