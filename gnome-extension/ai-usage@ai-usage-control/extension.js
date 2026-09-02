/* AI Usage — top-panel indicators for coding-agent usage limits.
 *
 * One progress bar per provider (Claude Code, Codex CLI): the used share of
 * the shortest limit window, blue < 75%, yellow 75-90%, red >= 90%, with a
 * countdown to the reset and notifications at 20/40/60/80/90/100%.
 *
 * There is no settings UI on purpose. A provider's bar appears when that
 * CLI is installed and logged in and disappears when it is not, rechecked
 * on every poll — so logging in to either tool brings its bar up within a
 * minute, with nothing to configure.
 *
 * ---------------------------------------------------------------------
 * This is the GNOME 42 entry point. GNOME 45 rewrote the shell's JS as ES
 * modules and now loads extension.js with `await import()`, expecting a
 * default-exported class; before that it read the file with the legacy
 * importer and called init(). A file cannot satisfy both — `export` is a
 * syntax error outside a module — so the modern entry point lives in
 * extension-esm.js and deploy/gnome-extension.sh installs whichever one
 * matches the running shell under this name.
 *
 * Only the entry points are split. Everything under aiusagelib/ is loaded
 * through the legacy importer by both of them, because an ES module can
 * still reach the `imports` object while a legacy script can never parse
 * an ES module — so legacy-style shared code is the half that both
 * generations can read.
 */
'use strict';

const Main = imports.ui.main;
const PanelMenu = imports.ui.panelMenu;
const PopupMenu = imports.ui.popupMenu;
const MessageTray = imports.ui.messageTray;
const ExtensionUtils = imports.misc.extensionUtils;
const Me = ExtensionUtils.getCurrentExtension();

/* imports.* is a process-wide namespace shared by every extension, and the
 * first loader of a given path wins for all of them — a directory named
 * `lib` would hand our modules to anyone else importing `imports.lib.*`,
 * and theirs to us. Hence the unlikely-to-collide name, and putting the
 * path back straight away. */
imports.searchPath.unshift(Me.path);
const Core = imports.aiusagelib.core;
imports.searchPath.shift();

const SHELL = { Main, PanelMenu, PopupMenu, MessageTray };

class Extension {
    enable() {
        this._controller = new Core.Controller(SHELL, Me.path);
        this._controller.enable();
    }

    disable() {
        this._controller.disable();
        this._controller = null;
    }
}

function init() {
    return new Extension();
}
