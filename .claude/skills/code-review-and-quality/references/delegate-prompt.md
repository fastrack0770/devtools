# Writing the review prompt for a delegate

A review delegate — codex, or an Agent tool subagent — arrives with zero session
context and spends its whole budget on whatever the prompt leaves open. Two
failures cost the most: it reviews code the branch never touched, and it reads
whole files where the diff would have answered the question. Both are decided
by the prompt, so build the reading plan yourself and hand over a closed one.

Write the prompt to a file and pipe it in on stdin (`-`); review prompts contain
quotes, backticks, and paths that a shell argument mangles.

## Build the packet first

Compute these before writing a line of prompt. Each one closes a hole the
delegate would otherwise fill by reading.

```bash
MB=$(git merge-base <base> HEAD)          # paste the SHA, not the branch name
git diff --numstat $MB..HEAD              # the file list, with churn per file
```

- **The merge-base SHA.** A branch name lets the delegate resolve a range that
  includes commits already on the base, and it will review them in good faith.
- **The inclusion list.** Paste the `--numstat` lines into the prompt as the
  set of files under review. Sort them by added lines: that ordering is the
  priority order the delegate follows when its budget runs short.
- **The exclusion is implied.** A file absent from the list is out of scope, so
  a list of forbidden directories is unnecessary and merely invites reading.
- **The repository rules, quoted.** Paste the two or three prose contracts from
  `CLAUDE.md` / `AGENTS.md` the change could break, as quoted lines. Pointing at
  the rules file instead costs a full read of it plus whatever it routes to.
- **The intent, in three or four lines.** What the change is for, what modules
  are new, what got deleted. Without it the delegate reviews syntax.
- **The spec location**, when one exists, as a path — the delegate reads it.

## The reading contract

State the reading method as steps, not as a subsystem tour. Naming a file — "look
at the recorder and the renderer" — gets those files `cat`-ed whole; naming the
hunks gets the hunks.

1. `git diff $MB..HEAD -- <path>` per file, in the priority order given, as the
   only entry point. The diff, not the file, is the object under review.
2. Widen to `git diff -U40 $MB..HEAD -- <path>` when a hunk's correctness
   depends on surrounding code.
3. Read a numbered slice, capped and around a hunk, only when a question
   genuinely needs the enclosing function — an unchecked allocation, a
   descriptor that must be closed on every path, an off-by-one:
   `nl -ba <path> | sed -n '<start>,<end>p'`. Numbered from the first read, so
   `path:line` citations never require a second pass over the same file.
4. Each file is read once. A file already read is re-consulted from what the
   first read returned.

State the slice cap explicitly — a number of slices and a line ceiling per
slice, sized to the diff (a 4000-line C diff is served by roughly ten slices of
150 lines). Whole-file reads stay available for a file the diff itself created,
since there the diff and the file are the same text.

## The checks, bound to hunks

Six to eight checks derived from this change beat "review carefully", but each
one has to say where it applies. Pick from the recurring sources below, name the
files from the inclusion list each applies to, and mark the ones that earn a
numbered slice — a check for an unchecked allocation or a leaked descriptor is
exactly the case step 3 allows, and the only case that justifies leaving the
hunk.

- **Shell scripts:** `set -euo pipefail` interactions, quoting, idempotency,
  and whether a destructive step can run before its guard succeeded.
- **Memory-unsafe code (C/C++, unsafe Rust):** fixed buffers and truncation,
  thread safety of shared state, unchecked syscall returns, descriptor leaks,
  async-signal safety, failure flags that latch permanently. *(slice)*
- **Managed code (TypeScript, Python, JVM, Go):** unawaited promises and
  swallowed errors, nullability at boundaries, unbounded queries, retries
  without backoff, mutable shared defaults.
- **Copies kept in sync by a test:** whether the copies are still identical and
  what breaks when they diverge.
- **Hot paths:** work added to a render loop, control loop, or per-request path,
  especially work whose cost grows with uptime or data size.
- **Tests:** what the new tests do *not* cover, and which new components have no
  tests at all.
- **The change's own spec:** specified but not implemented, implemented but not
  specified.
- **The quoted repository rules:** which hunk breaks which quoted line.

## The budget and the stop rule

An unbounded review runs until the quota ends and reports whatever it reached
first. Give it a bound and a way to end cleanly:

- A file budget: how many of the listed files to reach, in priority order.
- A stop rule: stop at the budget or after N findings, whichever comes first.
- A coverage line: on stopping, list the files examined and the files left
  untouched. That line is what makes a partial review usable, and it is the
  part a delegate omits unless asked.

When the diff is too large for one budget, split it into two runs over disjoint
file groups rather than raising the budget of one run.

## The output contract

Severity prefixes (Critical / required / Consider / Nit / FYI), `path:line` per
finding, one concrete failure scenario per finding, the report language, and
findings only — one line for clean areas. Without the last constraint a third of
the response is a summary of the diff you already have.

## Reading the result

The delegate is usually right about mechanism and shakier about line numbers and
scope. Confirm each Critical yourself — ideally with a reproduction — before it
enters the report. Downgrade findings whose failure scenario does not survive
contact with the code, and drop the ones about files outside the inclusion list.
