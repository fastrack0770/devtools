/* Everything the two entry points have in common: which providers exist,
 * how often they are polled, and the bookkeeping that adds and drops one
 * indicator per logged-in CLI.
 *
 * This file knows nothing about how it was loaded. The shell's UI modules
 * arrive as `shell` — { Main, PanelMenu, PopupMenu, MessageTray } — because
 * GNOME 42 and GNOME 45+ obtain them in incompatible ways; see extension.js
 * and extension-esm.js.
 */
'use strict';

const { GLib } = imports.gi;
const Indicator = imports.aiusagelib.indicator;

const POLL_SECONDS = 60;

const PROVIDERS = [
    imports.aiusagelib.claude.provider,
    imports.aiusagelib.codex.provider,
];

var Controller = class Controller {
    constructor(shell, extensionPath) {
        this._shell = shell;
        this._extensionPath = extensionPath;
        this._UsageIndicator = Indicator.getUsageIndicatorClass(shell);
        this._indicators = new Map();
        this._timeoutId = null;
    }

    enable() {
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
                const indicator = new this._UsageIndicator(provider, this._extensionPath);
                this._shell.Main.panel.addToStatusArea(
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
};
