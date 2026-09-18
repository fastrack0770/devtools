/* Running the shared runtime once and handing back its document.
 *
 * The runtime is installed separately from this extension, at a stable
 * user-level path, because the Godot Shell reads it too and must not depend on
 * the extension's private directory (design.md D1). Removing the extension
 * therefore does not remove the runtime, and vice versa.
 *
 * Freshness, the file lock and the per-provider backoff all live inside that
 * runtime: ordinary polling here is cheap because the answer is usually the
 * cached one, and two clients polling the same minute cost one request.
 */
'use strict';

const { GLib, Gio } = imports.gi;

var DEFAULT_BIN = GLib.build_filenamev(
    [GLib.get_home_dir(), '.local', 'libexec', 'ai-usage-control', 'ai-usage']);

/* AI_USAGE_BIN points the extension at a working copy during development. */
var binary = function () {
    return GLib.getenv('AI_USAGE_BIN') || DEFAULT_BIN;
};

var isInstalled = function () {
    return GLib.file_test(binary(), GLib.FileTest.EXISTS);
};

/* Fetch asynchronously and call back with (document, error).
 * `force` is the manual "Refresh now": it skips the freshness window, while the
 * runtime still honours a rate limit's Retry-After. */
var fetch = function (force, callback) {
    const argv = [binary()];
    if (force)
        argv.push('--force');

    let proc;
    try {
        proc = Gio.Subprocess.new(
            argv, Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE);
    } catch (e) {
        callback(null, 'helper');
        return;
    }

    proc.communicate_utf8_async(null, null, (p, res) => {
        /* Finish the operation even when the answer is about to be thrown
         * away — an async call left unfinished holds its pipes open. */
        let stdout;
        try {
            [, stdout] = p.communicate_utf8_finish(res);
        } catch (e) {
            callback(null, 'helper');
            return;
        }
        let document;
        try {
            document = JSON.parse(stdout);
        } catch (e) {
            callback(null, 'parse');
            return;
        }
        callback(document, null);
    });
};
