/* Claude Code provider: identity only.
 *
 * The parsing that used to live here moved into the shared Python runtime
 * (design.md D2), so a change in Claude's API is now fixed once, in one
 * language, for both this panel and the Godot Shell. What is left is what the
 * panel calls this provider and which key it occupies in the usage document.
 *
 * Whether the CLI is set up here is no longer guessed from a credentials file
 * either: the runtime reports `unavailable` for a CLI that is not logged in.
 */
'use strict';

var provider = {
    id: 'claude',
    title: 'Claude',
};
