/* Shared panel indicator: one progress bar for one usage provider.
 *
 * Everything provider-independent lives here — the bar, the colours, the
 * countdown, the threshold notifications and their persisted state, the
 * error handling and the staleness dimming. A provider (lib/claude.js,
 * lib/codex.js) only says which helper to run and how to turn its JSON
 * into the render model below:
 *
 *   { percent, resetsAt, stale, suffix, rows, note }
 *
 * `percent` null means "no trustworthy number" and renders as an em dash;
 * `resetsAt` is Unix seconds; `stale` dims the whole indicator.
 */
'use strict';

const { St, GLib, Gio, GObject, Clutter } = imports.gi;
const Main = imports.ui.main;
const PanelMenu = imports.ui.panelMenu;
const PopupMenu = imports.ui.popupMenu;
const MessageTray = imports.ui.messageTray;
const ExtensionUtils = imports.misc.extensionUtils;
const Me = ExtensionUtils.getCurrentExtension();
const Format = Me.imports.lib.format;

const TICK_SECONDS = 20; // countdown label refresh between polls
const BACKOFF_SECONDS = 300; // pause polling after the endpoint rate-limits us
const TRACK_WIDTH = 70;
const TRACK_HEIGHT = 8;
const THRESHOLDS = [20, 40, 60, 80, 90, 100];
const WINDOW_TOLERANCE_SECONDS = 300;
const STALE_OPACITY = 110;
const STATE_DIR = GLib.build_filenamev([GLib.get_user_cache_dir(), 'ai-usage-control']);

/* Helper error codes the user can actually act on. Anything absent falls
 * back to the raw code, which is still enough to grep the helpers for. */
const ERROR_MESSAGES = {
    no_credentials: 'Not logged in',
    not_logged_in: 'Not logged in',
    no_refresh_token: 'Session expired — log in again',
    refresh_token_expired: 'Session expired — log in again',
    unauthorized: 'Session expired — log in again',
    network: 'No connection to the usage endpoint',
    helper: 'Helper failed to start',
    parse: 'Unexpected helper output',
    no_codex_cli: 'codex CLI not found',
    no_usage_data: 'No usage data yet — run codex once',
};

function errorMessage(reason) {
    return ERROR_MESSAGES[reason] || reason;
}

function fillClassFor(percent) {
    if (percent >= 90)
        return 'cu-fill cu-fill-red';
    if (percent >= 75)
        return 'cu-fill cu-fill-yellow';
    return 'cu-fill cu-fill-blue';
}

function now() {
    return GLib.get_real_time() / 1000000;
}

var UsageIndicator = GObject.registerClass(
class UsageIndicator extends PanelMenu.Button {
    _init(provider) {
        super._init(0.5, '%s Usage'.format(provider.title));
        this._provider = provider;
        this._statePath = GLib.build_filenamev(
            [STATE_DIR, 'state-%s.json'.format(provider.id)]);

        this._box = new St.BoxLayout({ style_class: 'cu-box', y_align: Clutter.ActorAlign.CENTER });
        this._titleLabel = new St.Label({
            text: provider.title,
            style_class: 'cu-title',
            y_align: Clutter.ActorAlign.CENTER,
        });
        this._track = new St.Widget({
            style_class: 'cu-track',
            y_align: Clutter.ActorAlign.CENTER,
            width: TRACK_WIDTH,
            height: TRACK_HEIGHT,
        });
        this._fill = new St.Widget({ style_class: 'cu-fill cu-fill-gray', height: TRACK_HEIGHT });
        this._fill.set_position(0, 0);
        this._track.add_child(this._fill);
        this._infoLabel = new St.Label({ text: '…', y_align: Clutter.ActorAlign.CENTER });

        this._box.add_child(this._titleLabel);
        this._box.add_child(this._track);
        this._box.add_child(this._infoLabel);
        this.add_child(this._box);

        this._rowItems = [];
        this._updatedItem = new PopupMenu.PopupMenuItem('Updated: —', { reactive: false });
        this._rowSection = new PopupMenu.PopupMenuSection();
        this.menu.addMenuItem(this._rowSection);
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this.menu.addMenuItem(this._updatedItem);
        const refreshItem = new PopupMenu.PopupMenuItem('Refresh now');
        refreshItem.connect('activate', () => this.refresh(true));
        this.menu.addMenuItem(refreshItem);

        this._notifyState = this._loadState();
        this._model = null;
        this._backoffUntil = 0;
        this._destroyed = false;
        this._generation = 0;

        // keep the countdown fresh between polls
        this._tickId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, TICK_SECONDS, () => {
            if (this._model)
                this._render();
            return GLib.SOURCE_CONTINUE;
        });
    }

    /* `force` comes from the menu item and ignores the rate-limit backoff. */
    refresh(force = false) {
        if (!force && now() < this._backoffUntil)
            return;

        /* Replies are applied in completion order, not request order, so a
         * slow poll finishing after a quick "Refresh now" would overwrite
         * the fresher numbers — or, if it failed, mark them stale and start
         * a backoff. Only the newest request may touch the widget. */
        const generation = ++this._generation;

        let proc;
        try {
            proc = Gio.Subprocess.new(
                ['python3', GLib.build_filenamev([Me.path, this._provider.helper])],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE);
        } catch (e) {
            this._showError('helper');
            return;
        }
        proc.communicate_utf8_async(null, null, (p, res) => {
            /* Finish the operation even when the answer is about to be
             * thrown away — an async call left unfinished holds its pipes
             * and its GTask open. */
            let stdout;
            try {
                [, stdout] = p.communicate_utf8_finish(res);
            } catch (e) {
                if (!this._destroyed && generation === this._generation)
                    this._showError('helper');
                return;
            }
            if (this._destroyed || generation !== this._generation)
                return;
            try {
                const data = JSON.parse(stdout);
                if (!data.ok) {
                    this._showError(data.error);
                    return;
                }
                const model = this._provider.parse(data);
                if (!model) {
                    this._showError('parse');
                    return;
                }
                this._backoffUntil = 0;
                this._model = model;
                this._render();
                this._updatedItem.label.text = model.note
                    ? 'Updated: %s (%s)'.format(
                        GLib.DateTime.new_now_local().format('%H:%M:%S'), model.note)
                    : 'Updated: %s'.format(GLib.DateTime.new_now_local().format('%H:%M:%S'));
                if (model.percent !== null && !model.stale)
                    this._maybeNotify(model.percent, model.resetsAt);
            } catch (e) {
                this._showError('parse');
            }
        });
    }

    _render() {
        const model = this._model;
        const known = model.percent !== null;
        const percent = known ? Math.max(0, Math.min(100, model.percent)) : 0;
        const remaining = model.resetsAt ? Format.formatRemaining(model.resetsAt) : '?';

        if (known) {
            let width = Math.round(TRACK_WIDTH * percent / 100);
            if (percent > 0 && width < 2)
                width = 2;
            this._fill.set_size(width, TRACK_HEIGHT);
            this._fill.style_class = fillClassFor(percent);
            // every percentage below is the *used* share of a limit, never the remainder
            let info = '%d%% · %s'.format(Math.round(percent), remaining);
            if (model.suffix)
                info += model.suffix;
            this._infoLabel.text = info;
        } else {
            this._fill.set_size(TRACK_WIDTH, TRACK_HEIGHT);
            this._fill.style_class = 'cu-fill cu-fill-gray';
            this._infoLabel.text = '—';
        }

        /* A snapshot that is merely old still carries a usable number, so it
         * is shown — just dimmed, so it never passes for a live reading. */
        this._box.opacity = model.stale ? STALE_OPACITY : 255;

        this._setRows(model.rows);
    }

    _setRows(rows) {
        while (this._rowItems.length > rows.length) {
            this._rowItems.pop().destroy();
        }
        while (this._rowItems.length < rows.length) {
            const item = new PopupMenu.PopupMenuItem('', { reactive: false });
            this._rowSection.addMenuItem(item);
            this._rowItems.push(item);
        }
        rows.forEach((text, i) => {
            this._rowItems[i].label.text = text;
        });
    }

    _showError(reason) {
        if (reason === 'usage_http_429')
            this._backoffUntil = now() + BACKOFF_SECONDS;

        /* A rate limit or network blip should not blank a working panel:
         * keep the last known numbers and flag them as stale instead. */
        if (this._model) {
            this._model.stale = true;
            this._render();
            this._updatedItem.label.text = 'Stale — error at %s (%s)'.format(
                GLib.DateTime.new_now_local().format('%H:%M:%S'), reason);
            return;
        }

        this._fill.set_size(TRACK_WIDTH, TRACK_HEIGHT);
        this._fill.style_class = 'cu-fill cu-fill-gray';
        this._box.opacity = 255;
        this._infoLabel.text = '—';
        this._setRows([errorMessage(reason)]);
        this._updatedItem.label.text =
            'Error at %s'.format(GLib.DateTime.new_now_local().format('%H:%M:%S'));
    }

    _maybeNotify(percent, resetsAt) {
        /* The server recomputes the reset time on every poll, so it jitters
         * by a fraction of a second — and when it happens to sit next to a
         * minute boundary it flips back and forth across it. Anchoring the
         * window on an exact timestamp made that flip look like a new
         * window, which reset `notified` and re-sent every threshold.
         * Only a jump of minutes is a real rollover; a response with no
         * reset time at all leaves the current window alone. */
        const stamp = resetsAt || 0;
        const rolled = stamp &&
            Math.abs(stamp - this._notifyState.window) > WINDOW_TOLERANCE_SECONDS;

        let highest = 0;
        for (const t of THRESHOLDS) {
            if (percent >= t)
                highest = t;
        }

        /* First sighting of this provider: adopt whatever is already
         * crossed as the baseline instead of firing every threshold below
         * it at once. Installing at 85% should announce 90%, not 20-80. */
        if (!this._notifyState.seeded) {
            this._notifyState = { window: stamp, notified: highest, seeded: true };
            this._saveState();
            return;
        }
        if (rolled) {
            // new window: thresholds fire again
            this._notifyState = { window: stamp, notified: 0, seeded: true };
            this._saveState();
        }

        if (highest <= this._notifyState.notified)
            return;

        this._notifyState.notified = highest;
        this._saveState();

        const remaining = resetsAt ? Format.formatRemaining(resetsAt) : '?';
        const resetAt = resetsAt ? Format.formatReset(resetsAt) : '?';
        const title = '%s: %d%%'.format(this._provider.title, highest);
        const body = highest >= 100
            ? 'Limit reached. Resets in %s (at %s).'.format(remaining, resetAt)
            : '%d%% of the %s limit used. Resets in %s (at %s).'.format(
                highest, this._provider.title, remaining, resetAt);
        this._notify(title, body, highest >= 90);
    }

    _notify(title, body, critical) {
        const source = new MessageTray.Source(
            this._provider.title, 'utilities-system-monitor-symbolic');
        Main.messageTray.add(source);
        const notification = new MessageTray.Notification(source, title, body);
        notification.setTransient(false);
        if (critical)
            notification.setUrgency(MessageTray.Urgency.CRITICAL);
        source.showNotification(notification);
    }

    _loadState() {
        try {
            const [ok, bytes] = GLib.file_get_contents(this._statePath);
            if (ok) {
                const state = JSON.parse(new TextDecoder().decode(bytes));
                if (typeof state.notified === 'number' && typeof state.window === 'number')
                    return { window: state.window, notified: state.notified, seeded: true };
            }
        } catch (e) {
            // first run or corrupt state: start clean
        }
        return { window: 0, notified: 0, seeded: false };
    }

    _saveState() {
        try {
            GLib.mkdir_with_parents(STATE_DIR, 0o700);
            GLib.file_set_contents(this._statePath, JSON.stringify(this._notifyState));
        } catch (e) {
            logError(e, 'ai-usage: failed to save state');
        }
    }

    destroy() {
        this._destroyed = true;
        if (this._tickId) {
            GLib.source_remove(this._tickId);
            this._tickId = null;
        }
        super.destroy();
    }
});
