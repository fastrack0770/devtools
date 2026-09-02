---
name: prototype
description: Builds throwaway code to answer one unresolved design question. Use when sanity-checking whether a state model or logic feels right, exploring what a UI should look like, or facing a design question that cannot be settled on paper. Not for production code or exploration whose answer is already known.
---

# Prototype

A prototype is throwaway code that answers a question. The question decides the branch and bounds every implementation choice. Learn quickly, record the answer, then remove the artifact or deliberately promote the validated idea.

## 1. State the question

Write one concrete question the prototype must answer. Confirm that reading, sketching, or reasoning on paper cannot answer it cheaply and that the answer is not already known.

Done when: the question is written, falsifiable through interaction or observation, and narrow enough for one prototype.

## 2. Pick the branch

For “does this logic or state model feel right?”, load `references/logic.md`. Build an interactive, self-contained demonstration that drives difficult transitions and surfaces state.

For “what should this look like?”, load `references/ui.md`. This branch is web-specific and compares structurally different variants in their realistic page context.

If ambiguity remains and the user is unavailable, choose from surrounding code: backend or state logic suggests the logic branch; a web page or component suggests UI. Record the assumption prominently.

Done when: one branch clearly matches the written question and its required artifact is understood.

## 3. Apply the six rules

1. **Throwaway and marked as such.** Put it close to the code it explores and name it visibly as a prototype so readers do not mistake it for production.
2. **Trivial to run.** Give it one obvious command, or make a logic demo a single file that opens directly.
3. **No persistence by default.** Keep state in memory. If persistence is itself the question, use an isolated scratch store with a clear prototype name.
4. **Skip the polish.** Include only enough error handling and structure to keep the experiment runnable. Spend effort on learning, not production hardening.
5. **Surface the state.** Render or print all relevant state after every action or variant switch so changes remain observable.
6. **Capture it when done.** Record the question, verdict, evidence, and what the result changes before cleaning up the artifact.

Done when: the prototype follows all six rules and every feature directly helps answer the question.

## 4. Run the experiment

Exercise the cases most likely to overturn the design: happy path, awkward edge cases, invalid transitions, realistic density, or materially different layouts. Let users interact directly when their judgment is the evidence.

Revise the prototype only to resolve uncertainty in the written question. New questions become separate prototypes rather than speculative generalization.

Done when: observed evidence distinguishes the plausible answers and further prototype work would not change the decision.

## 5. Answer and dispose

Write the answer explicitly, including the evidence and any remaining uncertainty. Then choose one terminal path:

- **Delete** the prototype after its evidence and answer are captured in the appropriate work artifact.
- **Deliberately promote** the validated behavior or design. Treat it as production work: `Call the Skill tool with "test-driven-development"` and rebuild or harden it through that workflow.

Prototype constraints do not justify direct production shipping. Promotion changes the artifact's status and quality bar.

Done when: the question is answered in writing and the prototype is either deleted or deliberately promoted through test-driven development.

## Failure modes

- A prototype with no explicit question becomes an underbuilt product.
- Persistence, frameworks, abstractions, and polish obscure the experiment unless the question specifically needs them.
- Hidden state makes user feedback impressionistic rather than diagnostic.
- Keeping abandoned prototype paths in production creates misleading alternatives and maintenance burden.

## Verification

One written question determined the branch; the artifact was clearly throwaway and trivial to run; relevant state and decisive cases were visible; the answer and evidence are written; the prototype has been deleted or deliberately promoted through test-driven development.
