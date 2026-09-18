"""The one-shot `ai-usage` command (design.md D3, D4).

Each provider is fetched in its own thread against a real subprocess, so the
slow one does not hold back the one that already answered, and a provider that
crashes or hangs is reported inside its own entry rather than failing the run.
"""

import json
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import time
import unittest

from ai_usage import aggregate, schema

REPO = pathlib.Path(__file__).resolve().parent.parent

CLAUDE_REPLY = json.dumps({
    "ok": True, "percent": 74.0, "resets_at": "2026-09-11T15:00:00Z",
})
CODEX_REPLY = json.dumps({
    "ok": True, "source": "app-server", "age_seconds": 0,
    "windows": [{"minutes": 300, "percent": 42.0, "resets_at": 1789138800}],
})


def write_helper(directory, name, body):
    path = pathlib.Path(directory) / name
    path.write_text("#!/usr/bin/env python3\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def echo_helper(payload):
    return "import sys\nsys.stdout.write(%r)\n" % payload


def slow_helper(payload, seconds):
    return "import sys, time\ntime.sleep(%r)\nsys.stdout.write(%r)\n" % (seconds, payload)


class CollectTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def test_both_providers_are_reported_in_one_valid_document(self):
        write_helper(self.dir, "claude-usage-helper.py", echo_helper(CLAUDE_REPLY))
        write_helper(self.dir, "codex-usage-helper.py", echo_helper(CODEX_REPLY))
        doc = aggregate.collect(helper_dir=self.dir, timeout=10)
        schema.validate(doc)
        self.assertEqual(doc["providers"]["claude"]["state"], "ok")
        self.assertEqual(doc["providers"]["codex"]["state"], "ok")

    def test_one_provider_failing_leaves_the_other_intact(self):
        write_helper(self.dir, "claude-usage-helper.py",
                     "import sys; sys.exit('boom')\n")
        write_helper(self.dir, "codex-usage-helper.py", echo_helper(CODEX_REPLY))
        doc = aggregate.collect(helper_dir=self.dir, timeout=10)
        schema.validate(doc)
        self.assertEqual(doc["providers"]["claude"]["state"], "error")
        self.assertEqual(doc["providers"]["codex"]["state"], "ok")
        self.assertEqual(doc["providers"]["codex"]["windows"][0]["used_percent"], 42.0)

    def test_unparseable_helper_output_is_reported_as_a_parse_error(self):
        write_helper(self.dir, "claude-usage-helper.py", echo_helper("not json at all"))
        write_helper(self.dir, "codex-usage-helper.py", echo_helper(CODEX_REPLY))
        doc = aggregate.collect(helper_dir=self.dir, timeout=10)
        self.assertEqual(doc["providers"]["claude"]["error"], "parse")

    def test_a_hanging_provider_times_out_without_taking_the_run_with_it(self):
        write_helper(self.dir, "claude-usage-helper.py", slow_helper(CLAUDE_REPLY, 30))
        write_helper(self.dir, "codex-usage-helper.py", echo_helper(CODEX_REPLY))
        doc = aggregate.collect(helper_dir=self.dir, timeout=1)
        self.assertEqual(doc["providers"]["claude"]["error"], "timeout")
        self.assertEqual(doc["providers"]["codex"]["state"], "ok")

    def test_providers_are_fetched_concurrently_not_one_after_the_other(self):
        write_helper(self.dir, "claude-usage-helper.py", slow_helper(CLAUDE_REPLY, 2))
        write_helper(self.dir, "codex-usage-helper.py", slow_helper(CODEX_REPLY, 2))
        started = time.monotonic()
        doc = aggregate.collect(helper_dir=self.dir, timeout=10)
        elapsed = time.monotonic() - started
        self.assertEqual(doc["providers"]["claude"]["state"], "ok")
        self.assertEqual(doc["providers"]["codex"]["state"], "ok")
        self.assertLess(elapsed, 3.5, "two 2s providers ran sequentially (%.1fs)" % elapsed)

    def test_missing_helper_is_reported_as_unavailable(self):
        doc = aggregate.collect(helper_dir=self.dir, timeout=5)
        self.assertEqual(doc["providers"]["claude"]["state"], "unavailable")
        self.assertEqual(doc["providers"]["codex"]["state"], "unavailable")


class CommandTest(unittest.TestCase):
    """The installed entry point: exactly one JSON document on stdout."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.cache = tempfile.mkdtemp()
        write_helper(self.dir, "claude-usage-helper.py", echo_helper(CLAUDE_REPLY))
        write_helper(self.dir, "codex-usage-helper.py",
                     "import sys; raise RuntimeError('helper exploded')\n")

    def run_command(self):
        env = dict(os.environ,
                   AI_USAGE_HELPER_DIR=self.dir,
                   AI_USAGE_CACHE_DIR=self.cache,
                   PYTHONPATH=str(REPO))
        return subprocess.run([sys.executable, "-m", "ai_usage"],
                              capture_output=True, text=True, env=env, cwd=str(REPO))

    def test_stdout_is_exactly_one_json_document(self):
        done = self.run_command()
        self.assertEqual(done.returncode, 0, done.stderr)
        doc = json.loads(done.stdout)
        schema.validate(doc)

    def test_a_crashing_helper_leaves_no_traceback_on_stdout(self):
        done = self.run_command()
        self.assertNotIn("Traceback", done.stdout)
        self.assertNotIn("helper exploded", done.stdout)
        self.assertEqual(json.loads(done.stdout)["providers"]["codex"]["state"], "error")


if __name__ == "__main__":
    unittest.main()
