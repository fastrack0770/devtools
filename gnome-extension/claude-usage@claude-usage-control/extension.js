/* Claude Usage — GNOME 42 top-panel indicator for Claude Code session usage.
 *
 * Shows a progress bar (blue < 75%, yellow 75-90%, red >= 90%) with a
 * countdown until the limit resets and the used share of the model's
 * weekly quota, and sends notifications when usage crosses
 * 20/40/60/80/90/100%. Data comes from usage-helper.py (same OAuth usage
 * endpoint the claude CLI uses for /usage).
 */
'use strict';

const { St, GLib, Gio, GObject, Clutter } = imports.gi;
const Main = imports.ui.main;
const PanelMenu = imports.ui.panelMenu;
const PopupMenu = imports.ui.popupMenu;
const MessageTray = imports.ui.messageTray;
const ExtensionUtils = imports.misc.extensionUtils;
const Me = ExtensionUtils.getCurrentExtension();

const POLL_SECONDS = 60;
const TICK_SECONDS = 20; // countdown label refresh between polls
const BACKOFF_SECONDS = 300; // pause polling after the endpoint rate-limits us
const TRACK_WIDTH = 70;
const TRACK_HEIGHT = 8;
const THRESHOLDS = [20, 40, 60, 80, 90, 100];
const WINDOW_TOLERANCE_SECONDS = 300;
const STATE_DIR = GLib.build_filenamev([GLib.get_user_cache_dir(), 'claude-usage-control']);
const STATE_PATH = GLib.build_filenamev([STATE_DIR, 'state.json']);

function fillClassFor(percent) {
    if (percent >= 90)
        return 'cu-fill cu-fill-red';
    if (percent >= 75)
        return 'cu-fill cu-fill-yellow';
    return 'cu-fill cu-fill-blue';
}

/* Unix seconds of a resets_at, or 0 if it is missing/unparseable. */
function windowStamp(isoString) {
    if (!isoString)
        return 0;
    const dt = GLib.DateTime.new_from_iso8601(isoString, null);
    return dt ? dt.to_unix() : 0;
}

function formatReset(isoString) {
    const dt = GLib.DateTime.new_from_iso8601(isoString, null);
    if (!dt)
        return '?';
    const local = dt.to_local();
    const now = GLib.DateTime.new_now_local();
    if (local.difference(now) > 24 * 3600 * 1000000)
        return local.format('%d.%m %H:%M');
    return local.format('%H:%M');
}

/* Time left until the reset as "H:MM" — "5:00", "4:22", "0:04". */
function formatRemaining(isoString) {
    const dt = GLib.DateTime.new_from_iso8601(isoString, null);
    if (!dt)
        return '?';
    let mins = Math.ceil((dt.to_unix() - GLib.get_real_time() / 1000000) / 60);
    if (mins < 0)
        mins = 0;
    return '%d:%02d'.format(Math.floor(mins / 60), mins % 60);
}

const ClaudeUsageIndicator = GObject.registerClass(
class ClaudeUsageIndicator extends PanelMenu.Button {
    _init() {
        super._init(0.5, 'Claude Usage');

        this._box = new St.BoxLayout({ style_class: 'cu-box', y_align: Clutter.ActorAlign.CENTER });
        this._titleLabel = new St.Label({
            text: 'Usage',
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

        this._sessionItem = new PopupMenu.PopupMenuItem('Session (5 h): …', { reactive: false });
        this._weekItem = new PopupMenu.PopupMenuItem('Week: …', { reactive: false });
        this._modelItem = new PopupMenu.PopupMenuItem('Model: …', { reactive: false });
        this._updatedItem = new PopupMenu.PopupMenuItem('Updated: —', { reactive: false });
        this.menu.addMenuItem(this._sessionItem);
        this.menu.addMenuItem(this._weekItem);
        this.menu.addMenuItem(this._modelItem);
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this.menu.addMenuItem(this._updatedItem);
        const refreshItem = new PopupMenu.PopupMenuItem('Refresh now');
        refreshItem.connect('activate', () => this.refresh(true));
        this.menu.addMenuItem(refreshItem);

        this._notifyState = this._loadState();
        this._data = null;
        this._backoffUntil = 0;
        this._destroyed = false;

        // keep the countdown fresh between polls
        this._tickId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, TICK_SECONDS, () => {
            if (this._data)
                this._renderData();
            return GLib.SOURCE_CONTINUE;
        });
    }

    /* `force` comes from the menu item and ignores the rate-limit backoff. */
    refresh(force = false) {
        const now = GLib.get_real_time() / 1000000;
        if (!force && now < this._backoffUntil)
            return;

        let proc;
        try {
            proc = Gio.Subprocess.new(
                ['python3', GLib.build_filenamev([Me.path, 'usage-helper.py'])],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE);
        } catch (e) {
            this._showError('helper');
            return;
        }
        proc.communicate_utf8_async(null, null, (p, res) => {
            if (this._destroyed)
                return;
            try {
                const [, stdout] = p.communicate_utf8_finish(res);
                const data = JSON.parse(stdout);
                if (data.ok) {
                    this._backoffUntil = 0;
                    this._data = data;
                    this._renderData();
                    this._updatedItem.label.text =
                        'Updated: %s'.format(GLib.DateTime.new_now_local().format('%H:%M:%S'));
                    this._maybeNotify(Math.max(0, Math.min(100, data.percent)), data.resets_at);
                } else {
                    this._showError(data.error);
                }
            } catch (e) {
                this._showError('parse');
            }
        });
    }

    _renderData() {
        const data = this._data;
        const percent = Math.max(0, Math.min(100, data.percent));
        const remaining = data.resets_at ? formatRemaining(data.resets_at) : '?';

        let width = Math.round(TRACK_WIDTH * percent / 100);
        if (percent > 0 && width < 2)
            width = 2;
        this._fill.set_size(width, TRACK_HEIGHT);
        this._fill.style_class = fillClassFor(percent);

        // every percentage below is the *used* share of a limit, never the remainder
        let info = '%d%% · %s'.format(Math.round(percent), remaining);
        if (data.model_percent !== undefined) {
            info += ' · %s %d%%'.format(
                data.model_name || 'model', Math.round(data.model_percent));
        }
        this._infoLabel.text = info;

        this._sessionItem.label.text = 'Session (5 h): %d%% used, %s left (resets at %s)'.format(
            Math.round(percent), remaining,
            data.resets_at ? formatReset(data.resets_at) : '?');
        if (data.seven_day_percent !== undefined) {
            this._weekItem.label.text = 'Week: %d%% used, resets %s'.format(
                Math.round(data.seven_day_percent),
                data.seven_day_resets_at ? formatReset(data.seven_day_resets_at) : '?');
        }
        if (data.model_percent !== undefined) {
            this._modelItem.label.text = '%s: %d%% used, resets %s'.format(
                data.model_name || 'model',
                Math.round(data.model_percent),
                data.model_resets_at ? formatReset(data.model_resets_at) : '?');
            this._modelItem.visible = true;
        } else {
            this._modelItem.visible = false;
        }
    }

    _showError(reason) {
        if (reason === 'usage_http_429') {
            this._backoffUntil =
                GLib.get_real_time() / 1000000 + BACKOFF_SECONDS;
        }

        /* A rate limit or network blip should not blank a working panel:
         * keep the last known numbers and flag them as stale instead. */
        if (this._data) {
            this._renderData();
            this._updatedItem.label.text = 'Stale — error at %s (%s)'.format(
                GLib.DateTime.new_now_local().format('%H:%M:%S'), reason);
            return;
        }

        this._fill.set_size(TRACK_WIDTH, TRACK_HEIGHT);
        this._fill.style_class = 'cu-fill cu-fill-gray';
        this._infoLabel.text = '—';
        this._sessionItem.label.text = 'No data (%s)'.format(reason);
        this._updatedItem.label.text =
            'Error at %s'.format(GLib.DateTime.new_now_local().format('%H:%M:%S'));
    }

    _maybeNotify(percent, resetsAtIso) {
        /* The server recomputes resets_at on every poll, so it jitters by a
         * fraction of a second — and when it happens to sit next to a minute
         * boundary it flips back and forth across it. Anchoring the window on
         * an exact (or minute-truncated) timestamp made that flip look like a
         * new window, which reset `notified` and re-sent every threshold.
         * Only a jump of minutes is a real rollover; a response with no
         * resets_at at all leaves the current window alone. */
        const stamp = windowStamp(resetsAtIso);
        if (stamp && Math.abs(stamp - this._notifyState.window) > WINDOW_TOLERANCE_SECONDS) {
            // new 5-hour window: thresholds fire again
            this._notifyState = { window: stamp, notified: 0 };
            this._saveState();
        }

        let highest = 0;
        for (const t of THRESHOLDS) {
            if (percent >= t)
                highest = t;
        }
        if (highest <= this._notifyState.notified)
            return;

        this._notifyState.notified = highest;
        this._saveState();

        const remaining = resetsAtIso ? formatRemaining(resetsAtIso) : '?';
        const resetAt = resetsAtIso ? formatReset(resetsAtIso) : '?';
        const title = 'Claude Usage: %d%%'.format(highest);
        const body = highest >= 100
            ? 'Session limit reached. Resets in %s (at %s).'.format(remaining, resetAt)
            : '%d%% of the session limit used. Resets in %s (at %s).'.format(
                highest, remaining, resetAt);
        this._notify(title, body, highest >= 90);
    }

    _notify(title, body, critical) {
        const source = new MessageTray.Source('Claude Usage', 'utilities-system-monitor-symbolic');
        Main.messageTray.add(source);
        const notification = new MessageTray.Notification(source, title, body);
        notification.setTransient(false);
        if (critical)
            notification.setUrgency(MessageTray.Urgency.CRITICAL);
        source.showNotification(notification);
    }

    _loadState() {
        try {
            const [ok, bytes] = GLib.file_get_contents(STATE_PATH);
            if (ok) {
                const state = JSON.parse(new TextDecoder().decode(bytes));
                if (typeof state.notified === 'number') {
                    if (typeof state.window === 'number')
                        return state;
                    // v1 stored the window as a minute-count string
                    if (/^\d+$/.test(state.window))
                        return { window: Number(state.window) * 60, notified: state.notified };
                }
            }
        } catch (e) {
            // first run or corrupt state: start clean
        }
        return { window: 0, notified: 0 };
    }

    _saveState() {
        try {
            GLib.mkdir_with_parents(STATE_DIR, 0o700);
            GLib.file_set_contents(STATE_PATH, JSON.stringify(this._notifyState));
        } catch (e) {
            logError(e, 'claude-usage: failed to save state');
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

class Extension {
    enable() {
        this._indicator = new ClaudeUsageIndicator();
        Main.panel.addToStatusArea('claude-usage', this._indicator, 1, 'right');
        this._indicator.refresh();
        this._timeoutId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, POLL_SECONDS, () => {
            this._indicator.refresh();
            return GLib.SOURCE_CONTINUE;
        });
    }

    disable() {
        if (this._timeoutId) {
            GLib.source_remove(this._timeoutId);
            this._timeoutId = null;
        }
        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
        }
    }
}

function init() {
    return new Extension();
}
