/**
 * Dictator GNOME Shell Extension - Preferences
 *
 * Settings UI for customizing keyboard shortcuts.
 */

import Adw from 'gi://Adw';
import Gtk from 'gi://Gtk';
import Gio from 'gi://Gio';
import {ExtensionPreferences} from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

export default class DictatorPreferences extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const settings = this.getSettings();

        // Create preferences page
        const page = new Adw.PreferencesPage();
        const group = new Adw.PreferencesGroup({
            title: 'Keyboard Shortcut',
            description: 'Customize the shortcut to toggle dictation',
        });
        page.add(group);

        // Shortcut row with button
        const shortcutRow = new Adw.ActionRow({
            title: 'Toggle Dictation Shortcut',
            subtitle: 'Click the button and press your desired key combination',
        });

        // Shortcut button
        const shortcutButton = new Gtk.Button({
            label: this._getShortcutLabel(settings.get_strv('shortcut')),
            valign: Gtk.Align.CENTER,
        });

        // Make button trigger shortcut recording
        shortcutButton.connect('clicked', () => {
            this._recordShortcut(shortcutButton, settings);
        });

        shortcutRow.add_suffix(shortcutButton);
        shortcutRow.activatable_widget = shortcutButton;
        group.add(shortcutRow);

        // Reset button
        const resetRow = new Adw.ActionRow({
            title: 'Reset to Default',
            subtitle: 'Restore the default shortcut (Ctrl+Shift+Space)',
        });

        const resetButton = new Gtk.Button({
            label: 'Reset',
            valign: Gtk.Align.CENTER,
        });

        resetButton.connect('clicked', () => {
            settings.set_strv('shortcut', ['<Control><Shift>space']);
            shortcutButton.label = this._getShortcutLabel(['<Control><Shift>space']);
        });

        resetRow.add_suffix(resetButton);
        resetRow.activatable_widget = resetButton;
        group.add(resetRow);

        window.add(page);
    }

    _recordShortcut(button, settings) {
        // Change button appearance to indicate recording
        button.label = 'Press keys...';
        button.add_css_class('recording');

        // Create event controller for key capture
        const controller = new Gtk.EventControllerKey();

        controller.connect('key-pressed', (controller, keyval, keycode, state) => {
            // Ignore modifier-only presses
            const modifiers = state & Gtk.accelerator_get_default_mod_mask();

            if (keyval === 65307) { // Escape key
                // Cancel recording
                button.label = this._getShortcutLabel(settings.get_strv('shortcut'));
                button.remove_css_class('recording');
                button.remove_controller(controller);
                return true;
            }

            // Check if it's a valid shortcut (has modifiers)
            if (modifiers === 0) {
                return false;
            }

            // Build shortcut string
            const shortcutString = Gtk.accelerator_name(keyval, modifiers);

            if (shortcutString) {
                settings.set_strv('shortcut', [shortcutString]);
                button.label = this._getShortcutLabel([shortcutString]);
                button.remove_css_class('recording');
                button.remove_controller(controller);
                return true;
            }

            return false;
        });

        button.add_controller(controller);
    }

    _getShortcutLabel(shortcutArray) {
        if (!shortcutArray || shortcutArray.length === 0) {
            return 'Not set';
        }

        const shortcut = shortcutArray[0];

        // Parse the shortcut string and make it human-readable
        const [success, key, mods] = Gtk.accelerator_parse(shortcut);

        if (!success || (key === 0 && mods === 0)) {
            return 'Not set';
        }

        return Gtk.accelerator_get_label(key, mods);
    }
}
