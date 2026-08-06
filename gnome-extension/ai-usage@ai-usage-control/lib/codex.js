/* Codex CLI provider: reads codex-usage-helper.py.
 *
 * Codex does not report a fixed set of windows the way Claude does — a Plus
 * account may return a single weekly limit and nothing else — so nothing
 * here assumes a 5-hour window exists. The helper sorts the windows it got
 * shortest-first and the bar tracks the first one; the rest go to the menu.
 *
 * The helper's second source (the session journal) is a snapshot from
 * whenever Codex last ran, so `stale` dims the indicator. If such a snapshot
 * has already outlived its own reset time, the percentage is dropped rather
 * than shown as a confident 0% — the window may well have been spent from
 * an IDE or the web in the meantime.
 */
'use strict';

const { GLib } = imports.gi;
const ExtensionUtils = imports.misc.extensionUtils;
const Me = ExtensionUtils.getCurrentExtension();
const Format = Me.imports.lib.format;

const AUTH_PATH = GLib.build_filenamev([GLib.get_home_dir(), '.codex', 'auth.json']);

function nowUnix() {
    return GLib.get_real_time() / 1000000;
}

var provider = {
    id: 'codex',
    title: 'Codex',
    helper: 'codex-usage-helper.py',

    detect() {
        return GLib.file_test(AUTH_PATH, GLib.FileTest.EXISTS);
    },

    parse(data) {
        const windows = Array.isArray(data.windows) ? data.windows : [];
        if (!windows.length)
            return null;

        const stale = data.source !== 'app-server';
        const nowSec = nowUnix();

        /* Expiry is per window: a snapshot can be new enough for the 5-hour
         * limit and long past the weekly one, or the other way round. An
         * expired window's old percentage is dropped everywhere — bar, menu
         * row and suffix alike — not just on the bar, otherwise the menu
         * would still quote a number the panel refuses to show. */
        const shown = windows.map(w => ({
            minutes: w.minutes,
            percent: w.percent,
            resets_at: w.resets_at,
            expired: stale && !!w.resets_at && w.resets_at <= nowSec,
        }));

        const rows = shown.map(w => w.expired
            ? '%s: — window has reset, waiting for fresh data'.format(
                Format.formatWindow(w.minutes))
            : '%s: %d%% used, %s left (resets at %s)'.format(
                Format.formatWindow(w.minutes),
                Math.round(w.percent),
                w.resets_at ? Format.formatRemaining(w.resets_at) : '?',
                w.resets_at ? Format.formatReset(w.resets_at) : '?'));

        const bar = shown[0];
        const expired = bar.expired;

        if (data.credits) {
            rows.push('Credits: %s'.format(
                data.credits.unlimited ? 'unlimited' : data.credits.balance));
        }
        if (data.limit_reached)
            rows.push('Limit reached: %s'.format(data.limit_reached));
        if (data.plan)
            rows.push('Plan: %s'.format(data.plan));

        let suffix = null;
        if (!expired && shown.length > 1 && !shown[1].expired) {
            suffix = ' · %s %d%%'.format(
                Format.formatWindow(shown[1].minutes),
                Math.round(shown[1].percent));
        }

        return {
            percent: expired ? null : bar.percent,
            resetsAt: bar.resets_at || 0,
            stale,
            suffix,
            rows,
            note: stale
                ? 'from session journal, %s'.format(Format.formatAge(data.age_seconds || 0))
                : null,
        };
    },
};
