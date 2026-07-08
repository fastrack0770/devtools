#!/usr/bin/env python3
"""
skill_suggest.py — UserPromptSubmit hook.

Runs on EVERY user message and checks whether a methodology skill fits it
(by keywords, RU/EN). If one fits, it injects a reminder with the list of
candidates; otherwise it stays silent (no noise).

Complements the PostToolUse hook opsx_skill_routing.py (which only covers
launching openspec skills). The topic map mirrors the "Skill routing" section
in CLAUDE.md.

Input: JSON on stdin (UserPromptSubmit -> prompt field). Output: JSON with
hookSpecificOutput.additionalContext, or nothing.
"""

import json
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
    (("ui", "интерфейс", "кнопк", "форма", "страниц", "компонент", "frontend", "верстк", "css", "карточк"),
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
    (("план", "разбей", "декомпоз", "breakdown", "по шагам", "оцен", "estimate"),
     "planning/breakdown",
     ["planning-and-task-breakdown"]),
    (("производительн", "performance", "медленн", "оптимиз", "slow", "latency", "профил"),
     "performance",
     ["performance-optimization"]),
    (("логир", "метрик", "observability", "мониторинг", "trace", "телеметри"),
     "observability",
     ["observability-and-instrumentation"]),
    (("идея", "обдумать", "brainstorm", "не уверен", "stress-test", "размыт", "набросать"),
     "raw idea/clarification",
     ["idea-refine", "interview-me"]),
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
]


def suggest(prompt: str):
    p = prompt.lower()
    topics, skills = [], []
    for keys, topic, sk in RULES:
        if any(k in p for k in keys):
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
