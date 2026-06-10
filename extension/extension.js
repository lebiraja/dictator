/**
 * Dictator GNOME Shell Extension
 *
 * System-wide voice dictation using a local Whisper model.
 * Press the shortcut (default Shift+Ctrl+Space) to toggle recording.
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
import * as Animation from 'resource:///org/gnome/shell/ui/animation.js';
import * as Config from 'resource:///org/gnome/shell/misc/config.js';

import {Extension, gettext as _} from 'resource:///org/gnome/shell/extensions/extension.js';

const SHELL_MAJOR = parseInt(Config.PACKAGE_VERSION.split('.')[0], 10);

const BUS_NAME = 'org.lebi.Dictator';
const OBJECT_PATH = '/org/lebi/Dictator';

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
    <method name="Configure">
      <arg type="a{sv}" direction="in" name="options"/>
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
    <signal name="AudioLevel">
      <arg type="d" name="level"/>
    </signal>
    <property name="State" type="s" access="read"/>
  </interface>
</node>
`;

const DictatorProxy = Gio.DBusProxy.makeProxyWrapper(DictatorIface);

const STATE_LABELS = {
    'idle': _('Idle'),
    'starting': _('Starting…'),
    'recording': _('Listening…'),
    'transcribing': _('Transcribing…'),
    'typing': _('Typing…'),
    'loading': _('Loading model…'),
    'downloading': _('Downloading model…'),
    'error': _('Error'),
};

const LEVEL_BAR_COUNT = 12;


/**
 * Floating top-center pill showing recording/transcription progress.
 */
const DictatorOverlay = GObject.registerClass(
class DictatorOverlay extends St.BoxLayout {
    _init() {
        super._init({
            style_class: 'dictator-overlay',
            x_align: Clutter.ActorAlign.CENTER,
            y_align: Clutter.ActorAlign.CENTER,
            visible: false,
            opacity: 0,
        });

        this._dot = new St.Widget({
            style_class: 'dictator-dot',
            y_align: Clutter.ActorAlign.CENTER,
        });
        this.add_child(this._dot);

        this._icon = new St.Icon({
            icon_name: 'audio-input-microphone-symbolic',
            icon_size: 18,
            style_class: 'dictator-overlay-icon',
            y_align: Clutter.ActorAlign.CENTER,
        });
        this.add_child(this._icon);

        this._spinner = new Animation.Spinner(18);
        this._spinner.y_align = Clutter.ActorAlign.CENTER;
        this.add_child(this._spinner);

        this._bars = [];
        this._barsBox = new St.BoxLayout({
            style_class: 'dictator-bars',
            y_align: Clutter.ActorAlign.CENTER,
        });
        for (let i = 0; i < LEVEL_BAR_COUNT; i++) {
            const bar = new St.Widget({
                style_class: 'dictator-bar',
                y_align: Clutter.ActorAlign.CENTER,
                width: 3,
                height: 4,
            });
            this._bars.push(bar);
            this._barsBox.add_child(bar);
        }
        this.add_child(this._barsBox);

        this._label = new St.Label({
            style_class: 'dictator-overlay-label',
            y_align: Clutter.ActorAlign.CENTER,
        });
        this.add_child(this._label);

        this._timerLabel = new St.Label({
            style_class: 'dictator-overlay-timer',
            y_align: Clutter.ActorAlign.CENTER,
        });
        this.add_child(this._timerLabel);

        this._levels = new Array(LEVEL_BAR_COUNT).fill(0);
        this._timerId = 0;
        this._hideId = 0;
        this._pulseRunning = false;

        Main.layoutManager.addTopChrome(this);
        this.connect('notify::width', () => this._reposition());
        this._monitorsChangedId = Main.layoutManager.connect(
            'monitors-changed', () => this._reposition());
    }

    _reposition() {
        const monitor = Main.layoutManager.primaryMonitor;
        if (!monitor)
            return;
        this.set_position(
            monitor.x + Math.round((monitor.width - this.width) / 2),
            monitor.y + Math.round(monitor.height * 0.08)
        );
    }

    showState(state, message = '') {
        this._cancelAutoHide();

        const recording = state === 'recording' || state === 'starting';
        const busy = state === 'transcribing' || state === 'typing' ||
                     state === 'loading' || state === 'downloading';

        this._dot.visible = recording;
        this._icon.visible = !recording && !busy;
        this._icon.icon_name = state === 'error'
            ? 'dialog-warning-symbolic'
            : 'audio-input-microphone-symbolic';
        this._barsBox.visible = state === 'recording';
        this._timerLabel.visible = false;

        if (busy) {
            this._spinner.visible = true;
            this._spinner.play();
        } else {
            this._spinner.stop();
            this._spinner.visible = false;
        }

        this._label.text = message || STATE_LABELS[state] || state;

        if (state === 'recording')
            this._startTimer();
        else
            this._stopTimer();

        if (recording)
            this._startPulse();
        else
            this._stopPulse();

        this._fadeIn();
        this._reposition();

        if (state === 'error')
            this._autoHide(2500);
    }

    /** Brief "✓ <text>" toast, then fade out. */
    showResult(text) {
        this.showState('idle', text === ''
            ? _('No speech detected')
            : `✓  ${text.length > 60 ? `${text.substring(0, 60)}…` : text}`);
        this._autoHide(1600);
    }

    pushLevel(level) {
        this._levels.push(level);
        this._levels.shift();
        for (let i = 0; i < LEVEL_BAR_COUNT; i++) {
            const scaled = Math.min(1, this._levels[i] * 6);
            this._bars[i].height = Math.round(4 + scaled * 20);
        }
    }

    hideOverlay() {
        this._cancelAutoHide();
        this._stopTimer();
        this._stopPulse();
        this._spinner.stop();
        this.remove_all_transitions();
        this.ease({
            opacity: 0,
            duration: 150,
            mode: Clutter.AnimationMode.EASE_OUT_QUAD,
            onComplete: () => this.hide(),
        });
    }

    _fadeIn() {
        this.remove_all_transitions();
        this.show();
        this.ease({
            opacity: 255,
            duration: 150,
            mode: Clutter.AnimationMode.EASE_OUT_QUAD,
        });
    }

    _autoHide(ms) {
        this._cancelAutoHide();
        this._hideId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
            this._hideId = 0;
            this.hideOverlay();
            return GLib.SOURCE_REMOVE;
        });
    }

    _cancelAutoHide() {
        if (this._hideId) {
            GLib.source_remove(this._hideId);
            this._hideId = 0;
        }
    }

    _startTimer() {
        if (this._timerId)
            return;
        this._timerStart = GLib.get_monotonic_time();
        this._timerLabel.text = '0:00';
        this._timerLabel.visible = true;
        this._timerId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1000, () => {
            const secs = Math.floor((GLib.get_monotonic_time() - this._timerStart) / 1e6);
            this._timerLabel.text =
                `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}`;
            return GLib.SOURCE_CONTINUE;
        });
    }

    _stopTimer() {
        if (this._timerId) {
            GLib.source_remove(this._timerId);
            this._timerId = 0;
        }
        this._timerLabel.visible = false;
    }

    _startPulse() {
        if (this._pulseRunning)
            return;
        this._pulseRunning = true;
        const pulse = () => {
            if (!this._pulseRunning)
                return;
            this._dot.ease({
                opacity: 80,
                duration: 600,
                mode: Clutter.AnimationMode.EASE_IN_OUT_QUAD,
                onComplete: () => {
                    this._dot.ease({
                        opacity: 255,
                        duration: 600,
                        mode: Clutter.AnimationMode.EASE_IN_OUT_QUAD,
                        onComplete: pulse,
                    });
                },
            });
        };
        pulse();
    }

    _stopPulse() {
        this._pulseRunning = false;
        this._dot.remove_all_transitions();
        this._dot.opacity = 255;
    }

    destroy() {
        if (this._monitorsChangedId) {
            Main.layoutManager.disconnect(this._monitorsChangedId);
            this._monitorsChangedId = 0;
        }
        this._cancelAutoHide();
        this._stopTimer();
        this._stopPulse();
        super.destroy();
    }
});


/**
 * Panel indicator button for Dictator.
 */
const DictatorIndicator = GObject.registerClass(
class DictatorIndicator extends PanelMenu.Button {
    _init(extension) {
        super._init(0.0, 'Dictator');

        this._extension = extension;
        this._settings = extension.getSettings();
        this._state = 'idle';
        this._proxy = null;
        this._serviceAvailable = false;
        this._signalIds = [];
        this._settingsIds = [];
        this._shortcutRegistered = false;
        this._source = null;
        this._overlay = null;
        this._nameWatchId = 0;

        this._icon = new St.Icon({
            icon_name: 'audio-input-microphone-symbolic',
            style_class: 'system-status-icon dictator-icon-idle',
        });
        this.add_child(this._icon);

        this._buildMenu();
        this._connectToService();
        this._registerShortcut();

        this._settingsIds.push(this._settings.connect('changed::shortcut', () => {
            this._unregisterShortcut();
            this._registerShortcut();
        }));
        for (const key of ['model', 'output-mode', 'max-duration']) {
            this._settingsIds.push(this._settings.connect(`changed::${key}`, () => {
                this._pushConfig();
            }));
        }

        this._nameWatchId = Gio.bus_watch_name(
            Gio.BusType.SESSION, BUS_NAME, Gio.BusNameWatcherFlags.NONE,
            () => this._onServiceAppeared(),
            () => this._onServiceVanished()
        );
    }

    _buildMenu() {
        this._statusItem = new PopupMenu.PopupMenuItem(_('Idle'), {reactive: false});
        this.menu.addMenuItem(this._statusItem);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        this._toggleItem = new PopupMenu.PopupMenuItem(_('Start Dictation'));
        this._toggleItem.connect('activate', () => this._toggle());
        this.menu.addMenuItem(this._toggleItem);

        this._cancelItem = new PopupMenu.PopupMenuItem(_('Cancel'));
        this._cancelItem.connect('activate', () => this._cancel());
        this._cancelItem.visible = false;
        this.menu.addMenuItem(this._cancelItem);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        this._settingsItem = new PopupMenu.PopupMenuItem(_('Settings'));
        this._settingsItem.connect('activate', () => this._extension.openPreferences());
        this.menu.addMenuItem(this._settingsItem);
    }

    _connectToService() {
        new DictatorProxy(
            Gio.DBus.session, BUS_NAME, OBJECT_PATH,
            (proxy, error) => {
                if (error) {
                    console.error(`Dictator: failed to create proxy: ${error.message}`);
                    this._statusItem.label.text = _('Service unavailable');
                    return;
                }
                this._proxy = proxy;

                this._signalIds.push(proxy.connectSignal('StateChanged',
                    (p, sender, [state]) => this._onStateChanged(state)));
                this._signalIds.push(proxy.connectSignal('TranscriptionReady',
                    (p, sender, [text]) => this._onTranscriptionReady(text)));
                this._signalIds.push(proxy.connectSignal('Error',
                    (p, sender, [message]) => this._onError(message)));
                this._signalIds.push(proxy.connectSignal('AudioLevel',
                    (p, sender, [level]) => {
                        if (this._overlay)
                            this._overlay.pushLevel(level);
                    }));

                this._serviceAvailable = proxy.g_name_owner !== null;
                this._pushConfig();
                this._refreshState();
            }
        );
    }

    _onServiceAppeared() {
        console.log('Dictator: service appeared');
        this._serviceAvailable = true;
        this._pushConfig();
        this._refreshState();
    }

    _onServiceVanished() {
        console.log('Dictator: service vanished');
        this._serviceAvailable = false;
        this._onStateChanged('idle');
        this._statusItem.label.text = _('Service not running');
    }

    async _refreshState() {
        if (!this._proxy)
            return;
        try {
            const [state] = await this._proxy.GetStateAsync();
            this._onStateChanged(state);
        } catch (e) {
            console.error(`Dictator: GetState failed: ${e.message}`);
        }
    }

    async _pushConfig() {
        if (!this._proxy)
            return;
        const options = {
            'model': GLib.Variant.new_string(this._settings.get_string('model')),
            'output-mode': GLib.Variant.new_string(this._settings.get_string('output-mode')),
            'max-duration': GLib.Variant.new_double(this._settings.get_int('max-duration')),
        };
        try {
            await this._proxy.ConfigureAsync(options);
        } catch (e) {
            console.error(`Dictator: Configure failed: ${e.message}`);
        }
    }

    _registerShortcut() {
        if (this._shortcutRegistered)
            return;
        try {
            Main.wm.addKeybinding(
                'shortcut',
                this._settings,
                Meta.KeyBindingFlags.NONE,
                Shell.ActionMode.ALL,
                () => this._toggle()
            );
            this._shortcutRegistered = true;
        } catch (e) {
            console.error(`Dictator: failed to register shortcut: ${e.message}`);
        }
    }

    _unregisterShortcut() {
        if (!this._shortcutRegistered)
            return;
        try {
            Main.wm.removeKeybinding('shortcut');
        } catch (e) {
            console.error(`Dictator: failed to unregister shortcut: ${e.message}`);
        }
        this._shortcutRegistered = false;
    }

    async _toggle() {
        if (!this._proxy) {
            this._notify(_('Dictator'), _('Service not available'));
            return;
        }

        // Optimistic feedback: show the overlay before the round-trip.
        if (this._state === 'idle' || this._state === 'error')
            this._showOverlayState('starting');

        try {
            await this._proxy.ToggleAsync();
        } catch (e) {
            console.error(`Dictator: toggle failed: ${e.message}`);
            this._hideOverlay();
            this._notify(_('Dictator Error'), e.message);
        }
    }

    async _cancel() {
        if (!this._proxy)
            return;
        try {
            await this._proxy.CancelAsync();
        } catch (e) {
            console.error(`Dictator: cancel failed: ${e.message}`);
        }
    }

    _onStateChanged(state) {
        this._state = state;
        this._icon.style_class = `system-status-icon dictator-icon-${state}`;
        this._statusItem.label.text = STATE_LABELS[state] || state;

        if (state === 'idle' || state === 'error') {
            this._toggleItem.label.text = _('Start Dictation');
            this._cancelItem.visible = state === 'error';
        } else if (state === 'recording') {
            this._toggleItem.label.text = _('Stop & Transcribe');
            this._cancelItem.visible = true;
        } else {
            this._toggleItem.label.text = _('Working…');
            this._cancelItem.visible = true;
        }

        if (['recording', 'transcribing', 'typing', 'downloading'].includes(state))
            this._showOverlayState(state);
        else if (state === 'idle')
            this._hideOverlay();
        // 'error' overlay is handled by _onError with the message,
        // 'loading'/'downloading' at login shouldn't pop an overlay uninvited.
    }

    _onTranscriptionReady(text) {
        const trimmed = text ? text.trim() : '';
        if (this._overlayEnabled()) {
            this._ensureOverlay().showResult(trimmed);
        } else if (trimmed === '') {
            this._notify(_('Dictator'), _('No speech detected'));
        } else {
            const preview = trimmed.length > 50 ? `${trimmed.substring(0, 50)}…` : trimmed;
            this._notify(_('Dictation Complete'), preview);
        }
    }

    _onError(message) {
        if (this._overlayEnabled())
            this._ensureOverlay().showState('error', message);
        this._notify(_('Dictator Error'), message);
    }

    // ---------------------------------------------------------------- overlay

    _overlayEnabled() {
        return this._settings.get_boolean('show-overlay');
    }

    _ensureOverlay() {
        if (!this._overlay)
            this._overlay = new DictatorOverlay();
        return this._overlay;
    }

    _showOverlayState(state) {
        if (!this._overlayEnabled())
            return;
        this._ensureOverlay().showState(state);
    }

    _hideOverlay() {
        if (this._overlay)
            this._overlay.hideOverlay();
    }

    // ----------------------------------------------------------- notifications

    _getSource() {
        if (this._source)
            return this._source;
        if (SHELL_MAJOR >= 46) {
            this._source = new MessageTray.Source({
                title: 'Dictator',
                iconName: 'audio-input-microphone-symbolic',
            });
        } else {
            this._source = new MessageTray.Source(
                'Dictator', 'audio-input-microphone-symbolic');
        }
        this._source.connect('destroy', () => {
            this._source = null;
        });
        Main.messageTray.add(this._source);
        return this._source;
    }

    _notify(title, body) {
        if (!this._settings.get_boolean('show-notifications'))
            return;
        try {
            const source = this._getSource();
            if (SHELL_MAJOR >= 46) {
                const notification = new MessageTray.Notification({
                    source, title, body, isTransient: true,
                });
                source.addNotification(notification);
            } else {
                const notification = new MessageTray.Notification(source, title, body);
                notification.setTransient(true);
                source.showNotification(notification);
            }
        } catch (e) {
            console.error(`Dictator: notification failed: ${e.message}`);
        }
    }

    destroy() {
        if (this._nameWatchId) {
            Gio.bus_unwatch_name(this._nameWatchId);
            this._nameWatchId = 0;
        }

        for (const id of this._settingsIds)
            this._settings.disconnect(id);
        this._settingsIds = [];

        if (this._proxy) {
            for (const id of this._signalIds)
                this._proxy.disconnectSignal(id);
            this._signalIds = [];
            this._proxy = null;
        }

        this._unregisterShortcut();

        if (this._overlay) {
            this._overlay.destroy();
            this._overlay = null;
        }

        super.destroy();
    }
});


export default class DictatorExtension extends Extension {
    enable() {
        this._indicator = new DictatorIndicator(this);
        Main.panel.addToStatusArea('dictator', this._indicator);
    }

    disable() {
        this._indicator?.destroy();
        this._indicator = null;
    }
}
