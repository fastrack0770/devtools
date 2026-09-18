/* Shared panel indicator: one progress bar for one usage provider.
 *
 * Everything provider-independent lives here — the bar, the colours, the
 * countdown, the threshold notifications and their persisted state, the
 * error handling and the staleness dimming. A provider (aiusagelib/claude.js,
 * aiusagelib/codex.js) is now only an id and a title: the controller fetches
 * one shared document and hands this class its own entry, which
 * aiusagelib/model.js turns into the render model below:
 *
 *   { percent, resetsAt, stale, suffix, rows, note }
 *
 * `percent` null means "no trustworthy number" and renders as an em dash;
 * `resetsAt` is Unix seconds; `stale` dims the whole indicator.
 *
 * Threshold notifications stay here and only here. The Godot Shell renders the
 * same numbers and deliberately raises none, so a crossing is announced once
 * (design.md D8).
 */
'use strict';

/* gi is reachable the same way under both shell generations, and so are
 * these two siblings — the entry point puts the extension directory on
 * imports.searchPath before pulling this file in. The shell's own UI
 * modules are not: GNOME 45 turned them into ES modules, which the legacy
 * importer cannot read, so they arrive through getUsageIndicatorClass(). */
const { St, GLib, GObject, Clutter } = imports.gi;
const Format = imports.aiusagelib.format;
const Errors = imports.aiusagelib.errors;
const Model = imports.aiusagelib.model;

const TICK_SECONDS = 20; // countdown label refresh between polls
const TRACK_WIDTH = 70;
const TRACK_HEIGHT = 8;
const THRESHOLDS = [20, 40, 60, 80, 90, 100];
const WINDOW_TOLERANCE_SECONDS = 300;
const STALE_OPACITY = 110;
const STATE_DIR = GLib.build_filenamev([GLib.get_user_cache_dir(), 'ai-usage-control']);

function fillClassFor(percent) {
    if (percent >= 90)
        return 'cu-fill cu-fill-red';
    if (percent >= 75)
        return 'cu-fill cu-fill-yellow';
    return 'cu-fill cu-fill-blue';
}

/* Registering a GType twice throws, so the class is built on first use and
 * cached: enable/disable cycles reuse it. `shell` carries the four UI
 * modules the entry point imported in whichever way its generation allows —
 * { Main, PanelMenu, PopupMenu, MessageTray }. */
let IndicatorClass = null;

var getUsageIndicatorClass = function (shell) {
    if (IndicatorClass)
        return IndicatorClass;

    const { Main, PanelMenu, PopupMenu, MessageTray } = shell;

    IndicatorClass = GObject.registerClass(
    class UsageIndicator extends PanelMenu.Button {
        _init(provider, onForceRefresh) {
            super._init(0.5, '%s Usage'.format(provider.title));
            this._provider = provider;
            this._onForceRefresh = onForceRefresh || (() => {});
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
            refreshItem.connect('activate', () => this._onForceRefresh());
            this.menu.addMenuItem(refreshItem);

            this._notifyState = this._loadState();
            this._model = null;
            this._destroyed = false;

            // keep the countdown fresh between polls
            this._tickId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, TICK_SECONDS, () => {
                if (this._model)
                    this._render();
                return GLib.SOURCE_CONTINUE;
            });
        }

        /* One provider's entry from the shared document (design.md D2). A failed
         * or rate-limited provider still arrives here — the runtime keeps its
         * last good windows and marks them stale — so a blip never blanks a
         * working panel. */
        update(entry) {
            if (this._destroyed)
                return;

            const model = Model.render(entry);
            if (!model) {
                this.showError(entry.error || 'parse', entry.next_retry_at);
                return;
            }

            this._model = model;
            this._render();

            const stamp = GLib.DateTime.new_now_local().format('%H:%M:%S');
            if (entry.state === 'stale' && entry.next_retry_at) {
                this._updatedItem.label.text = 'Stale — %s, retry at %s'.format(
                    Errors.errorMessage(entry.error), Format.formatReset(entry.next_retry_at));
            } else if (model.note) {
                this._updatedItem.label.text = 'Updated: %s (%s)'.format(stamp, model.note);
            } else {
                this._updatedItem.label.text = 'Updated: %s'.format(stamp);
            }

            /* Only a live reading may raise a notification: a stale snapshot
             * would re-announce a threshold the user was already told about. */
            if (model.percent !== null && !model.stale)
                this._maybeNotify(model.percent, model.resetsAt);
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

        /* The runtime could not be run or did not answer. Pausing the polling
         * is the runtime's job, so all this does is say so. */
        showError(reason, retryAt = 0) {
            const message = Errors.errorMessage(reason);

            /* A rate limit or network blip should not blank a working panel:
             * keep the last known numbers and flag them as stale instead. */
            if (this._model) {
                this._model.stale = true;
                this._render();
                /* This line is the one a user actually reads, so it gets the message —
                 * it used to interpolate the raw `reason`, which is why a rate limit
                 * still surfaced as `usage_http_429` on every panel that already had
                 * numbers, i.e. almost always. When polling is paused, when it resumes
                 * is the useful half; otherwise, when the reading stopped being live. */
                this._updatedItem.label.text = retryAt
                    ? 'Stale — %s, retry at %s'.format(message, Format.formatReset(Math.round(retryAt)))
                    : 'Stale — %s (at %s)'.format(
                        message, GLib.DateTime.new_now_local().format('%H:%M:%S'));
                return;
            }

            this._fill.set_size(TRACK_WIDTH, TRACK_HEIGHT);
            this._fill.style_class = 'cu-fill cu-fill-gray';
            this._box.opacity = 255;
            this._infoLabel.text = '—';
            this._setRows([message]);
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

        /* GNOME 46 rebuilt this corner of the API: the positional Source and
         * Notification constructors became parameter objects, setTransient()
         * and setUrgency() became properties, and showNotification() became
         * addNotification(). Both shapes are ordinary method calls with no
         * syntax the other generation rejects, so one runtime test keeps this
         * file shared instead of forcing a third variant. The test looks for
         * the method that was *removed*: 42 has showNotification and 50 does
         * not, whereas guessing from a method 46 added would rest on an
         * assumption about 42 that cannot be checked from a GNOME 50 box. */
        _notify(title, body, critical) {
            const legacyTray =
                typeof MessageTray.Source.prototype.showNotification === 'function';
            const iconName = 'utilities-system-monitor-symbolic';

            if (legacyTray) {
                const source = new MessageTray.Source(this._provider.title, iconName);
                Main.messageTray.add(source);
                const notification = new MessageTray.Notification(source, title, body);
                notification.setTransient(false);
                if (critical)
                    notification.setUrgency(MessageTray.Urgency.CRITICAL);
                source.showNotification(notification);
                return;
            }

            const source = new MessageTray.Source({ title: this._provider.title, iconName });
            Main.messageTray.add(source);
            source.addNotification(new MessageTray.Notification({
                source,
                title,
                body,
                isTransient: false,
                urgency: critical
                    ? MessageTray.Urgency.CRITICAL
                    : MessageTray.Urgency.NORMAL,
            }));
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

    return IndicatorClass;
};
