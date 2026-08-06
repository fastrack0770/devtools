/* Claude Code provider: reads claude-usage-helper.py.
 *
 * The helper returns the session window plus, when present, the weekly
 * and model-scoped quotas. The bar tracks the 5-hour session — the
 * shortest window Claude reports.
 */
'use strict';

const { GLib } = imports.gi;
const ExtensionUtils = imports.misc.extensionUtils;
const Me = ExtensionUtils.getCurrentExtension();
const Format = Me.imports.lib.format;

const CREDS_PATH = GLib.build_filenamev([GLib.get_home_dir(), '.claude', '.credentials.json']);

function clamp(value) {
    return Math.max(0, Math.min(100, Number(value) || 0));
}

var provider = {
    id: 'claude',
    title: 'Claude',
    helper: 'claude-usage-helper.py',

    /* The helper reads the OAuth token the claude CLI stores here; without
     * that file there is nothing to show, so the indicator stays away. */
    detect() {
        return GLib.file_test(CREDS_PATH, GLib.FileTest.EXISTS);
    },

    parse(data) {
        if (typeof data.percent !== 'number')
            return null;

        const percent = clamp(data.percent);
        const resetsAt = Format.isoToUnix(data.resets_at);
        const rows = ['Session (5 h): %d%% used, %s left (resets at %s)'.format(
            Math.round(percent),
            resetsAt ? Format.formatRemaining(resetsAt) : '?',
            resetsAt ? Format.formatReset(resetsAt) : '?')];

        if (data.seven_day_percent !== undefined) {
            const weekReset = Format.isoToUnix(data.seven_day_resets_at);
            rows.push('Week: %d%% used, resets %s'.format(
                Math.round(clamp(data.seven_day_percent)),
                weekReset ? Format.formatReset(weekReset) : '?'));
        }

        let suffix = null;
        if (data.model_percent !== undefined) {
            const name = data.model_name || 'model';
            const modelReset = Format.isoToUnix(data.model_resets_at);
            rows.push('%s: %d%% used, resets %s'.format(
                name,
                Math.round(clamp(data.model_percent)),
                modelReset ? Format.formatReset(modelReset) : '?'));
            suffix = ' · %s %d%%'.format(name, Math.round(clamp(data.model_percent)));
        }

        return { percent, resetsAt, stale: false, suffix, rows, note: null };
    },
};
