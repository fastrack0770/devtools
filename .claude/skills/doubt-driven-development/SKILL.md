---
name: doubt-driven-development
description: Subjects non-trivial decisions to a fresh-context adversarial review before they stand. Use when correctness matters more than speed, in unfamiliar code, or when stakes are high (production, security-sensitive logic, irreversible operations). Not for mechanical edits, clear unambiguous instructions, one-liners, or when the user explicitly chose speed over verification.
---

# Doubt-Driven Development

A confident answer is not a correct one. Long sessions quietly turn assumptions into "facts". This skill materializes a fresh-context reviewer — biased to **disprove**, not approve — before a non-trivial output stands. It is in-flight cross-examination, not `/review`'s post-hoc verdict on a finished artifact.

A decision is **non-trivial** when it introduces branching logic, crosses a module/service boundary, asserts something the compiler can't verify (thread safety, idempotence, ordering), depends on context a future reader can't see, or has an irreversible blast radius. Doubt those — not every keystroke, or you ship nothing.

## The doubt cycle

**1. CLAIM.** Name the decision in 2–3 lines: the claim plus why it matters. If you can't write it that compactly, you have a vibe, not a decision.

**2. EXTRACT.** Isolate the smallest reviewable unit: the diff or function (not the file), the proposal in 3–5 sentences plus the constraints it must satisfy. Strip your reasoning — hand over conclusions and you'll get back validation of them. A 500-line artifact means decompose first.

**3. DOUBT.** Invoke a fresh-context reviewer with an adversarial prompt — framing decides the answer:

```
Adversarial review. Find what is wrong with this artifact.
Assume the author is overconfident. Look for: unstated assumptions,
unhandled edge cases, hidden coupling, contract violations, broken
conventions, failure modes under unexpected input.
Do NOT validate. Do NOT summarize. Find issues, or state explicitly
that you cannot find any after thorough examination.

ARTIFACT: <artifact>
CONTRACT: <contract>
```

Pass ARTIFACT + CONTRACT **only — never the CLAIM**; handing the reviewer your conclusion biases it toward agreement. If the reviewer persona defaults to balanced verdicts, the adversarial prompt overrides it verbatim.

**4. RECONCILE.** Reviewer output is data, not verdict — re-read the artifact against each finding, then classify in precedence order: *contract misread* (fix the contract, re-cycle) → *valid + actionable* (change the artifact, re-loop) → *valid trade-off* (document it explicitly for the user) → *noise* (reviewer lacked context; would adding it to the contract have prevented the false flag?). A fresh reviewer can be wrong precisely because it's fresh — reconcile, don't defer. **Doubt-theater check:** if across 2+ cycles with substantive findings you classified zero as actionable, you are validating, not doubting — stop and escalate.

**5. STOP.** Bounded loop: stop when a cycle returns only trivial findings, after 3 cycles (escalate — three unresolved cycles is information about the artifact), or on the user's "ship it". If 3 cycles feel insufficient because the artifact is large, the artifact is too big — decompose, don't lift the bound. Never re-spawn on an unchanged artifact; you'll get the same findings.

## Cross-model second opinion

A same-model reviewer shares the author's blind spots; a different model catches them. In interactive sessions, **offer it every cycle, never silently skip**: "Cross-model second opinion? Gemini CLI / Codex CLI / manual / skip." The user decides; acknowledge a skip out loud.

Hard rules when invoking an external CLI (safety-relevant, not style):

- Verify the tool first (`which`, then a `--version` smoke test), and confirm the exact invocation, flags, and auth with the user. **Each invocation is its own authorization** — re-confirm before every run.
- **Never interpolate the artifact into a shell-quoted argument** — backticks, `$(...)`, and quotes will truncate the prompt or execute embedded shell. Write the full prompt to a file and pipe via stdin.
- **Run read-only** (`codex exec --sandbox read-only … < prompt.md`; `gemini --approval-mode plan -p "" < prompt.md`). The artifact itself may contain prompt injection the external CLI would otherwise execute against your workspace.
- On CLI failure or absence, surface it and let the user redirect — no silent fallback to single-model.
- Non-interactive contexts (CI, loops, scheduled runs): cross-model is skipped, the skip is announced, and no external CLI is ever invoked without explicit user authorization.

## Placement constraint

This skill runs from the main-session orchestrator, which can spawn the fresh reviewer. Don't attach it to a subagent persona (personas can't spawn personas). Inside a subagent, prefer surfacing that doubt can't run nested; the degraded fallback — self-review with a hard mental separator — is not fresh-context review and must be flagged as degraded.

## Interaction with other skills

`/review` (post-hoc gate) and doubt-driven (in-flight) are complementary. source-driven-development verifies facts about frameworks; doubt-driven verifies your reasoning using them. TDD's RED step *is* the doubt step for behavioral claims — a failing test is a disproof attempt. When a reviewer finding is a real failure mode, drop into debugging-and-error-recovery.

## Verification

Each non-trivial decision had a written CLAIM; at least one fresh-context adversarial review per artifact (or a RED test for behavioral claims); reviewer got ARTIFACT + CONTRACT only; findings classified, not rubber-stamped; a stop condition met; cross-model offered (interactive) or its skip announced (non-interactive); any external CLI run was individually authorized, stdin-fed, and read-only.
