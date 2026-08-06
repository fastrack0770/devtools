/* AI Usage — GNOME 42 top-panel indicators for coding-agent usage limits.
 *
 * One progress bar per provider (Claude Code, Codex CLI): the used share of
 * the shortest limit window, blue < 75%, yellow 75-90%, red >= 90%, with a
 * countdown to the reset and notifications at 20/40/60/80/90/100%.
 *
 * There is no settings UI on purpose. A provider's bar appears when that
 * CLI is installed and logged in and disappears when it is not, rechecked
 * on every poll — so logging in to either tool brings its bar up within a
 * minute, with nothing to configure.
 */
'use strict';

const { GLib } = imports.gi;
const Main = imports.ui.main;
const ExtensionUtils = imports.misc.extensionUtils;
const Me = ExtensionUtils.getCurrentExtension();
const { UsageIndicator } = Me.imports.lib.indicator;

const POLL_SECONDS = 60;

const PROVIDERS = [
    Me.imports.lib.claude.provider,
    Me.imports.lib.codex.provider,
];

class Extension {
    enable() {
        this._indicators = new Map();
        this._sync();
        this._timeoutId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, POLL_SECONDS, () => {
            this._sync();
            return GLib.SOURCE_CONTINUE;
        });
    }

    /* Add, drop and poll indicators to match which CLIs are logged in. */
    _sync() {
        PROVIDERS.forEach((provider, index) => {
            const existing = this._indicators.get(provider.id);
            let present;
            try {
                present = provider.detect();
            } catch (e) {
                logError(e, 'ai-usage: %s detection failed'.format(provider.id));
                present = !!existing;
            }

            if (present && !existing) {
                const indicator = new UsageIndicator(provider);
                Main.panel.addToStatusArea(
                    'ai-usage-%s'.format(provider.id), indicator, index + 1, 'right');
                this._indicators.set(provider.id, indicator);
                indicator.refresh();
            } else if (present) {
                existing.refresh();
            } else if (existing) {
                existing.destroy();
                this._indicators.delete(provider.id);
            }
        });
    }

    disable() {
        if (this._timeoutId) {
            GLib.source_remove(this._timeoutId);
            this._timeoutId = null;
        }
        for (const indicator of this._indicators.values())
            indicator.destroy();
        this._indicators.clear();
    }
}

function init() {
    return new Extension();
}
