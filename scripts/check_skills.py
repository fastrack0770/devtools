#!/usr/bin/env python3
"""Lint skills: frontmatter, names, references, size, manifest and routing consistency.

Frontmatter check is intentionally not full YAML: it enforces exact `---` delimiter
lines, one `key: value` per line (nested/multiline values are skipped, not validated),
and rejects duplicate keys.

Usage: python3 scripts/check_skills.py [--skills-dir PATH] [--manifest PATH] [--hooks-dir PATH]
Exit code 1 on errors; warnings don't fail the run.
"""

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

WARN_LINES = 150   # entry SKILL.md larger than this gets a warning
FAIL_LINES = 400   # ...larger than this is an error
MAX_DESCRIPTION = 1024
BOILERPLATE_HEADINGS = (
    "## Common Rationalizations",
    "## Red Flags",
    "## Anti-Patterns",
)
# Paths anywhere in the text (bare, backticked, or inside links), with optional #anchor.
REL_PATH_RE = re.compile(r"(?<![\w./-])((?:references|scripts)/[\w./-]+\.[\w]+)(?:#[\w-]+)?")
REPO_PATH_RE = re.compile(r"(\.claude/skills/[\w./-]+\.[\w]+)(?:#[\w-]+)?")
ROUTING_ALLOWLIST = {"update-config"}
REMINDER_WORD_ALLOWLIST = {"skill-routing", "high-stakes"}
OPSX_ALIASES = {
    "openspec-apply-change": "opsx:apply", "openspec-archive-change": "opsx:archive",
    "openspec-explore": "opsx:explore", "openspec-propose": "opsx:propose",
    "openspec-sync-specs": "opsx:sync",
}


def load_module(path: Path, name: str):
    """Load a dependency-free hook module without running its CLI entry point."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_frontmatter(text: str, problems: list[str]) -> dict | None:
    """Parse the supported frontmatter subset; append syntax issues to `problems`."""
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        problems.append("first line must be exactly '---'")
        return None
    try:
        end = lines.index("---", 1)
    except ValueError:
        problems.append("closing '---' delimiter line not found")
        return None
    fields: dict[str, str] = {}
    for i, line in enumerate(lines[1:end], start=2):
        if not line.strip():
            continue
        if line.startswith((" ", "\t")) or line.strip().startswith("#"):
            continue  # nested/continuation/comment lines: out of the validated subset
        key, sep, value = line.partition(":")
        if not sep or not key.strip():
            problems.append(f"line {i}: not 'key: value' — {line!r}")
            continue
        key = key.strip()
        if key in fields:
            problems.append(f"line {i}: duplicate key '{key}'")
            continue
        fields[key] = value.strip()
    return fields


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skills-dir", type=Path,
                        default=Path(__file__).resolve().parent.parent / ".claude" / "skills")
    repo_default = Path(__file__).resolve().parent.parent
    parser.add_argument("--manifest", type=Path,
                        default=repo_default / ".claude" / "skill-manifest.json")
    parser.add_argument("--hooks-dir", type=Path,
                        default=repo_default / "scripts" / "hooks")
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    seen_names: dict[str, str] = {}
    repo_root = args.skills_dir.parent.parent

    skill_files = sorted(args.skills_dir.glob("*/SKILL.md"))
    if not skill_files:
        errors.append(f"no SKILL.md files found under {args.skills_dir}")

    disabled: set[str] = set()
    for skill_md in skill_files:
        skill_dir = skill_md.parent
        rel = skill_md.relative_to(repo_root)
        text = skill_md.read_text(encoding="utf-8")

        fm_problems: list[str] = []
        fm = parse_frontmatter(text, fm_problems)
        for problem in fm_problems:
            errors.append(f"{rel}: frontmatter — {problem}")
        if fm is not None:
            name = fm.get("name", "")
            description = fm.get("description", "")
            if not name:
                errors.append(f"{rel}: frontmatter missing 'name'")
            elif name != skill_dir.name:
                errors.append(f"{rel}: name '{name}' != directory '{skill_dir.name}'")
            if name in seen_names:
                errors.append(f"{rel}: duplicate name '{name}' (also in {seen_names[name]})")
            elif name:
                seen_names[name] = str(rel)
            if fm.get("disable-model-invocation", "").lower() == "true" and name:
                disabled.add(name)
            if not description:
                errors.append(f"{rel}: frontmatter missing 'description'")
            elif len(description) > MAX_DESCRIPTION:
                errors.append(f"{rel}: description is {len(description)} chars (max {MAX_DESCRIPTION})")

        line_count = text.count("\n") + 1
        if line_count > FAIL_LINES:
            errors.append(f"{rel}: {line_count} lines — split into references/ (limit {FAIL_LINES})")
        elif line_count > WARN_LINES:
            warnings.append(f"{rel}: {line_count} lines — consider progressive disclosure (soft limit {WARN_LINES})")

        for heading in BOILERPLATE_HEADINGS:
            if heading in text:
                warnings.append(f"{rel}: contains boilerplate section '{heading}'")

        # References relative to the skill directory, plus repo-rooted cross-skill paths.
        for match in REL_PATH_RE.finditer(text):
            target = skill_dir / match.group(1)
            if not target.exists():
                errors.append(f"{rel}: broken reference '{match.group(1)}'")
        for match in REPO_PATH_RE.finditer(text):
            target = repo_root / match.group(1)
            if not target.exists():
                errors.append(f"{rel}: broken cross-skill reference '{match.group(1)}'")

        # Files in references/ should be mentioned from the entry point, or they're unreachable.
        refs_dir = skill_dir / "references"
        if refs_dir.is_dir():
            for ref_file in refs_dir.rglob("*.md"):
                if str(ref_file.relative_to(skill_dir)) not in text:
                    warnings.append(f"{rel}: {ref_file.relative_to(skill_dir)} never referenced from SKILL.md")

    skill_names = set(seen_names)
    promoted: list[str] = []
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        promoted = manifest.get("promoted", [])
        in_progress = manifest.get("in_progress", [])
        if not isinstance(promoted, list) or not isinstance(in_progress, list):
            raise ValueError("'promoted' and 'in_progress' must be lists")
        entries = promoted + in_progress
        duplicates = sorted({name for name in entries if entries.count(name) > 1})
        for name in duplicates:
            errors.append(f"{args.manifest}: skill '{name}' is listed more than once")
        for name in sorted(skill_names - set(entries)):
            errors.append(f"{args.manifest}: skill directory '{name}' is not listed")
        for name in sorted(set(entries) - skill_names):
            errors.append(f"{args.manifest}: entry '{name}' has no skill directory")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"{args.manifest}: invalid manifest — {exc}")

    router_path = args.skills_dir / "using-agent-skills" / "SKILL.md"
    try:
        router_text = router_path.read_text(encoding="utf-8")
        for name in promoted:
            representations = (name, OPSX_ALIASES.get(name, ""))
            if not any(value and value in router_text for value in representations):
                errors.append(f"{router_path}: promoted skill '{name}' is missing from router")
    except OSError as exc:
        errors.append(f"{router_path}: cannot check router — {exc}")

    try:
        suggest_hook = load_module(args.hooks_dir / "skill_suggest.py", "skill_suggest_check")
        suggested = {skill for _keys, _topic, skills in suggest_hook.RULES for skill in skills}
        valid_routed = skill_names | set(OPSX_ALIASES.values()) | ROUTING_ALLOWLIST
        for name in sorted(suggested - valid_routed):
            errors.append(f"skill_suggest.py: routed skill '{name}' does not exist")
        for name in sorted(suggested & disabled):
            errors.append(f"skill_suggest.py: user-invoked skill '{name}' must not be suggested")

        opsx_hook = load_module(args.hooks_dir / "opsx_skill_routing.py", "opsx_routing_check")
        reminder_text = " ".join((opsx_hook.PROPOSE, opsx_hook.APPLY, opsx_hook.ARCHIVE))
        reminder_names = set(re.findall(r"\b(?:opsx:[a-z-]+|[a-z]+(?:-[a-z]+)+)\b", reminder_text))
        for name in sorted(reminder_names - REMINDER_WORD_ALLOWLIST - valid_routed):
            errors.append(f"opsx_skill_routing.py: routed skill '{name}' does not exist")
        for name in opsx_hook.REMINDER_SKILLS:
            if name not in valid_routed:
                errors.append(f"opsx_skill_routing.py: routed skill '{name}' does not exist")
            if name not in reminder_text:
                errors.append(f"opsx_skill_routing.py: declared reminder skill '{name}' is absent from reminders")
    except (OSError, ImportError, AttributeError, TypeError) as exc:
        errors.append(f"{args.hooks_dir}: cannot check routing hooks — {exc}")

    for msg in warnings:
        print(f"WARN  {msg}")
    for msg in errors:
        print(f"ERROR {msg}")
    print(f"\n{len(skill_files)} skills checked: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
