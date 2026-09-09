---
name: using-agent-skills
description: Discovers and invokes agent skills. Use when choosing which skill applies to a task, when several skills seem to apply at once, or when their guidance conflicts. Not needed when exactly one applicable skill is already named.
---

# Using Agent Skills

Skills encode this team's engineering practices. This map shows the normal flow, useful detours, and the vocabulary beneath both.

## The main flow

Start with interview-me when the ask is underspecified, then grilling when the design tree still has open branches. Use opsx:explore for a foggy idea. Move to opsx:propose, applying spec-driven-development, planning-and-task-breakdown, api-and-interface-design, and codebase-design as needed.

During opsx:apply, use incremental-implementation and test-driven-development. Add source-driven-development, frontend-ui-engineering, security-and-hardening, or observability-and-instrumentation when their triggers fit. Finish with code-review-and-quality, then opsx:archive; use opsx:sync when delta specs need merging separately.

OpenSpec is the default spec artifact, not the only path. A small, unambiguous change can go straight to implementation.

## On-ramps

- Something broke: debugging-and-error-recovery.
- Already mid-merge conflict: resolving-merge-conflicts.
- A design question cannot be settled on paper: prototype.
- A big change spans independent file groups: parallel-dev.

## Codebase health

- code-simplification improves local clarity without changing behavior.
- codebase-design creates deep modules, small interfaces, and clean seams.
- deprecation-and-migration retires or replaces systems with consumers.
- performance-optimization starts only from measured slowness or an explicit budget: measure first.

## Vocabulary underneath

- domain-modeling owns domain language and the project's `CONTEXT.md` glossary.
- codebase-design owns module, interface, depth, seam, adapter, leverage, and locality.
- writing-for-agents shapes skills, CLAUDE.md, AGENTS.md, and documents reached through pointers.
- documentation-and-adrs records human-facing documentation and durable decisions.

## Production

ci-cd-and-automation builds automated pipelines and gates. shipping-and-launch handles rollout, rollback, and launch monitoring.

## Phase boundaries

At a phase boundary, choose continue, clear, handoff, subagent, or compact using `context-engineering`'s `.claude/skills/context-engineering/references/phase-boundaries.md`. Keep explore -> propose in one context window; start each apply task fresh so implementation gets a clean, focused context.

## User-invoked skills

handoff, retro, and to-questionnaire are typed by the human because they control session transfer, reflection, or communication to another person. The model can explain when one may help, but only the user starts it.

## Quick lookup

| Situation | Skill |
|---|---|
| API or public contract | api-and-interface-design |
| Real-browser verification | browser-testing-with-devtools |
| Pipeline or automated gate | ci-cd-and-automation |
| Completed change review | code-review-and-quality |
| Working code is too complex | code-simplification |
| Module boundary, seam, or depth | codebase-design |
| Context or rules-file hygiene | context-engineering |
| Failure or unexpected behavior | debugging-and-error-recovery |
| Retire a consumed system | deprecation-and-migration |
| Human docs or durable decision | documentation-and-adrs |
| Domain terms or CONTEXT.md | domain-modeling |
| High-stakes adversarial check | doubt-driven-development |
| User-facing UI | frontend-ui-engineering |
| Commit, branch, or history | git-workflow-and-versioning |
| Stress-test a known design | grilling |
| Portable session transfer | handoff |
| Multi-file implementation | incremental-implementation |
| Underspecified request | interview-me |
| Logs, metrics, traces, alerts | observability-and-instrumentation |
| Implement OpenSpec tasks | opsx:apply (openspec-apply-change) |
| Archive OpenSpec change | opsx:archive (openspec-archive-change) |
| Explore a foggy idea | opsx:explore (openspec-explore) |
| Create OpenSpec artifacts | opsx:propose (openspec-propose) |
| Sync delta specs | opsx:sync (openspec-sync-specs) |
| Independent implementation threads | parallel-dev |
| Measured slowness | performance-optimization |
| Break requirements into tasks | planning-and-task-breakdown |
| Answer one question in code | prototype |
| Active merge/rebase conflict | resolving-merge-conflicts |
| Trust boundary, auth, secrets | security-and-hardening |
| Production rollout | shipping-and-launch |
| Current framework guidance | source-driven-development |
| Significant change without spec | spec-driven-development |
| Automated behavior tests | test-driven-development |
| Questionnaire for another person | to-questionnaire |
| Skill selection or conflict | using-agent-skills |
| Human-only provisioning | wizard |
| Agent-facing document | writing-for-agents |

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
