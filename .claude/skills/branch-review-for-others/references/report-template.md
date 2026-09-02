# Report template

The reader is the author of the change or a maintainer, working through the
file without you. Save it as Markdown, one finding per entry. Keep the headings
that have findings and drop the empty ones. Translate headings into the
repository's documentation language; keep the severity prefixes in English.

```markdown
# Review of `<branch>` against `<base>`

<One or two lines: what the change is, diff size, what it consists of
(e.g. +5577 lines, ~1200 of them code, the rest docs/specs). How the review was
done: the reviewing model's own pass plus an independent read-only codex pass.>

## Critical

- [ ] **1. `path/to/file:line` — <defect in one sentence>** *(codex; reproduced)*

  <What breaks and why. A code fragment when it shortens the explanation.>

  <Failure scenario: the inputs or state under which the system misbehaves.>

  <Reproduction when there is one — the command and its output, not a
  paraphrase.>

  <What to do.>

## Required before merge

- [ ] **2. `path:line` — <defect>** *(both, independently)*

  <Failure scenario. What to do.>

## Spec

<Reported separately from the quality findings. Requirements missing or
partial; behaviour not asked for; requirements that look implemented but are
wrong — each with the spec line quoted. Or: "No spec available."
Spec items that block merge are numbered and checkboxed like the sections
above.>

## Consider

- **`path:line`** *(claude)* — <finding and why it is worth weighing>

## Nit / FYI

- **`path:line`** *(codex)* — <small thing>
- **FYI** — <context>

## Not verified

<What the review could not check and why: a test suite that does not run in
this environment, hardware not available, codex unavailable so the review is
single-pass.>

## What the change got right

<Short and specific — which decisions to keep. It tells the author which part
of the approach to leave alone.>

## Verdict

**Request changes** / **Approve**. <What blocks. Whether the change should be
split. One line on what the reviewer is ready to fix on request.>
```

## Numbering and ordering

Number Critical, required, and blocking spec findings continuously across their
sections and order them by severity — the reader works top-down and the first
item should be the one that would break production. Each numbered finding gets
a checkbox so the author can tick it off in the MR. `Consider`, `Nit`, and
`FYI` stay unnumbered bullets: a menu, not a queue.

## Attribution

Mark each finding with the model that found it — *(claude)*, *(codex)*,
*(both, independently)* — and add *(reproduced)* where you ran the repro. Two
independent passes converging on the same defect is the strongest evidence in
the report, and it is invisible unless written down.

## Self-containment

Every path resolves in the repository at the reviewed commit; every
cross-reference names a numbered finding; every command shown is one the reader
can run from the repository root. Session details — scratchpad paths, what was
said in the conversation — stay out.
