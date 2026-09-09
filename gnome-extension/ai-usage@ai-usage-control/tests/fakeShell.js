/* Loads aiusagelib/indicator.js outside GNOME Shell.
 *
 * The indicator cannot simply be imported here: its first line asks for St,
 * whose typelib ships inside the shell process and nowhere else. But the
 * file reaches every one of its dependencies through `imports`, so
 * evaluating it inside a function whose parameter is called `imports`
 * shadows the global importer and lets stand-ins be handed in instead.
 *
 * That is what makes the version-dependent half testable: _notify() is the
 * one place where GNOME 42 and GNOME 46+ need different calls, and the
 * branch it takes is decided by what MessageTray.Source looks like — which
 * is exactly what a stand-in gets to control. Both branches are therefore
 * exercised on any machine, including one that has only ever run GNOME 50.
 */
'use strict';

const { GLib, Gio, GObject } = imports.gi;

/* St widgets are only ever constructed, mutated and read back, so plain
 * objects carrying the same property names are enough. */
function fakeActor(props = {}) {
    return Object.assign({
        children: [],
        opacity: 255,
        add_child(child) {
            this.children.push(child);
        },
        set_position() {},
        set_size(w, h) {
            this.width = w;
            this.height = h;
        },
        destroy() {},
    }, props);
}

const St = {
    BoxLayout: function (props) {
        return fakeActor(props);
    },
    Label: function (props) {
        return fakeActor(Object.assign({ text: '' }, props));
    },
    Widget: function (props) {
        return fakeActor(props);
    },
};

const Clutter = { ActorAlign: { CENTER: 'center' } };

/* PanelMenu.Button must be a real GObject class: the indicator is passed to
 * GObject.registerClass, which rejects a base that is not one. */
const FakeButton = GObject.registerClass(
class FakeButton extends GObject.Object {
    _init(menuAlignment, nameText) {
        super._init({});
        this.menuAlignment = menuAlignment;
        this.nameText = nameText;
        this.children = [];
        this.menu = {
            items: [],
            addMenuItem(item) {
                this.items.push(item);
            },
        };
    }

    add_child(child) {
        this.children.push(child);
    }

    destroy() {
        this.destroyed = true;
    }
});

function fakeMenuItem(text) {
    return {
        label: { text: text || '' },
        connect() {},
        destroy() {},
    };
}

const PopupMenu = {
    PopupMenuItem: function (text) {
        return fakeMenuItem(text);
    },
    PopupMenuSection: function () {
        return {
            items: [],
            addMenuItem(item) {
                this.items.push(item);
            },
        };
    },
    PopupSeparatorMenuItem: function () {
        return fakeMenuItem('');
    },
};

/* `generation` picks which MessageTray API the indicator will find:
 * 'legacy' is GNOME 42-44, 'modern' is GNOME 46+. Every call the indicator
 * makes is appended to `log` so a test can assert on the whole sequence. */
function makeMessageTray(generation, log) {
    class Notification {
        constructor(a, b, c) {
            if (generation === 'modern') {
                Object.assign(this, a);
                log.push(['notification', {
                    title: a.title,
                    body: a.body,
                    isTransient: a.isTransient,
                    urgency: a.urgency,
                    hasSource: !!a.source,
                }]);
            } else {
                this.source = a;
                this.title = b;
                this.body = c;
                log.push(['notification', { title: b, body: c, hasSource: !!a }]);
            }
        }

        setTransient(value) {
            log.push(['setTransient', value]);
        }

        setUrgency(value) {
            log.push(['setUrgency', value]);
        }
    }

    class Source {
        constructor(a, b) {
            if (generation === 'modern')
                log.push(['source', { title: a.title, iconName: a.iconName }]);
            else
                log.push(['source', { title: a, iconName: b }]);
        }
    }

    if (generation === 'modern') {
        Source.prototype.addNotification = function (n) {
            log.push(['addNotification', n.title]);
        };
    } else {
        Source.prototype.showNotification = function (n) {
            log.push(['showNotification', n.title]);
        };
    }

    return { Source, Notification };
}

/* Build the shell stand-ins plus the call log they write to.
 *
 * MessageTray is a holder whose Source and Notification are swapped by
 * use(), rather than a fresh object per generation, because a GType name is
 * registered once per process: loading the indicator twice would throw
 * "Type name Gjs_UsageIndicator is already registered". Inside a real shell
 * the module is loaded once and getUsageIndicatorClass() caches, so one
 * registration is also what actually happens in production. _notify() reads
 * MessageTray.Source when it is called, so swapping is enough. */
var makeShell = function () {
    const log = [];
    const MessageTray = { Source: null, Notification: null, Urgency: { NORMAL: 0, CRITICAL: 3 } };
    const Main = {
        messageTray: {
            add(source) {
                log.push(['trayAdd', !!source]);
            },
        },
        panel: {
            addToStatusArea(name) {
                log.push(['addToStatusArea', name]);
            },
        },
    };
    return {
        shell: { Main, PanelMenu: { Button: FakeButton }, PopupMenu, MessageTray },
        log,
        /* Point the tray at one generation's API and clear the log. */
        use(generation) {
            const tray = makeMessageTray(generation, log);
            MessageTray.Source = tray.Source;
            MessageTray.Notification = tray.Notification;
            log.length = 0;
        },
    };
};

/* Evaluate indicator.js with `imports` bound to the stand-ins and hand back
 * the indicator class. Call this once per process: see makeShell() above. */
var loadIndicatorFactory = function (extensionDir, shell) {
    const path = GLib.build_filenamev([extensionDir, 'aiusagelib', 'indicator.js']);
    const [ok, bytes] = GLib.file_get_contents(path);
    if (!ok)
        throw new Error('cannot read %s'.format(path));

    const fakeImports = {
        gi: { St, GLib, Gio, GObject, Clutter },
        aiusagelib: {
            format: imports.aiusagelib.format,
            errors: imports.aiusagelib.errors,
        },
    };

    const source = new TextDecoder().decode(bytes);
    const factory = new Function(
        'imports', '%s\nreturn getUsageIndicatorClass;'.format(source));
    return factory(fakeImports)(shell);
};
