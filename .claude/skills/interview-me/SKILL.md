---
name: interview-me
description: Extracts what the user actually wants instead of what they think they should want, via one-question-at-a-time interview until ~95% confidence. Use when an ask is underspecified ("build me X" without who/why/success), when the user invokes it ("interview me", "grill me", "stress-test my thinking"), or when you catch yourself silently filling in ambiguous requirements. Not for unambiguous self-contained asks, pure information requests, mechanical operations, or non-interactive contexts (CI, loops) — there, flag the gap as a blocker instead.
---

# Interview Me

What people ask for and what they want are different things — "a dashboard" is what one asks for, not necessarily what solves the problem. The cheapest moment to find that gap is before any plan, spec, or code exists; afterwards, switching costs make the user rationalize the wrong thing into "good enough".

This runs *before* the other Define-phase skills: opsx:explore refines an idea you roughly have, spec-driven-development writes down what's already understood, doubt-driven-development stress-tests a drafted decision. Interview-me produces the understanding they all consume.

## The process

**1. Hypothesize, with a confidence number.** One sentence — your best read of the underlying want — plus an honest 0–100%. Below ~70%, append what's missing on the same line ("~30% — missing: who it's for, what success looks like"). If you claim a high number but can't predict the user's reactions to your next three questions, the number is wrong.

**2. One question at a time, each with a guess attached.**

```
Q:     <one focused question>
GUESS: <your hypothesis for the answer, with the reasoning behind it>
```

Wait for the reaction before the next question. One at a time because the third question depends on the first answer, and batches get skim-read. Guess attached because reacting to a wrong guess is faster than generating from scratch — and it exposes *your* assumptions, which is the point. The risk is a polite user agreeing to be agreeable; mitigate by being visibly willing to be wrong and occasionally guessing where you expect pushback.

**3. Listen for "want vs. should-want."** The dangerous answers sound thoughtful without being specific: "scalable", "clean architecture", "the standard approach", "I'm supposed to…". When you hear one, ask: *"If you didn't have to justify this to anyone, what would you actually want?"* — that question often does more work than the previous five.

**4. Restate in the user's own words** when confidence is high — 5–8 lines they can confirm line by line:

```
- Outcome:      <one line>
- User:         <who benefits>
- Why now:      <what changed>
- Success:      <how we know it worked>
- Constraint:   <the binding limit>
- Out of scope: <what we're explicitly not doing>
Yes / no / refine?
```

"Out of scope" is non-negotiable — half of misalignment is silent disagreement about what is *not* being built.

**5. Confirm — an explicit yes.** These are not yes: "whatever you think is best" (delegation — re-ask with two concrete options), "sounds good" / "sure, let's go" (ambiguous — ask what they'd refine), silence then "okay start" (the user gave up, not converged — ask what you missed). Fold corrections in, restate, loop until an explicit yes.

## The 95% stop

Done when you can answer yes to: *can I predict the user's reaction to the next three questions I would ask?* — a checkable test, not a vibe. It has a floor: several rounds with no rising confidence is information about the ask, not a reason to grind. Say so: "I've asked X questions and still can't predict your reactions — something foundational is missing. Step back?"

## Output

A **confirmed statement of intent** — the Step 4 restate with an explicit yes. Specs, plans, and tasks are downstream consumers. For multi-session work or handoffs, offer to save it to `docs/intent/<topic>.md` — only after the confirmation, never before (the saved doc implies a yes the user didn't give).

## Worked contrast

"Build me a dashboard for our metrics" taken literally → chart libraries and layouts on four unstated assumptions. Interviewed → two questions in, it turns out the user personally keeps losing track of running experiments, and there is no list of them anywhere. The right artifact is a list, not a dashboard — different scope, different work, discovered at the cost of two questions.

## Downstream handoffs

Hand the *confirmed intent* (never the original underspecified ask) to opsx:explore when scoping is still open, or to spec-driven-development when the intent is concrete. doubt-driven-development sits at the opposite end of the timeline: it reviews decisions after they're drafted; this skill extracts intent before.
