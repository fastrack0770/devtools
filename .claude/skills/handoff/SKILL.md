---
name: handoff
description: Write a compact handoff document so a fresh agent can continue the work.
argument-hint: "What will the next session focus on?"
disable-model-invocation: true
---

# Handoff

Write a self-contained handoff for a fresh agent. Save it under the operating system's temporary directory, never in the workspace, and tailor it to the user's argument when one was provided.

Include:

- the next session's objective, current state, decisions, constraints, blockers, and concrete next actions;
- a `## Suggested skills` section naming skills the next agent should call the Skill tool for;
- paths to existing OpenSpec change directories, plans, ADRs, commits, diffs, and other artifacts instead of duplicating their contents;
- commands needed to verify or resume safely.

Redact secrets and personal data. Record only the minimum sensitive context needed to continue.

The choice between continuing, clearing, handing off, using a subagent, or compacting is described in the `phase-boundaries` reference of the `context-engineering` skill (load it there).

## Verification

The document exists in the OS temp directory, matches the requested next-session focus, points to existing artifacts, names suggested skills, contains actionable next steps, and contains no secrets or personal data.
