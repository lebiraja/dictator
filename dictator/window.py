"""Floating overlay window for dictation."""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk, GLib, Gio


class DictatorWindow(Gtk.Window):
    """Floating overlay popup with mic button."""

    # States
    STATE_IDLE = "idle"
    STATE_RECORDING = "recording"
    STATE_TRANSCRIBING = "transcribing"

    def __init__(self, app, on_toggle_callback):
        super().__init__(application=app)

        self.on_toggle = on_toggle_callback
        self._state = self.STATE_IDLE

        # Window setup - make it a popup overlay
        self.set_title("Dictator")
        self.set_default_size(140, 100)
        self.set_resizable(False)
        self.set_decorated(False)  # No title bar
        self.set_deletable(False)

        # Critical: Make it a popup/overlay
        self.set_modal(False)

        # Set as a utility window (no taskbar entry)
        # Note: On Wayland, we use layer-shell or just hide from taskbar
        self.set_hide_on_close(True)

        # Main container with rounded corners effect
        self.overlay_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.overlay_box.set_halign(Gtk.Align.CENTER)
        self.overlay_box.set_valign(Gtk.Align.CENTER)
        self.overlay_box.add_css_class("overlay-container")

        # Mic button
        self.mic_button = Gtk.Button()
        self.mic_button.set_size_request(80, 80)
        self.mic_button.add_css_class("circular")
        self.mic_button.add_css_class("mic-button")
        self.mic_button.add_css_class("mic-idle")
        self.mic_button.connect("clicked", self._on_mic_clicked)

        # Mic icon
        self.mic_icon = Gtk.Image.new_from_icon_name("audio-input-microphone-symbolic")
        self.mic_icon.set_pixel_size(36)
        self.mic_button.set_child(self.mic_icon)

        self.overlay_box.append(self.mic_button)

        # Status label
        self.status_label = Gtk.Label(label="Click to speak")
        self.status_label.add_css_class("status-label")
        self.status_label.set_margin_top(8)
        self.overlay_box.append(self.status_label)

        # Spinner for transcribing state (hidden initially)
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(36, 36)

        self.set_child(self.overlay_box)

        # Apply CSS
        self._apply_css()

        # Handle ESC key to cancel
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

        # Position at top-center of screen
        self.connect("realize", self._on_realize)

    def _on_realize(self, widget):
        """Position window when realized."""
        # Center horizontally at top of screen
        display = Gdk.Display.get_default()
        if display:
            monitors = display.get_monitors()
            if monitors.get_n_items() > 0:
                monitor = monitors.get_item(0)
                geometry = monitor.get_geometry()
                # Position at top center
                x = geometry.x + (geometry.width - 140) // 2
                y = geometry.y + 50  # 50px from top
                # Note: On Wayland we can't set position freely
                # The window manager decides placement

    def _apply_css(self):
        """Apply custom CSS styling."""
        css = b"""
        window {
            background-color: transparent;
        }

        .overlay-container {
            background-color: rgba(20, 20, 20, 0.92);
            border-radius: 20px;
            padding: 16px;
        }

        .mic-button {
            border-radius: 50%;
            border: none;
            min-width: 80px;
            min-height: 80px;
        }

        .mic-idle {
            background-color: #444444;
            color: white;
        }

        .mic-idle:hover {
            background-color: #555555;
        }

        .mic-recording {
            background-color: #e53935;
            color: white;
        }

        .mic-transcribing {
            background-color: #1e88e5;
            color: white;
        }

        .status-label {
            font-size: 12px;
            font-weight: 500;
            color: rgba(255, 255, 255, 0.8);
        }
        """

        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _on_mic_clicked(self, button):
        """Handle mic button click."""
        if self._state != self.STATE_TRANSCRIBING:
            self.on_toggle()

    def _on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key press events."""
        if keyval == Gdk.KEY_Escape:
            # Cancel and hide
            if self._state == self.STATE_RECORDING:
                self.on_toggle()  # Cancel recording
            self.hide()
            return True
        return False

    def set_state(self, state: str):
        """Update the window state.

        Args:
            state: One of STATE_IDLE, STATE_RECORDING, STATE_TRANSCRIBING
        """
        self._state = state

        # Update button style classes
        self.mic_button.remove_css_class("mic-idle")
        self.mic_button.remove_css_class("mic-recording")
        self.mic_button.remove_css_class("mic-transcribing")

        if state == self.STATE_RECORDING:
            self.mic_button.add_css_class("mic-recording")
            self.status_label.set_text("Recording... click to stop")
            self.mic_button.set_child(self.mic_icon)
            self.mic_icon.set_from_icon_name("audio-input-microphone-symbolic")

        elif state == self.STATE_TRANSCRIBING:
            self.mic_button.add_css_class("mic-transcribing")
            self.status_label.set_text("Transcribing...")
            # Show spinner in button
            self.mic_button.set_child(self.spinner)
            self.spinner.start()

        else:  # IDLE
            self.mic_button.add_css_class("mic-idle")
            self.status_label.set_text("Click to speak")
            self.spinner.stop()
            self.mic_button.set_child(self.mic_icon)
            self.mic_icon.set_from_icon_name("audio-input-microphone-symbolic")

    def show_result(self, text: str, success: bool = True):
        """Show transcription result briefly.

        Args:
            text: Transcription result or error message.
            success: Whether transcription was successful.
        """
        if success and text:
            preview = text[:25] + "..." if len(text) > 25 else text
            self.status_label.set_text(f"✓ Copied!")
        elif success:
            self.status_label.set_text("No speech detected")
        else:
            self.status_label.set_text(f"Error")

        self.set_state(self.STATE_IDLE)

        # Hide after a short delay
        GLib.timeout_add(1500, self._hide_after_result)

    def _hide_after_result(self):
        """Hide window after showing result."""
        self.hide()
        return False

    def show_popup(self):
        """Show the popup overlay."""
        self.present()
        self.set_visible(True)
