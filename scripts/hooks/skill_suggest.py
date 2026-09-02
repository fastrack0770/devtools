#!/usr/bin/env python3
"""
skill_suggest.py — UserPromptSubmit hook.

Runs on EVERY user message and checks whether a methodology skill fits it
(by keywords, RU/EN). If one fits, it injects a reminder with the list of
candidates; otherwise it stays silent (no noise).

Complements the PostToolUse hook opsx_skill_routing.py (which only covers
launching openspec skills). The topic map mirrors `using-agent-skills` and is
checked by `scripts/check_skills.py`.

Input: JSON on stdin (UserPromptSubmit -> prompt field). Output: JSON with
hookSpecificOutput.additionalContext, or nothing.
"""

import json
import re
import sys

# (lowercase keywords, topic, candidate skills)
# Keywords intentionally include both Russian and English so the hook fires
# on prompts written in either language.
RULES = [
    (("баг", "ошибк", "не работает", "падает", "сломал", "traceback", "exception",
      "bug", "error", "broken", "fails", "failing", "крэш", "crash"),
     "bug/unexpected behavior",
     ["debugging-and-error-recovery", "test-driven-development"]),
    (("тест", "покрыт", "unit test", "test", "регресс"),
     "testing",
     ["test-driven-development"]),
    (("api", "эндпоинт", "endpoint", "контракт", "rest", "graphql", "схема данных", "интерфейс модул"),
     "API/contract/interface",
     ["api-and-interface-design"]),
    (("ui", "ui-", "интерфейс", "кнопк", "форма", "страниц", "компонент", "frontend", "верстк", "css", "карточк"),
     "UI/frontend",
     ["frontend-ui-engineering"]),
    (("безопасн", "security", "auth", "пароль", "токен", "уязвим", "инъекц", "untrusted", "ввод польз"),
     "security/untrusted input",
     ["security-and-hardening"]),
    (("деплой", "deploy", "релиз", "release", "выкат", "rollout", "pipeline", "ci/cd", "ci-cd"),
     "deploy/release",
     ["shipping-and-launch", "ci-cd-and-automation"]),
    (("рефактор", "упрост", "почист", "cleanup", "refactor", "simplif", "читаемост"),
     "refactoring/simplification",
     ["code-simplification"]),
    (("ревью", "review", "проверь код", "качество кода", "code quality"),
     "quality review",
     ["code-review-and-quality"]),
    (("codex", "второе мнение", "вторым мнением", "чужую ветку", "чужой ветк", "чужой код", "ревью ветки", "review the branch", "review this branch", "review the mr", "review the pr", "review mr", "review pr"),
     "someone else's branch review",
     ["branch-review-for-others"]),
    (("план", "разбей", "декомпоз", "breakdown", "по шагам", "оцен", "estimate"),
     "planning/breakdown",
     ["planning-and-task-breakdown"]),
    (("производительн", "performance", "медленн", "оптимиз", "slow", "latency", "профил"),
     "performance",
     ["performance-optimization"]),
    (("логир", "метрик", "observability", "мониторинг", "trace", "телеметри"),
     "observability",
     ["observability-and-instrumentation"]),
    (("идея", "обдумать", "brainstorm", "не уверен", "размыт", "набросать"),
     "raw idea/clarification",
     ["opsx:explore", "interview-me"]),
    (("спецификац", "spec", "новая фича", "с нуля", "новый проект", "требовани"),
     "new feature/specification",
     ["spec-driven-development"]),
    (("хук", "hook", "settings.json", ".claude", "конфиг claude", "permission", "разрешени claude"),
     "harness configuration",
     ["update-config"]),
    (("скил", "skill", "какой навык", "which skill"),
     "skill selection",
     ["using-agent-skills"]),
    (("докум", "adr", "readme", "архитектурн решени", "document"),
     "documentation/decisions",
     ["documentation-and-adrs"]),
    (("grill", "гриль", "стресс-тест", "прожарь", "допроси"),
     "design stress-test", ["grilling"]),
    (("прототип", "prototype", "набросок", "throwaway", "poc"),
     "throwaway prototype", ["prototype"]),
    (("конфликт", "conflict", "rebase", "merge"),
     "merge conflict", ["resolving-merge-conflicts"]),
    (("модул", "seam", "интерфейс модул", "deep module", "архитектур", "deepen"),
     "codebase/module design", ["codebase-design"]),
    (("глоссар", "glossary", "термин", "context.md", "ubiquitous"),
     "domain vocabulary", ["domain-modeling"]),
    (("skill.md", "claude.md", "agents.md", "напиши скилл", "write a skill"),
     "agent-facing writing", ["writing-for-agents"]),
    (("credentials", "секрет", "secrets", "provision", "настрой ci"),
     "human-only setup", ["wizard"]),
]


WORD_KEYS = {"ui", "api", "poc", "rest", "css", "adr", "test", "bug", "error", "merge"}


def key_matches(key: str, prompt: str) -> bool:
    """Use word boundaries for short bare tokens; stems and phrases stay substring matches."""
    if key in WORD_KEYS:
        return re.search(rf"(?<!\w){re.escape(key)}(?!\w)", prompt) is not None
    return key in prompt


def suggest(prompt: str):
    p = prompt.lower()
    topics, skills = [], []
    for keys, topic, sk in RULES:
        if any(key_matches(k, p) for k in keys):
            topics.append(topic)
            for s in sk:
                if s not in skills:
                    skills.append(s)
    return topics, skills


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    prompt = str(data.get("prompt", ""))
    if not prompt.strip():
        return
    topics, skills = suggest(prompt)
    if not skills:
        return  # no matches — stay silent
    text = ("[skill-routing] This message touches on: " + "; ".join(topics)
            + ". Consider skills: " + ", ".join(skills)
            + " (when in doubt — using-agent-skills).")
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": text,
        }
    }))


if __name__ == "__main__":
    main()
