"""Provider adapters: vendor reply in, schema-v1 windows out (design.md D2).

These are the parsers that used to live in the extension's JavaScript. They are
tested here on the raw shapes each vendor actually returns, so that a vendor
change is fixed once, in Python, rather than twice in two languages.
"""

import unittest

from ai_usage import schema
from ai_usage.providers import claude, codex

CLAUDE_RAW = {
    "ok": True,
    "percent": 74.0,
    "resets_at": "2026-09-11T15:00:00Z",
    "seven_day_percent": 31.5,
    "seven_day_resets_at": "2026-09-16T00:00:00Z",
    "model_name": "Fable",
    "model_percent": 12.0,
    "model_resets_at": "2026-09-16T00:00:00Z",
}

CODEX_RAW = {
    "ok": True,
    "source": "app-server",
    "age_seconds": 0,
    "windows": [
        {"minutes": 300, "percent": 42.0, "resets_at": 1757610000},
        {"minutes": 10080, "percent": 88.0, "resets_at": 1758000000},
    ],
    "plan": "plus",
}


class ClaudeNormaliseTest(unittest.TestCase):
    def test_session_window_comes_first_and_carries_the_used_share(self):
        result = claude.normalise(CLAUDE_RAW, fetched_at=1757600000)
        self.assertEqual(result["state"], "ok")
        first = result["windows"][0]
        self.assertEqual(first["id"], "session")
        self.assertEqual(first["kind"], "session")
        self.assertEqual(first["minutes"], 300)
        self.assertEqual(first["used_percent"], 74.0)
        self.assertEqual(first["resets_at"], 1789138800)   # date -u -d 2026-09-11T15:00:00Z +%s

    def test_weekly_and_model_windows_follow_the_session_window(self):
        result = claude.normalise(CLAUDE_RAW, fetched_at=1757600000)
        ids = [w["id"] for w in result["windows"]]
        self.assertEqual(ids, ["session", "weekly_all", "model:fable"])
        self.assertEqual(result["windows"][2]["label"], "Fable")
        self.assertEqual(result["windows"][2]["kind"], "model")

    def test_optional_windows_are_simply_absent(self):
        result = claude.normalise({"ok": True, "percent": 5.0, "resets_at": None},
                                  fetched_at=1757600000)
        self.assertEqual([w["id"] for w in result["windows"]], ["session"])
        self.assertIsNone(result["windows"][0]["resets_at"])

    def test_percentage_is_clamped_into_range(self):
        result = claude.normalise({"ok": True, "percent": 140.0, "resets_at": None},
                                  fetched_at=1757600000)
        self.assertEqual(result["windows"][0]["used_percent"], 100.0)

    def test_helper_error_becomes_an_error_state_with_no_windows(self):
        result = claude.normalise({"ok": False, "error": "network"}, fetched_at=1757600000)
        self.assertEqual(result["state"], "error")
        self.assertEqual(result["error"], "network")
        self.assertEqual(result["windows"], [])

    def test_missing_credentials_is_unavailable_rather_than_an_error(self):
        result = claude.normalise({"ok": False, "error": "no_credentials"}, fetched_at=1757600000)
        self.assertEqual(result["state"], "unavailable")

    def test_rate_limit_reports_an_absolute_retry_time(self):
        result = claude.normalise({"ok": False, "error": "usage_http_429", "retry_after": 120},
                                  fetched_at=1757600000)
        self.assertEqual(result["next_retry_at"], 1757600120)

    def test_result_is_a_valid_document_fragment(self):
        result = claude.normalise(CLAUDE_RAW, fetched_at=1757600000)
        schema.validate(schema.document({"claude": result}, 1757600000))


class CodexNormaliseTest(unittest.TestCase):
    def test_windows_keep_shortest_first_and_are_labelled_by_length(self):
        result = codex.normalise(CODEX_RAW, fetched_at=1757600000, now=1757600000)
        self.assertEqual(result["state"], "ok")
        self.assertEqual([w["id"] for w in result["windows"]], ["primary", "secondary"])
        self.assertEqual([w["label"] for w in result["windows"]], ["5 h", "Week"])
        self.assertEqual([w["kind"] for w in result["windows"]], ["session", "weekly"])
        self.assertEqual(result["windows"][1]["used_percent"], 88.0)

    def test_journal_source_is_stale_and_carries_its_age(self):
        raw = dict(CODEX_RAW, source="rollout", age_seconds=4000)
        result = codex.normalise(raw, fetched_at=1757600000, now=1757600000)
        self.assertEqual(result["state"], "stale")
        self.assertEqual(result["source"], "rollout")
        self.assertEqual(result["age_seconds"], 4000)

    def test_expired_window_of_a_stale_snapshot_drops_its_percentage(self):
        raw = dict(CODEX_RAW, source="rollout", age_seconds=4000)
        result = codex.normalise(raw, fetched_at=1757600000, now=1757620000)
        self.assertIsNone(result["windows"][0]["used_percent"])
        self.assertEqual(result["windows"][1]["used_percent"], 88.0)

    def test_a_live_reply_is_never_treated_as_expired(self):
        result = codex.normalise(CODEX_RAW, fetched_at=1757600000, now=1757620000)
        self.assertEqual(result["windows"][0]["used_percent"], 42.0)

    def test_helper_error_becomes_an_error_state(self):
        result = codex.normalise({"ok": False, "error": "no_usage_data"}, fetched_at=1757600000)
        self.assertEqual(result["state"], "error")
        self.assertEqual(result["error"], "no_usage_data")

    def test_missing_cli_is_unavailable(self):
        result = codex.normalise({"ok": False, "error": "no_codex_cli"}, fetched_at=1757600000)
        self.assertEqual(result["state"], "unavailable")

    def test_result_is_a_valid_document_fragment(self):
        result = codex.normalise(CODEX_RAW, fetched_at=1757600000, now=1757600000)
        schema.validate(schema.document({"codex": result}, 1757600000))


class BothProducedTheSameWindowShapeTest(unittest.TestCase):
    def test_normalised_windows_have_identical_field_sets(self):
        c = claude.normalise(CLAUDE_RAW, fetched_at=1757600000)["windows"][0]
        x = codex.normalise(CODEX_RAW, fetched_at=1757600000, now=1757600000)["windows"][0]
        self.assertEqual(sorted(c), sorted(x))


if __name__ == "__main__":
    unittest.main()


class CodexDetailsTest(unittest.TestCase):
    """Lines the panel menu has always shown that belong to no window."""

    def test_credits_plan_and_limit_reached_become_detail_lines(self):
        raw = dict(CODEX_RAW,
                   credits={"balance": "0", "unlimited": False},
                   limit_reached="weekly")
        result = codex.normalise(raw, fetched_at=1757600000, now=1757600000)
        self.assertEqual(result["details"],
                         ["Credits: 0", "Limit reached: weekly", "Plan: plus"])

    def test_unlimited_credits_read_as_unlimited(self):
        raw = dict(CODEX_RAW, credits={"balance": "0", "unlimited": True})
        result = codex.normalise(raw, fetched_at=1757600000, now=1757600000)
        self.assertIn("Credits: unlimited", result["details"])

    def test_a_reply_without_extras_has_no_detail_lines(self):
        result = claude.normalise(CLAUDE_RAW, fetched_at=1757600000)
        self.assertEqual(result["details"], [])
