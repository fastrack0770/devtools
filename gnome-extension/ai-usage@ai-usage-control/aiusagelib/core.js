/* Everything the two entry points have in common: which providers exist,
 * how often they are polled, and the bookkeeping that adds and drops one
 * indicator per logged-in CLI.
 *
 * One fetch now covers every provider: the shared runtime answers for all of
 * them in a single document (design.md D2, D4), so the panel no longer starts
 * one subprocess per CLI per minute.
 *
 * This file knows nothing about how it was loaded. The shell's UI modules
 * arrive as `shell` — { Main, PanelMenu, PopupMenu, MessageTray } — because
 * GNOME 42 and GNOME 45+ obtain them in incompatible ways; see extension.js
 * and extension-esm.js.
 */
'use strict';

const { GLib } = imports.gi;
const Indicator = imports.aiusagelib.indicator;
const Model = imports.aiusagelib.model;
const Usage = imports.aiusagelib.usage;

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
        this._generation = 0;
    }

    enable() {
        this.refresh(false);
        this._timeoutId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, POLL_SECONDS, () => {
            this.refresh(false);
            return GLib.SOURCE_CONTINUE;
        });
    }

    /* `force` comes from an indicator's "Refresh now" and skips the runtime's
     * freshness window; a rate limit's pause is still honoured there. */
    refresh(force) {
        /* Replies are applied in completion order, not request order, so a slow
         * poll finishing after a quick "Refresh now" would overwrite the fresher
         * numbers. Only the newest request may touch the panel. */
        const generation = ++this._generation;
        Usage.fetch(force, (document, error) => {
            if (generation !== this._generation)
                return;
            if (error) {
                this._failAll(error);
                return;
            }
            const providers = Model.providersOf(document);
            if (!providers) {
                this._failAll('parse');
                return;
            }
            this._apply(providers);
        });
    }

    /* Add, drop and update indicators to match which CLIs are logged in. */
    _apply(providers) {
        PROVIDERS.forEach((provider, index) => {
            const entry = providers[provider.id];
            const existing = this._indicators.get(provider.id);

            if (!Model.isPresent(entry)) {
                if (existing) {
                    existing.destroy();
                    this._indicators.delete(provider.id);
                }
                return;
            }

            let indicator = existing;
            if (!indicator) {
                indicator = new this._UsageIndicator(
                    provider, () => this.refresh(true));
                this._shell.Main.panel.addToStatusArea(
                    'ai-usage-%s'.format(provider.id), indicator, index + 1, 'right');
                this._indicators.set(provider.id, indicator);
            }
            indicator.update(entry);
        });
    }

    /* The runtime itself failed, so nothing is known about any provider: the
     * panels that already have numbers keep them, dimmed. */
    _failAll(reason) {
        for (const indicator of this._indicators.values())
            indicator.showError(reason);
    }

    disable() {
        if (this._timeoutId) {
            GLib.source_remove(this._timeoutId);
            this._timeoutId = null;
        }
        this._generation++;
        for (const indicator of this._indicators.values())
            indicator.destroy();
        this._indicators.clear();
    }
};
