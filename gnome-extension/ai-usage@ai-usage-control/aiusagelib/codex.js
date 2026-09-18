/* Codex CLI provider: identity only.
 *
 * See aiusagelib/claude.js — the window parsing, the app-server/journal source
 * split and the per-window expiry rule all moved into the shared Python runtime
 * (design.md D2). Codex reports no fixed set of windows, and nothing in the
 * renderer assumes one exists.
 */
'use strict';

var provider = {
    id: 'codex',
    title: 'Codex',
};
