#!/usr/bin/env python3
"""
opsx_skill_routing.py — PostToolUse hook for the Skill tool.

When an openspec skill runs (opsx:propose/apply/sync/archive or openspec-*),
it injects a reminder about the methodology skills relevant to the current
phase. For other skills it stays silent (event-gated, no noise).

Input: JSON on stdin (tool_name, tool_input.skill). Output: JSON with
hookSpecificOutput.additionalContext, or nothing.
"""

import json
import sys

# Phase -> reminder text (this map mirrors the "Skill routing" section in CLAUDE.md).
PROPOSE = ("[skill-routing] Planning phase (propose/explore): consider "
           "spec-driven-development, planning-and-task-breakdown, "
           "api-and-interface-design (if introducing a new contract/endpoint), "
           "opsx:explore / interview-me (if the spec is vague), "
           "doubt-driven-development (high stakes/irreversible).")
APPLY = ("[skill-routing] Implementation phase (apply): "
         "incremental-implementation and test-driven-development are MANDATORY "
         "(invoke via the Skill tool before implementing tasks). Also consider "
         "source-driven-development (framework/API), "
         "frontend-ui-engineering (if UI), "
         "security-and-hardening (if input/storage/network), "
         "observability-and-instrumentation (if production behavior). "
         "Before finishing — code-review-and-quality on the diff.")
ARCHIVE = ("[skill-routing] Before archive: run code-review-and-quality and "
           "code-simplification on the change diff.")


def reminder_for(skill: str) -> str | None:
    s = skill.lower()
    if "propose" in s or "explore" in s:
        return PROPOSE
    if "apply" in s:
        return APPLY
    if "archive" in s:
        return ARCHIVE
    return None  # sync and non-openspec skills — no reminder


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    if data.get("tool_name") != "Skill":
        return
    skill = str((data.get("tool_input") or {}).get("skill", ""))
    # openspec flow only.
    if not (skill.startswith("opsx:") or skill.startswith("openspec-")):
        return
    text = reminder_for(skill)
    if not text:
        return
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": text,
        }
    }))


if __name__ == "__main__":
    main()
