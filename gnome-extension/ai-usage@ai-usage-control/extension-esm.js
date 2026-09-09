/* AI Usage — the GNOME 45+ entry point: usage bars for Claude Code and Codex
 * in the top panel. The extension is described in the package README, and
 * the source file extension-esm.js is one of two entry points — the GNOME
 * 42-44 one lives in the package as extension.js and explains the split.
 * deploy/gnome-extension.sh installs whichever matches the running shell
 * under the name extension.js, so this comment may be reading from a file
 * that no longer carries its original name.
 */

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import * as MessageTray from 'resource:///org/gnome/shell/ui/messageTray.js';
import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';

export default class AiUsageExtension extends Extension {
    enable() {
        /* An ES module still sees the legacy `imports` object, which is the
         * only reason aiusagelib/ can be shared verbatim with the GNOME 42
         * entry point instead of duplicated. this.path is only available on
         * the instance, so the load happens here rather than at module
         * scope; the importer caches, so a re-enable costs nothing. */
        imports.searchPath.unshift(this.path);
        const Core = imports.aiusagelib.core;
        imports.searchPath.shift();

        this._controller = new Core.Controller(
            { Main, PanelMenu, PopupMenu, MessageTray }, this.path);
        this._controller.enable();
    }

    disable() {
        this._controller.disable();
        this._controller = null;
    }
}
