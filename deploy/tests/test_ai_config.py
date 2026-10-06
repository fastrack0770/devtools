"""Exercise installation with isolated project and user configuration directories."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import stat
import tempfile
import tomllib
import unittest


DEPLOY = Path(__file__).resolve().parents[1]
FLAGS = {
    "DISABLE_TELEMETRY": "1",
    "DISABLE_ERROR_REPORTING": "1",
    "DISABLE_FEEDBACK_COMMAND": "1",
}


class AiConfigPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "source"
        shutil.copytree(DEPLOY, self.repo / "deploy", ignore=shutil.ignore_patterns("tests"))
        for name in [".claude/skills/fixture", ".codex/skills", "scripts/hooks"]:
            (self.repo / name).mkdir(parents=True)
        (self.repo / ".claude/skill-manifest.json").write_text(
            '{"promoted": ["fixture"], "in_progress": ["unfinished"]}'
        )
        (self.repo / ".claude/skills/fixture/SKILL.md").write_text("# Fixture\n")
        (self.repo / ".claude/settings.json").write_text('{"hooks": {}}')
        (self.repo / "scripts/hooks/skill_suggest.py").write_text("# fixture\n")
        self.project = self.root / "project"
        self.project.mkdir()
        self.user = self.root / "claude-user"
        self.env = dict(os.environ, CLAUDE_CONFIG_DIR=str(self.user),
                        CODEX_HOME=str(self.root / "codex-user"))

    def settings_path(self, mode):
        return (self.user if mode == "global" else self.project / ".claude") / "settings.json"

    def install(self, mode):
        return subprocess.run(
            ["bash", str(self.repo / "deploy/ai-config.sh"),
             "--global" if mode == "global" else str(self.project)],
            env=self.env, capture_output=True, text=True,
        )

    def test_fresh_installs_disable_optional_traffic(self):
        for mode in ["project", "global"]:
            with self.subTest(mode=mode):
                result = self.install(mode)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                settings = json.loads(self.settings_path(mode).read_text())
                for key, value in FLAGS.items():
                    self.assertEqual(settings.get("env", {}).get(key), value)

    def test_reinstall_restores_flags_preserves_custom_settings_and_is_idempotent(self):
        for mode in ["project", "global"]:
            with self.subTest(mode=mode):
                path = self.settings_path(mode)
                path.parent.mkdir(parents=True, exist_ok=True)
                custom_hook = {"hooks": [{"type": "command", "command": "echo user-hook"}]}
                path.write_text(json.dumps({
                    "env": {"MY_SETTING": "keep", "DISABLE_TELEMETRY": "0"},
                    "model": "custom-model", "permissions": {"defaultMode": "plan"},
                    "hooks": {"UserPromptSubmit": [custom_hook]},
                }))
                for _ in range(2):
                    result = self.install(mode)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    settings = json.loads(path.read_text())
                    self.assertEqual(settings["env"], {"MY_SETTING": "keep", **FLAGS})
                    self.assertEqual(settings["model"], "custom-model")
                    self.assertEqual(settings["permissions"], {"defaultMode": "plan"})
                    self.assertIn(custom_hook, settings["hooks"]["UserPromptSubmit"])
                    if mode == "project":
                        self.assertEqual(settings["hooks"], {"UserPromptSubmit": [custom_hook]})
                    if _ == 0:
                        first = path.read_bytes()
                    else:
                        self.assertEqual(path.read_bytes(), first)

    def test_invalid_settings_are_rejected_without_overwriting(self):
        for mode in ["project", "global"]:
            for original in ["{broken", "[]", '{"env": null}']:
                with self.subTest(mode=mode, original=original):
                    path = self.settings_path(mode)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(original)
                    result = self.install(mode)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(path.read_text(), original)

    def codex_config(self):
        return self.root / "codex-user" / "config.toml"

    def assert_codex_private(self, text):
        config = tomllib.loads(text)
        self.assertIs(config["analytics"]["enabled"], False)
        self.assertIs(config["feedback"]["enabled"], False)

    def test_fresh_installs_disable_codex_analytics(self):
        for mode in ["project", "global"]:
            with self.subTest(mode=mode):
                self.codex_config().unlink(missing_ok=True)
                result = self.install(mode)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assert_codex_private(self.codex_config().read_text())
                self.assertEqual(stat.S_IMODE(self.codex_config().stat().st_mode), 0o600)

    def test_reinstall_keeps_codex_config_and_is_idempotent(self):
        original = (
            '# my codex settings\n'
            'model = "custom-model"\n'
            'feedback.enabled = true\n'
            '\n'
            '[analytics]  # vendor default\n'
            'enabled = true\n'
            '\n'
            '[features]\n'
            'memories = false\n'
        )
        for mode in ["project", "global"]:
            with self.subTest(mode=mode):
                path = self.codex_config()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(original)
                path.chmod(0o640)
                for run in range(2):
                    result = self.install(mode)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    text = path.read_text()
                    self.assert_codex_private(text)
                    config = tomllib.loads(text)
                    self.assertEqual(config["model"], "custom-model")
                    self.assertEqual(config["features"], {"memories": False})
                    self.assertIn("# my codex settings", text)
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)
                    if run == 0:
                        first = text
                    else:
                        self.assertEqual(text, first)

    def test_invalid_codex_config_is_rejected_without_overwriting(self):
        for mode in ["project", "global"]:
            for original in ["model = [broken", "analytics = { enabled = true }\n"]:
                with self.subTest(mode=mode, original=original):
                    path = self.codex_config()
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(original)
                    result = self.install(mode)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(path.read_text(), original)


if __name__ == "__main__":
    unittest.main()
