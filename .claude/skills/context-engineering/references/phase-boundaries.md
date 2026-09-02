# Phase Boundaries

A phase is a coherent chunk of work; its boundary is the moment that chunk feels done. Make session decisions at that boundary, not mid-phase.

## Five options

| Option | What it does |
|---|---|
| **Continue** | Keep the current session and its full context. |
| **Clear** | Start empty when prior context is irrelevant. |
| **Handoff** | Write a portable file for another harness, directory, repository, colleague, or side task. |
| **Subagent** | Give a tightly scoped, agent-runnable task its own context and receive a report. |
| **Compact** | Replace the current context with a lossy summary for the next phase. |

The `handoff` skill writes the portable file. When more than one subagent runs, each counts against `parallel-dev`'s quota; Call the Skill tool with "parallel-dev" first.

## Decide in order

The first yes wins:

1. **Can you continue?** Continue when the next phase needs this session as a primary source, or enough **smart zone** remains: the useful portion of the context window where the next phase fits without context degradation.
2. **Is this context irrelevant next?** Clear when the exploration, decisions, and dead ends are disposable. Preserve relevant rationale instead of clearing it.
3. **Must anything travel?** Handoff when changing harness, directory, repository, owner, or when forking a side task without derailing the current phase.
4. **Can the task run without steering?** Use a subagent when the scope and completion signal are tight enough for unattended work.
5. **Otherwise, compact.** Keep relevant context for the same harness and location in a focused summary, with an instruction naming the next phase.

## Primary and secondary sources

Continue preserves the session as a **primary source**: full information, more noise, less room. Clear discards it; compact and handoff create **secondary sources**: lossy summaries with less noise and more room. A subagent preserves the parent session but returns its work as a secondary report.

## Judgement calls

The questions are intentionally contextual. Ask them in order at the boundary; the same boundary can reasonably yield a different answer when available context, portability, or steering needs differ.
