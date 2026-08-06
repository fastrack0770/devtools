/* Minimal stand-in for GNOME Shell's imports.misc.extensionUtils.
 *
 * Only exists so lib/claude.js and lib/codex.js can be loaded by plain gjs:
 * they ask for the extension object purely to reach Me.imports.lib.format.
 * Handing back the global importer works because the test runner puts the
 * extension directory on imports.searchPath.
 */
'use strict';

var getCurrentExtension = function () {
    return { imports: imports, path: '.' };
};
