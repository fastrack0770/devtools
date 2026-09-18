"""Contract tests for the provider-neutral usage document (design.md D2).

Both clients — the GNOME extension and the Godot Shell — read this shape, so an
accidental change here is a break in two places at once. Every fixture under
tests/fixtures is validated, and the rejection cases pin the parts a renderer
is allowed to trust: the version, the state vocabulary and the value types.
"""

import json
import pathlib
import unittest

from ai_usage import schema

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / (name + ".json")).read_text())


class FixtureContractTest(unittest.TestCase):
    def test_every_fixture_validates(self):
        names = sorted(p.stem for p in FIXTURES.glob("*.json"))
        self.assertTrue(names, "fixtures directory is not empty")
        for name in names:
            with self.subTest(fixture=name):
                schema.validate(load(name))

    def test_fixture_set_covers_the_documented_states(self):
        seen = set()
        for path in FIXTURES.glob("*.json"):
            for provider in json.loads(path.read_text())["providers"].values():
                seen.add(provider["state"])
        self.assertEqual(seen, {"ok", "stale", "unavailable", "error"})

    def test_partial_failure_is_a_valid_document(self):
        doc = schema.validate(load("partial_failure"))
        self.assertEqual(doc["providers"]["claude"]["state"], "error")
        self.assertEqual(doc["providers"]["codex"]["state"], "ok")
        self.assertEqual(doc["providers"]["codex"]["windows"][0]["used_percent"], 42.0)

    def test_rate_limit_carries_an_absolute_retry_time(self):
        doc = schema.validate(load("rate_limited"))
        self.assertEqual(doc["providers"]["claude"]["next_retry_at"], 1757600900)

    def test_expired_window_drops_the_percentage_instead_of_guessing(self):
        doc = schema.validate(load("expired_window"))
        self.assertIsNone(doc["providers"]["codex"]["windows"][0]["used_percent"])


class RejectionTest(unittest.TestCase):
    def reject(self, doc, fragment):
        with self.assertRaises(schema.ContractError) as caught:
            schema.validate(doc)
        self.assertIn(fragment, str(caught.exception))

    def test_unknown_schema_version_is_rejected(self):
        doc = load("claude_ok")
        doc["schema_version"] = 2
        self.reject(doc, "schema_version")

    def test_missing_schema_version_is_rejected(self):
        doc = load("claude_ok")
        del doc["schema_version"]
        self.reject(doc, "schema_version")

    def test_unknown_provider_state_is_rejected(self):
        doc = load("claude_ok")
        doc["providers"]["claude"]["state"] = "probably-fine"
        self.reject(doc, "state")

    def test_percent_outside_the_range_is_rejected(self):
        doc = load("claude_ok")
        doc["providers"]["claude"]["windows"][0]["used_percent"] = 140
        self.reject(doc, "used_percent")

    def test_percent_of_the_wrong_type_is_rejected(self):
        doc = load("claude_ok")
        doc["providers"]["claude"]["windows"][0]["used_percent"] = "74%"
        self.reject(doc, "used_percent")

    def test_windows_must_be_a_list(self):
        doc = load("claude_ok")
        doc["providers"]["claude"]["windows"] = {"session": 74}
        self.reject(doc, "windows")

    def test_window_without_an_id_is_rejected(self):
        doc = load("claude_ok")
        del doc["providers"]["claude"]["windows"][0]["id"]
        self.reject(doc, "id")

    def test_reset_time_of_the_wrong_type_is_rejected(self):
        doc = load("claude_ok")
        doc["providers"]["claude"]["windows"][0]["resets_at"] = "2026-09-11T12:00:00Z"
        self.reject(doc, "resets_at")

    def test_providers_must_be_an_object(self):
        doc = load("claude_ok")
        doc["providers"] = []
        self.reject(doc, "providers")

    def test_ok_state_requires_at_least_one_window(self):
        doc = load("claude_ok")
        doc["providers"]["claude"]["windows"] = []
        self.reject(doc, "windows")


if __name__ == "__main__":
    unittest.main()
