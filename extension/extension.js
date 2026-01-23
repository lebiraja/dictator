/**
 * Dictator GNOME Shell Extension
 *
 * System-wide voice dictation using Whisper.
 * Press Ctrl+Shift+Space to toggle recording.
 */

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import * as MessageTray from 'resource:///org/gnome/shell/ui/messageTray.js';

import { Extension, gettext as _ } from 'resource:///org/gnome/shell/extensions/extension.js';


// D-Bus interface for org.lebi.Dictator
const DictatorIface = `
<node>
  <interface name="org.lebi.Dictator">
    <method name="StartRecording">
      <arg type="b" direction="out" name="success"/>
    </method>
    <method name="StopRecording">
      <arg type="s" direction="out" name="transcription"/>
    </method>
    <method name="Cancel">
      <arg type="b" direction="out" name="success"/>
    </method>
    <method name="Toggle">
      <arg type="s" direction="out" name="new_state"/>
    </method>
    <method name="GetState">
      <arg type="s" direction="out" name="state"/>
    </method>
    <signal name="StateChanged">
      <arg type="s" name="state"/>
    </signal>
    <signal name="TranscriptionReady">
      <arg type="s" name="text"/>
    </signal>
    <signal name="Error">
      <arg type="s" name="message"/>
    </signal>
    <property name="State" type="s" access="read"/>
  </interface>
</node>
`;

const DictatorProxy = Gio.DBusProxy.makeProxyWrapper(DictatorIface);


/**
 * Panel indicator button for Dictator.
 */
const DictatorIndicator = GObject.registerClass(
class DictatorIndicator extends PanelMenu.Button {
    _init(extension) {
        super._init(0.0, 'Dictator');

        this._extension = extension;
        this._state = 'idle';
        this._proxy = null;
        this._signalIds = [];

        // Create icon
        this._icon = new St.Icon({
            icon_name: 'audio-input-microphone-symbolic',
            style_class: 'system-status-icon dictator-icon-idle',
        });
        this.add_child(this._icon);

        // Create menu
        this._buildMenu();

        // Connect to D-Bus service
        this._connectToService();

        // Register keyboard shortcut
        this._registerShortcut();
    }

    _buildMenu() {
        // Status item
        this._statusItem = new PopupMenu.PopupMenuItem(_('Idle'), { reactive: false });
        this.menu.addMenuItem(this._statusItem);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // Toggle button
        this._toggleItem = new PopupMenu.PopupMenuItem(_('Start Dictation'));
        this._toggleItem.connect('activate', () => this._toggle());
        this.menu.addMenuItem(this._toggleItem);

        // Cancel button (only visible when recording/transcribing)
        this._cancelItem = new PopupMenu.PopupMenuItem(_('Cancel'));
        this._cancelItem.connect('activate', () => this._cancel());
        this._cancelItem.visible = false;
        this.menu.addMenuItem(this._cancelItem);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // Settings/info section
        this._modelStatusItem = new PopupMenu.PopupMenuItem(_('Ready'), { reactive: false });
        this.menu.addMenuItem(this._modelStatusItem);
    }

    async _connectToService() {
        try {
            this._proxy = new DictatorProxy(
                Gio.DBus.session,
                'org.lebi.Dictator',
                '/org/lebi/Dictator'
            );

            // Connect to signals
            this._signalIds.push(
                this._proxy.connectSignal('StateChanged', (proxy, sender, [state]) => {
                    this._onStateChanged(state);
                })
            );

            this._signalIds.push(
                this._proxy.connectSignal('TranscriptionReady', (proxy, sender, [text]) => {
                    this._onTranscriptionReady(text);
                })
            );

            this._signalIds.push(
                this._proxy.connectSignal('Error', (proxy, sender, [message]) => {
                    this._onError(message);
                })
            );

            // Get initial state
            const [state] = await this._proxy.GetStateAsync();
            this._onStateChanged(state);

        } catch (e) {
            log(`Dictator: Failed to connect to service: ${e.message}`);
            this._statusItem.label.text = _('Service unavailable');
            this._modelStatusItem.label.text = _('Start service first');
        }
    }

    _registerShortcut() {
        const settings = this._extension.getSettings();

        Main.wm.addKeybinding(
            'shortcut',
            settings,
            Meta.KeyBindingFlags.NONE,
            Shell.ActionMode.ALL,
            () => this._toggle()
        );
    }

    _unregisterShortcut() {
        Main.wm.removeKeybinding('shortcut');
    }

    async _toggle() {
        if (!this._proxy) {
            this._showNotification(_('Dictator'), _('Service not available'));
            return;
        }

        try {
            await this._proxy.ToggleAsync();
        } catch (e) {
            log(`Dictator: Toggle failed: ${e.message}`);
            this._showNotification(_('Dictator Error'), e.message);
        }
    }

    async _cancel() {
        if (!this._proxy)
            return;

        try {
            await this._proxy.CancelAsync();
        } catch (e) {
            log(`Dictator: Cancel failed: ${e.message}`);
        }
    }

    _onStateChanged(state) {
        this._state = state;

        // Update icon style
        this._icon.style_class = `system-status-icon dictator-icon-${state}`;

        // Update status text
        const stateLabels = {
            'idle': _('Idle'),
            'recording': _('Recording...'),
            'transcribing': _('Transcribing...'),
            'typing': _('Typing...'),
            'downloading': _('Downloading model...'),
            'error': _('Error'),
        };
        this._statusItem.label.text = stateLabels[state] || state;

        // Update toggle button text
        if (state === 'idle' || state === 'error') {
            this._toggleItem.label.text = _('Start Dictation');
            this._cancelItem.visible = false;
        } else if (state === 'recording') {
            this._toggleItem.label.text = _('Stop & Transcribe');
            this._cancelItem.visible = true;
        } else {
            this._toggleItem.label.text = _('Working...');
            this._cancelItem.visible = true;
        }

        // Show recording overlay
        if (state === 'recording') {
            this._showOverlay(_('Listening...'));
        } else if (state === 'transcribing') {
            this._showOverlay(_('Transcribing...'));
        } else if (state === 'typing') {
            this._showOverlay(_('Typing...'));
        } else {
            this._hideOverlay();
        }
    }

    _onTranscriptionReady(text) {
        if (!text || text.trim() === '') {
            this._showNotification(_('Dictator'), _('No speech detected'));
            return;
        }

        // Show notification with preview
        const preview = text.length > 50 ? text.substring(0, 50) + '...' : text;
        this._showNotification(
            _('Dictation Complete'),
            preview
        );
    }

    _onError(message) {
        this._showNotification(_('Dictator Error'), message);
    }

    _showNotification(title, body) {
        const source = new MessageTray.Source({
            title: 'Dictator',
            iconName: 'audio-input-microphone-symbolic',
        });
        Main.messageTray.add(source);

        const notification = new MessageTray.Notification({
            source,
            title,
            body,
            isTransient: true,
        });

        source.addNotification(notification);
    }

    _showOverlay(text) {
        if (!this._overlay) {
            this._overlay = new St.BoxLayout({
                style_class: 'dictator-overlay',
                vertical: true,
                x_align: Clutter.ActorAlign.CENTER,
                y_align: Clutter.ActorAlign.CENTER,
            });

            this._overlayIcon = new St.Icon({
                icon_name: 'audio-input-microphone-symbolic',
                icon_size: 48,
                style_class: 'dictator-overlay-icon',
            });
            this._overlay.add_child(this._overlayIcon);

            this._overlayLabel = new St.Label({
                style_class: 'dictator-overlay-label',
            });
            this._overlay.add_child(this._overlayLabel);

            Main.layoutManager.addTopChrome(this._overlay);
        }

        this._overlayLabel.text = text;

        // Position at top center
        const monitor = Main.layoutManager.primaryMonitor;
        this._overlay.set_position(
            monitor.x + (monitor.width - this._overlay.width) / 2,
            monitor.y + 100
        );

        this._overlay.show();
    }

    _hideOverlay() {
        if (this._overlay) {
            this._overlay.hide();
        }
    }

    destroy() {
        // Disconnect signals
        if (this._proxy) {
            for (const id of this._signalIds) {
                this._proxy.disconnectSignal(id);
            }
        }

        // Remove shortcut
        this._unregisterShortcut();

        // Remove overlay
        if (this._overlay) {
            Main.layoutManager.removeChrome(this._overlay);
            this._overlay.destroy();
            this._overlay = null;
        }

        super.destroy();
    }
});


/**
 * Main extension class.
 */
export default class DictatorExtension extends Extension {
    enable() {
        this._indicator = new DictatorIndicator(this);
        Main.panel.addToStatusArea('dictator', this._indicator);
    }

    disable() {
        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
        }
    }
}
