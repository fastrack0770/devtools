# Writing the codex review prompt

Codex arrives with zero session context. Everything it needs must be in the
prompt, and everything you leave unconstrained it decides for itself — usually
by retelling the diff back to you.

Write the prompt to a file and pipe it in on stdin (`-`); review prompts are
long and contain quotes, backticks, and paths that a shell argument mangles.

## What the prompt must carry

1. **The diff range and how to get it.** Give the commands (`git diff
   <base>...HEAD --stat`, then per file) rather than pasting the diff — codex
   reads the repository, and a pasted 5000-line diff spends its context on files
   it does not need.
2. **What the change is for, in three or four lines.** Intent, new modules, what
   got deleted. Without this codex reviews syntax.
3. **Where the spec lives**, when there is one: the OpenSpec change directory,
   the issue, the design doc.
4. **The five quality axes**, named explicitly: correctness, readability and
   simplicity, architecture, security, performance.
5. **A numbered list of the specific things to check**, derived from the change
   itself — the concurrency it introduces, the resources it allocates, the hot
   paths it touches, the spec it claims to implement, the repository rules it
   might break. Six to eight concrete items beat "review carefully". The
   section below lists the recurring sources.
6. **The output contract.** Severity prefixes (Critical / required / Consider /
   Nit / FYI), `path:line` per finding, a concrete failure scenario per
   finding, the report language.
7. **What to do with clean areas**: one line saying so. Ask for findings only —
   without that constraint a third of the response is summary you already
   have.

## Sources for the numbered list

Pick the ones the change actually touches; each is a check that a generic
"review this" prompt tends to skip.

- **Shell scripts:** `set -euo pipefail` interactions, quoting, idempotency,
  behaviour when a target path or disk is unavailable, and whether any
  destructive step can run before its guard succeeded.
- **Memory-unsafe code (C/C++, unsafe Rust):** fixed buffers and truncation,
  thread safety of shared state, error handling of every syscall, descriptor
  leaks, async-signal safety when handlers are involved, failure flags that
  latch permanently.
- **Managed code (TypeScript, Python, JVM, Go):** unawaited promises and
  swallowed errors, nullability at boundaries, unbounded queries and missing
  pagination, retries without backoff, mutable shared defaults.
- **Copies kept in sync by a test:** whether the copies are actually identical,
  what breaks when they diverge, whether the sync boundary crosses a submodule
  or package.
- **Hot paths:** work added to a render loop, control loop, or per-request
  path, especially work whose cost grows with uptime or data size.
- **Tests:** what the new tests do *not* cover — concurrency, resource
  exhaustion, malformed environment — and which new components have no tests.
- **The change's own spec:** everything specified but not implemented, and
  everything implemented but not specified.
- **The repository's prose contracts** in `CLAUDE.md` / `AGENTS.md`.

## Reading the result

Codex is usually right about mechanism and shakier about line numbers and
scope. Confirm each Critical yourself — ideally with a reproduction — before it
enters the report. Downgrade findings whose failure scenario does not survive
contact with the code, and drop the ones about files the change never touched.
