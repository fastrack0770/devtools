---
name: branch-review-for-others
description: Reviews someone else's branch against its base in two independent passes — the reviewing model's own pass plus a read-only codex pass — and writes one self-contained, severity-ranked Markdown report a third party can read and act on without the session. Use when asked to review a branch, MR, or PR written by someone else, "проверь чужую ветку", "что не так в этой ветке", a review "через codex" or "вторым мнением", or a review to paste into an MR. Not for your own in-progress change (code-review-and-quality) and not for implementing the fixes.
---

# Branch review for others

Review a branch someone else wrote and hand back a document, not a conversation:
two independent passes over the same diff, every finding verified before it is
written down, one report whose reader has none of your session context. The
defining constraint is that reader — the author or a maintainer works through
the file top-down without you, so each finding must stand on its own.

Two passes because they fail differently. Your pass knows the repository's rules
and specs; codex arrives with no session history and no attachment to the
change, so it catches what familiarity hides. Independent agreement between the
two is the strongest signal in the report.

## 1. Establish scope and intent

```bash
MB=$(git merge-base <base> HEAD)
git log --oneline $MB..HEAD
git diff --numstat $MB..HEAD
```

Resolve the merge base to a SHA and carry that SHA through the review, so
commits that landed on `<base>` after the fork stay out of it. A branch name
handed to a delegate resolves to a wider range, and the delegate then reviews
already-merged code in good faith — the single largest waste in a delegated
review. Read the change's intent before its implementation — an OpenSpec change
under `openspec/changes/`, a linked task or issue, the commit messages — and
sort the `--numstat` list into real code versus mechanical bulk (docs, generated
files, renames), keeping it ordered by added lines.

Done when: the merge-base SHA is pinned, the diff is non-empty, the intent is
written down in three or four lines, and the file list is ordered by churn with
the mechanical bulk marked.

## 2. Launch codex on a closed reading plan, then keep working

The delegate spends its whole budget on whatever the prompt leaves open, so hand
it a closed plan: the merge-base SHA, the file list from step 1 as the set under
review, a diff-first reading method, a file budget, and a stop rule. Load
`.claude/skills/code-review-and-quality/references/delegate-prompt.md` and build
the prompt from it — that file is the single source of truth for the prompt's
shape, wherever a delegated review is launched from.

Codex runs unattended for minutes; start it before your own pass so the two
overlap. Write the prompt to a file and launch read-only in the background:

```bash
.claude/skills/parallel-dev/scripts/run_codex.sh --cwd <repo root> \
  --out <scratchpad>/codex_review.md - < <scratchpad>/codex_prompt.md
```

Read-only is the script's default and the only mode for a reviewer. One
sequential read-only delegate needs neither `parallel-dev` nor a partitioning
plan. When `which codex` finds nothing or the run returns no message, continue
single-pass and record that in the report's unverified section.

Done when: the prompt carries the SHA, the file list, the reading method, a
budget and a stop rule; codex is running (or its absence is noted); and your own
pass has started without waiting for it.

## 3. Your own pass

Call the Skill tool with "code-review-and-quality" and run its process on the
range from step 1: the five quality axes, the separate spec axis, its severity
ladder, its verdict rule. Add the checks a reviewer without the repository's
context cannot make:

- **Prose contracts.** Rules in `CLAUDE.md` / `AGENTS.md` that a diff can
  silently break — counts that must be updated, directories that must match an
  upstream, deploy invariants. They live in prose rather than CI, so they are
  the rules that break.
- **Spec ↔ code ↔ docs coherence.** Compare the delta spec with what was synced
  into the living spec; check that design decisions cited in comments exist and
  that superseded design notes no longer contradict the final spec.
- **Dead ends.** Constants never read, one straggler in the old format,
  docstrings mass-edited into saying something false — cheap to find, and what
  makes the next reader distrust the change.

Done when: every axis has a finding or an explicit "clean", and the spec axis is
reported separately.

## 4. Verify before writing down

Neither pass gets to assert.

- **Reproduce behavioural claims.** A shell-semantics bug, an arithmetic claim,
  "this returns non-zero": write the short repro in the scratchpad and run it.
  A finding that ships with its reproduction cannot be argued away, and
  sometimes the repro shows the finding was wrong.
- **Recompute counted claims** yourself when a number is a contract.
- **Treat codex output as a draft.** It is right about mechanism more often than
  about line numbers and scope. Confirm each Critical against the code before
  promoting it; downgrade findings whose failure scenario does not survive the
  code; drop findings about files the change never touched.
- **Record what you could not verify** (a test suite that does not run here, a
  device you do not have) as a report section rather than leaving it out, and
  put the files the delegate's coverage line left unexamined in that section.

Done when: every Critical and required finding has been checked against the code
or reproduced, and the unverified list is written.

## 5. Merge, attribute, write the report

Merge both passes into one deduplicated list and attribute each finding by model
name — *(claude)*, *(codex)*, *(both, independently)* — because provenance tells
the reader how much independent scrutiny a finding survived. Rank Critical and
required findings by severity, not file order, and number them continuously so
an MR discussion can cite "finding 3".

Write for a reader without your session: every finding carries a `path:line`
that resolves in the repository, the defect in one sentence, a concrete failure
scenario, the repro output when there is one, and what to do. Every reference
points at the repository or at another numbered finding. Follow
`references/report-template.md`; write in the language the repository uses for
its docs and commits, keeping the severity prefixes as they are.

Save to `<scratchpad>/<branch>-review.md`, or to the path the user names, and
hand the file to the user with a three-line summary in the terminal: verdict,
Critical count, offer to fix.

Done when: the file exists, renders as Markdown, and each numbered finding has
path, defect, scenario, action, and attribution.

## 6. Verdict, then stop

Approve when the change definitely improves code health even if imperfect;
request changes when a Critical or required finding stands. Close with a short,
specific note on what the change got right — it tells the author which parts of
the approach to keep. Then stop: this skill produces a report, not commits.
Offer to apply mechanical fixes and wait to be asked.

Done when: the verdict is in the file and no file in the reviewed branch was
changed.

## Verification

Merge-base SHA pinned and its diff non-empty; the delegate prompt carries that
SHA, the file list, the reading method, a budget and a stop rule; codex launched
read-only via `run_codex.sh` or its absence recorded; the delegate's coverage
line recorded; code-review-and-quality's quality axes
and spec axis reported; every Critical and required finding verified or
reproduced; findings attributed, numbered, severity-ranked; report saved as a
file that stands alone; verdict stated; reviewed branch left unmodified.
