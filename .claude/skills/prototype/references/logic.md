# Logic Prototype

Use this branch for business logic, state transitions, data shapes, and interfaces that only become clear when driven through concrete cases.

## Shape

Build one self-contained HTML file that opens directly. Put the logic in a pure module inside it: a reducer, explicit state machine, small set of pure functions, or stateful class with a clear method surface. The page is a thin shell and the logic has no DOM dependency.

Use domain language in labels and explanations so a non-developer can operate it.

## Interaction

Lay out:

1. The exact question and a one-line explanation.
2. Full relevant current state as labeled fields, refreshed after every action.
3. Free-play controls for every meaningful action.
4. Guided scenario tabs for the happy path, an awkward edge case, and an invalid action.

Each guided scenario starts from a known state and presents ordered, clickable steps. Keep styling restrained so state and actions dominate.

## Evidence and cleanup

Hand the file to the relevant user or domain expert and observe where their expectation differs from the model. Record those moments as evidence.

When the question is answered, write the verdict. Delete the demo, or deliberately promote the validated pure logic through test-driven development; the HTML shell remains throwaway.
