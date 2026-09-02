# 0004: Skill routing is hooks plus router

## Context
Different routing needs range from exact phrase recognition to contextual judgment and explicit human control.

## Decision
Use keyword hooks as deterministic pointers, skill descriptions as fuzzy pointers, and user-invoked skills as zero-load commands started only by a human. Keep the hook maps, descriptions, and `using-agent-skills` router aligned through `scripts/check_skills.py`.

## Why
The three mechanisms cover precise, semantic, and intentional invocation without forcing every prompt to load the full catalog.
