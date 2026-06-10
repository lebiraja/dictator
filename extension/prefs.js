/**
 * Dictator GNOME Shell Extension - Preferences
 */

import Adw from 'gi://Adw';
import Gtk from 'gi://Gtk';
import Gio from 'gi://Gio';
import {ExtensionPreferences, gettext as _} from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

const MODELS = [
    {id: 'tiny.en', label: 'tiny.en — fastest, lowest accuracy (~75 MB)'},
    {id: 'base.en', label: 'base.en — fast, good accuracy (~140 MB)'},
    {id: 'small.en', label: 'small.en — slower, best accuracy (~460 MB)'},
];

const OUTPUT_MODES = [
    {id: 'clipboard', label: _('Paste (recommended)'), subtitle: _('Instant via Ctrl+V, keeps your clipboard')},
    {id: 'type', label: _('Type'), subtitle: _('Simulates each keystroke — for apps that block pasting')},
];


export default class DictatorPreferences extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const settings = this.getSettings();
        const page = new Adw.PreferencesPage();
        window.add(page);

        // ------------------------------------------------------------ Shortcut
        const shortcutGroup = new Adw.PreferencesGroup({
            title: _('Keyboard Shortcut'),
        });
        page.add(shortcutGroup);

        const shortcutRow = new Adw.ActionRow({
            title: _('Toggle Dictation'),
            subtitle: _('Click the button, then press your key combination'),
        });
        const shortcutButton = new Gtk.Button({
            label: this._getShortcutLabel(settings.get_strv('shortcut')),
            valign: Gtk.Align.CENTER,
        });
        shortcutButton.connect('clicked', () => {
            this._recordShortcut(shortcutButton, settings);
        });
        shortcutRow.add_suffix(shortcutButton);
        shortcutRow.activatable_widget = shortcutButton;
        shortcutGroup.add(shortcutRow);

        const resetRow = new Adw.ActionRow({
            title: _('Reset to Default'),
            subtitle: _('Shift+Ctrl+Space'),
        });
        const resetButton = new Gtk.Button({
            label: _('Reset'),
            valign: Gtk.Align.CENTER,
        });
        resetButton.connect('clicked', () => {
            settings.set_strv('shortcut', ['<Shift><Control>space']);
            shortcutButton.label = this._getShortcutLabel(['<Shift><Control>space']);
        });
        resetRow.add_suffix(resetButton);
        resetRow.activatable_widget = resetButton;
        shortcutGroup.add(resetRow);

        // -------------------------------------------------------- Transcription
        const transcriptionGroup = new Adw.PreferencesGroup({
            title: _('Transcription'),
        });
        page.add(transcriptionGroup);

        const modelRow = new Adw.ComboRow({
            title: _('Whisper Model'),
            subtitle: _('Larger models are more accurate but slower; changing triggers a download'),
            model: new Gtk.StringList({strings: MODELS.map(m => m.label)}),
        });
        modelRow.selected = Math.max(0,
            MODELS.findIndex(m => m.id === settings.get_string('model')));
        modelRow.connect('notify::selected', () => {
            settings.set_string('model', MODELS[modelRow.selected].id);
        });
        transcriptionGroup.add(modelRow);

        const durationRow = new Adw.SpinRow({
            title: _('Max Recording Duration'),
            subtitle: _('Seconds before recording auto-stops and transcribes'),
            adjustment: new Gtk.Adjustment({
                lower: 10, upper: 600, step_increment: 10, page_increment: 30,
            }),
        });
        settings.bind('max-duration', durationRow, 'value', Gio.SettingsBindFlags.DEFAULT);
        transcriptionGroup.add(durationRow);

        // --------------------------------------------------------------- Output
        const outputGroup = new Adw.PreferencesGroup({
            title: _('Text Output'),
            description: _('Note: terminals usually paste with Ctrl+Shift+V — use Type mode for terminal-heavy work'),
        });
        page.add(outputGroup);

        const outputRow = new Adw.ComboRow({
            title: _('Output Mode'),
            model: new Gtk.StringList({strings: OUTPUT_MODES.map(m => m.label)}),
        });
        outputRow.selected = Math.max(0,
            OUTPUT_MODES.findIndex(m => m.id === settings.get_string('output-mode')));
        outputRow.subtitle = OUTPUT_MODES[outputRow.selected].subtitle;
        outputRow.connect('notify::selected', () => {
            const mode = OUTPUT_MODES[outputRow.selected];
            settings.set_string('output-mode', mode.id);
            outputRow.subtitle = mode.subtitle;
        });
        outputGroup.add(outputRow);

        // ----------------------------------------------------------- Appearance
        const appearanceGroup = new Adw.PreferencesGroup({
            title: _('Appearance'),
        });
        page.add(appearanceGroup);

        const overlayRow = new Adw.SwitchRow({
            title: _('Show Overlay'),
            subtitle: _('Floating status pill with live audio level while dictating'),
        });
        settings.bind('show-overlay', overlayRow, 'active', Gio.SettingsBindFlags.DEFAULT);
        appearanceGroup.add(overlayRow);

        const notificationsRow = new Adw.SwitchRow({
            title: _('Show Notifications'),
            subtitle: _('Notify on results and errors'),
        });
        settings.bind('show-notifications', notificationsRow, 'active', Gio.SettingsBindFlags.DEFAULT);
        appearanceGroup.add(notificationsRow);
    }

    _recordShortcut(button, settings) {
        button.label = _('Press keys…');
        button.add_css_class('suggested-action');

        const controller = new Gtk.EventControllerKey();
        controller.connect('key-pressed', (ctrl, keyval, keycode, state) => {
            const modifiers = state & Gtk.accelerator_get_default_mod_mask();

            if (keyval === 65307) { // Escape — cancel
                button.label = this._getShortcutLabel(settings.get_strv('shortcut'));
                button.remove_css_class('suggested-action');
                button.remove_controller(controller);
                return true;
            }

            if (modifiers === 0)
                return false; // require at least one modifier

            const shortcut = Gtk.accelerator_name(keyval, modifiers);
            if (shortcut) {
                settings.set_strv('shortcut', [shortcut]);
                button.label = this._getShortcutLabel([shortcut]);
                button.remove_css_class('suggested-action');
                button.remove_controller(controller);
                return true;
            }
            return false;
        });
        button.add_controller(controller);
    }

    _getShortcutLabel(shortcutArray) {
        if (!shortcutArray || shortcutArray.length === 0)
            return _('Not set');

        const [success, key, mods] = Gtk.accelerator_parse(shortcutArray[0]);
        if (!success || (key === 0 && mods === 0))
            return _('Not set');

        return Gtk.accelerator_get_label(key, mods);
    }
}
