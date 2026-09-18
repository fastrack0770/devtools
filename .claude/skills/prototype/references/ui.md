# Web UI Prototype

This branch is specifically for web UI questions. Compare several structurally different renderings in the realistic context where the UI will live.

## Shape

Prefer an existing page with its real header, navigation, data, auth, and density. Switch only the rendered subtree. Use a new throwaway route only when no existing page can host the experiment.

Create three variants by default and no more than five. Make them differ in layout, information hierarchy, and primary affordance rather than only color or copy.

Select variants with a shareable `?variant=` URL parameter and a small fixed bottom switcher. Support previous and next controls and left/right keyboard navigation, except while an editable control has focus. Make the switcher visibly experimental and unavailable in production builds.

## Evidence and cleanup

Give every variant the same realistic inputs. Ask users which structure supports the task and which pieces should combine; record the chosen variant and why.

After answering the question, remove losing variants and the switcher. Delete the prototype, or deliberately promote the winner through test-driven development before treating it as production code.
