---
name: using-agent-skills
description: Discovers and invokes agent skills. Use when choosing which skill applies to a task, when several skills seem to apply at once, or when their guidance conflicts. Not needed when exactly one applicable skill is already named.
---

# Using Agent Skills

Skills encode this team's engineering practices, one per development phase. This meta-skill covers picking the right one and combining them.

## Picking a skill

Match the task to its phase:

| Situation | Skill |
|---|---|
| Unclear what the user actually wants | interview-me |
| Rough idea that needs shaping | opsx:explore |
| New feature or significant change, no spec | spec-driven-development |
| Spec exists, needs a task breakdown | planning-and-task-breakdown |
| Implementing a multi-file change | incremental-implementation |
| UI work / API or interface work | frontend-ui-engineering / api-and-interface-design |
| Need doc-verified framework usage | source-driven-development |
| High stakes or unfamiliar code | doubt-driven-development |
| Proving behavior with tests | test-driven-development (browser runtime: browser-testing-with-devtools) |
| Something broke unexpectedly | debugging-and-error-recovery |
| Pre-merge review | code-review-and-quality |
| Working code, too complex | code-simplification |
| Untrusted input, auth, secrets | security-and-hardening |
| Performance requirement or regression | performance-optimization |
| Commit/branch/history questions | git-workflow-and-versioning |
| Build and deployment pipelines | ci-cd-and-automation |
| Retiring systems, migrating users | deprecation-and-migration |
| Recording decisions, writing docs | documentation-and-adrs |
| Logs, metrics, traces, alerts | observability-and-instrumentation |
| Production deploy or launch | shipping-and-launch |
| Setting up agent context, CLAUDE.md | context-engineering |

## Composing skills

- Pick **one primary skill** for the task; consult others as specialist references, not as full workflows to stack. A bug fix needs debugging → test → review, not the entire lifecycle.
- When work genuinely spans phases (spec → plan → implement → test → review → ship), enter each phase's skill when you reach it, not all upfront.
- Skills use progressive disclosure: each SKILL.md says when to load files from its `references/` directory. Load them only when that condition applies.

## Global norms

Three behaviors apply across every skill; they live here so individual skills don't repeat them:

- **Scope discipline.** Touch only what the task requires; don't refactor, delete, or "clean up" adjacent code as a side effect.
- **Evidence-based verification.** Done means demonstrated — a passing test, build output, runtime behavior — proportional to the change; not "looks right".
- **Surface consequential ambiguity.** When requirements conflict or are missing on a decision that matters, say so and ask; don't invent product behavior.

## When guidance conflicts

- Hard rules about secrets, destructive operations, and production changes win over any other skill's stylistic preference.
- Project reality (CLAUDE.md, existing code conventions) wins over a skill's generic default.
- If two skills give genuinely contradictory instructions for the same decision, surface the conflict and ask rather than silently picking one.
