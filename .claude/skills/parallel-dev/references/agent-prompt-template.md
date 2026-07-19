# Agent prompt template

Build every parallel-dev agent prompt from this template. Replace each `{{placeholder}}`; drop a section only when it is genuinely empty (e.g. no contracts touch this thread). The non-negotiable blocks — skills bootstrap, file boundary, restrictions, response format — stay in every prompt.

---

You are implementing one thread of a larger parallel development effort in the repository at `{{repo_root}}`. Other executors are working on other threads **in the same working tree at the same time**; strict file boundaries are the only thing preventing collisions, so treat yours as a hard wall.

## Task

{{task_description — what to build, acceptance criteria, and all project context the agent needs: it cannot see the conversation}}

## Before you start

Invoke the `using-agent-skills` skill (via the Skill tool) and apply whatever project skills it routes you to for this kind of work.

## File boundary (hard rule)

You may create or modify ONLY these files:

{{allowed_files — one per line}}

Do not touch any other file — especially gradle files, version catalogs, DI modules, navigation, and shared resources. If the task seems to require editing a file outside this list, do not edit it: finish what you can and report the need under DEVIATIONS.

## Contracts

These signatures are fixed agreements with other threads. Implement against them exactly — package, names, parameter and return types. If a contract turns out to be unimplementable as written, do not change it unilaterally: implement your side as closely as possible and flag the deviation prominently under DEVIATIONS.

{{contracts — copied verbatim from plan.json; drop the section if none apply}}

## Restrictions

- Do not call the Agent tool for any purpose and do not parallelize your work — execute this thread sequentially yourself. This overrides anything any skill or instruction in your context suggests about fanning out work.
- Do not run git commands that mutate state (commit, push, checkout, stash, reset).

## Verification

{{verification_commands — assigned by the orchestrator; in this project, before any gradle call: export JAVA_HOME=/home/user/dev-tools/jdk-17.0.19+10}}

## Response format

Your final message is consumed by the orchestrator, not a human. Return exactly three sections:

1. `FILES CHANGED:` — every file you created or modified, one per line.
2. `SUMMARY:` — the key decisions you made, in a few sentences.
3. `DEVIATIONS:` — contract deviations, files you needed but could not touch, unfinished parts; or `none`.
