"""JARVIS V4 - main window and wiring."""

import time

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from gui import theme as T  # noqa: E402
from gui.bridge import QUICK_COMMANDS, AssistantBridge  # noqa: E402
from gui.hud import Animator, CoreWidget, WaveformWidget  # noqa: E402
from gui.metrics import SystemMetrics  # noqa: E402
from gui.panels import (ActivityPanel, DeviceStatusPanel, Panel,
                        QuickCommandsPanel, SchedulePanel,
                        SystemStatusPanel, WeatherPanel, _label)
from gui.voice_state import AppState, VoiceState  # noqa: E402

APP_ID = "org.jarvis.v4.hud"
DEVICE_NAMES = ["Arduino", "Camera", "Microphone", "Speaker", "Groq AI"]
QUOTE = "The best way to predict the future is to create it."


class JarvisWindow(Gtk.ApplicationWindow):

    def __init__(self, application, fullscreen=True, voice=True):
        Gtk.ApplicationWindow.__init__(
            self,
            application=application,
            title="JARVIS V4"
        )

        self.get_style_context().add_class("jarvis")
        self.set_default_size(1366, 768)

        self.state = AppState()
        self.metrics = SystemMetrics()
        self.anim = Animator()

        self.bridge = AssistantBridge(self._emit_from_thread)
        self.bridge.set_state_callback(self._state_from_thread)
        self.bridge.set_shutdown_callback(self._shutdown_from_thread)

        self._timers = []
        self._shutting_down = False
        self._is_fullscreen = False

        self._build()

        self.connect("destroy", self.on_destroy)
        self.connect("key-press-event", self.on_key)
        self.connect("window-state-event", self.on_window_state)

        self.show_all()

        if fullscreen:
            self.fullscreen()

        self.anim.start()

        self._add_timer(1000, self._tick_clock)
        self._add_timer(2000, self._tick_metrics)
        self._add_timer(4000, self._tick_devices)

        self._tick_clock()
        self._tick_metrics()
        self._tick_devices()

        if voice:
            self.bridge.start()
        else:
            self._append("system", "voice disabled (--no-voice)")

    # ------------------------------------------------------------ build
    def _add_timer(self, interval, fn):
        self._timers.append(GLib.timeout_add(interval, self._wrap(fn)))

    def _wrap(self, fn):
        def runner():
            if self._shutting_down:
                return False

            try:
                fn()

            except Exception as exc:
                self._append(
                    "error",
                    "timer %s: %s" % (fn.__name__, exc)
                )

            return True

        return runner

    def _build(self):
        root = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0
        )

        self.add(root)

        root.pack_start(
            self._build_topbar(),
            False,
            False,
            0
        )

        middle = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=T.GUTTER
        )

        middle.set_border_width(T.GUTTER)

        root.pack_start(
            middle,
            True,
            True,
            0
        )

        middle.pack_start(
            self._build_left(),
            False,
            False,
            0
        )

        middle.pack_start(
            self._build_center(),
            True,
            True,
            0
        )

        middle.pack_start(
            self._build_right(),
            False,
            False,
            0
        )

        root.pack_start(
            self._build_bottom(),
            False,
            False,
            0
        )

    def _build_topbar(self):
        bar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10
        )

        bar.get_style_context().add_class("topbar")

        bar.pack_start(
            _label("JARVIS V4", "brand"),
            False,
            False,
            0
        )

        self.online_lb = _label("\u25cf ONLINE", "online")

        bar.pack_start(
            self.online_lb,
            False,
            False,
            4
        )

        self.clock_lb = _label(
            "",
            "clock",
            xalign=0.5
        )

        bar.set_center_widget(self.clock_lb)

        self.audio_lb = _label("AUD --", "muted")
        self.bt_lb = _label("BT --", "muted")
        self.wifi_lb = _label("WIFI --", "muted")
        self.batt_lb = _label("BAT --", "muted")

        for widget in (
            self.batt_lb,
            self.audio_lb,
            self.bt_lb,
            self.wifi_lb
        ):
            bar.pack_end(
                widget,
                False,
                False,
                3
            )

        return bar

    def _build_left(self):
        col = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=T.GUTTER
        )

        col.set_size_request(
            T.SIDE_WIDTH,
            -1
        )

        self.sys_panel = SystemStatusPanel()

        labels = [
            item[0]
            for item in QUICK_COMMANDS
        ]

        self.cmd_panel = QuickCommandsPanel(
            labels,
            self._on_quick
        )

        self.weather_panel = WeatherPanel()

        col.pack_start(
            self.sys_panel,
            False,
            False,
            0
        )

        col.pack_start(
            self.cmd_panel,
            False,
            False,
            0
        )

        col.pack_start(
            self.weather_panel,
            False,
            False,
            0
        )

        scroller = Gtk.ScrolledWindow()

        scroller.set_policy(
            Gtk.PolicyType.NEVER,
            Gtk.PolicyType.AUTOMATIC
        )

        scroller.set_size_request(
            T.SIDE_WIDTH,
            -1
        )

        scroller.add(col)

        return scroller

    def _build_center(self):
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6
        )

        self.core = CoreWidget(self.anim)

        box.pack_start(
            self.core,
            True,
            True,
            0
        )

        self.waveform = WaveformWidget(self.anim)

        box.pack_start(
            self.waveform,
            False,
            False,
            0
        )

        controls = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12
        )

        controls.set_halign(Gtk.Align.CENTER)

        self.mic_btn = Gtk.Button(
            label="\U0001F3A4"
        )

        self.mic_btn.get_style_context().add_class("mic")

        self.mic_btn.set_size_request(
            68,
            68
        )

        self.mic_btn.set_relief(
            Gtk.ReliefStyle.NONE
        )

        self.mic_btn.connect(
            "clicked",
            self._on_mic
        )

        controls.pack_start(
            self.mic_btn,
            False,
            False,
            0
        )

        text_col = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=2
        )

        text_col.set_valign(
            Gtk.Align.CENTER
        )

        self.status_lb = Gtk.Label()
        self.status_lb.set_xalign(0.0)

        text_col.pack_start(
            self.status_lb,
            False,
            False,
            0
        )

        self.reply_lb = _label(
            "",
            "muted"
        )

        self.reply_lb.set_line_wrap(True)
        self.reply_lb.set_max_width_chars(58)

        text_col.pack_start(
            self.reply_lb,
            False,
            False,
            0
        )

        controls.pack_start(
            text_col,
            False,
            False,
            0
        )

        box.pack_start(
            controls,
            False,
            False,
            6
        )

        self._render_status()

        return box

    def _build_right(self):
        col = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=T.GUTTER
        )

        col.set_size_request(
            T.SIDE_WIDTH,
            -1
        )

        self.schedule_panel = SchedulePanel()
        self.activity_panel = ActivityPanel()
        self.device_panel = DeviceStatusPanel(DEVICE_NAMES)

        col.pack_start(
            self.schedule_panel,
            False,
            False,
            0
        )

        col.pack_start(
            self.activity_panel,
            True,
            True,
            0
        )

        col.pack_start(
            self.device_panel,
            False,
            False,
            0
        )

        return col

    def _build_bottom(self):
        bar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=T.GUTTER
        )

        bar.set_border_width(T.GUTTER)

        avatar = Panel("Jarvis")

        avatar.set_size_request(
            T.SIDE_WIDTH,
            -1
        )

        avatar.body.pack_start(
            _label(
                "Always with you, Boss.",
                "muted"
            ),
            False,
            False,
            0
        )

        self.hint_lb = _label(
            "F11 fullscreen  \u2022  Esc window  \u2022  Ctrl+Q quit",
            "tiny"
        )

        avatar.body.pack_start(
            self.hint_lb,
            False,
            False,
            0
        )

        bar.pack_start(
            avatar,
            False,
            False,
            0
        )

        spacer = Gtk.Box()

        bar.pack_start(
            spacer,
            True,
            True,
            0
        )

        quote = Panel("\u2014 JARVIS")

        quote.set_size_request(
            T.SIDE_WIDTH + 40,
            -1
        )

        q = _label(
            '"%s"' % QUOTE,
            "muted"
        )

        q.set_line_wrap(True)
        q.set_max_width_chars(34)

        quote.body.pack_start(
            q,
            False,
            False,
            0
        )

        bar.pack_end(
            quote,
            False,
            False,
            0
        )

        return bar

    # ------------------------------------------------------------ events
    def _emit_from_thread(self, event):
        GLib.idle_add(
            self._on_event,
            event,
            priority=GLib.PRIORITY_DEFAULT_IDLE
        )

    def _state_from_thread(self, state):
        GLib.idle_add(
            self._on_state,
            state,
            priority=GLib.PRIORITY_DEFAULT_IDLE
        )

    # NEW: called from the JARVIS listener thread after speech finishes.
    def _shutdown_from_thread(self):
        GLib.idle_add(
            self._shutdown_gui,
            priority=GLib.PRIORITY_DEFAULT_IDLE
        )

    # NEW: GTK-safe shutdown.
    def _shutdown_gui(self):
        if self._shutting_down:
            return False

        self._append(
            "system",
            "JARVIS shutting down..."
        )

        self.close()

        return False

    def _on_event(self, event):
        if self._shutting_down:
            return False

        self.activity_panel.add_event(event)

        if event.kind == "user":
            self.state.last_user = event.text

        elif event.kind == "jarvis":
            self.state.last_reply = event.text
            self.reply_lb.set_text(
                event.text[:180]
            )

        elif event.kind == "error":
            self.reply_lb.set_text(
                event.text[:180]
            )

        return False

    def _append(self, kind, text):
        from gui.voice_state import Event

        self._on_event(
            Event(kind, text)
        )

    def _on_state(self, state):
        if self._shutting_down:
            return False

        self.state.set_voice(state)

        self.core.set_state(state)
        self.waveform.set_state(state)

        self.anim.set_active(
            state in (
                VoiceState.LISTENING,
                VoiceState.SPEAKING,
                VoiceState.PROCESSING
            )
        )

        self._render_status()

        return False

    def _render_status(self):
        from gui.hud import STATE_ACCENT

        rgb = STATE_ACCENT.get(
            self.state.voice,
            T.CYAN
        )

        hexc = "#%02x%02x%02x" % (
            int(rgb[0] * 255),
            int(rgb[1] * 255),
            int(rgb[2] * 255)
        )

        self.status_lb.set_markup(
            '<span foreground="%s" size="11500"><b>%s</b></span>'
            % (
                hexc,
                GLib.markup_escape_text(
                    self.state.status_line
                )
            )
        )

    def _on_mic(self, _button):
        enabled = not self.bridge.is_enabled()

        self.bridge.set_enabled(enabled)

        ctx = self.mic_btn.get_style_context()

        if enabled:
            ctx.remove_class("muted")
            self._append(
                "system",
                "microphone resumed"
            )
            self._on_state(
                VoiceState.IDLE
            )

        else:
            ctx.add_class("muted")
            self._append(
                "system",
                "microphone paused"
            )
            self._on_state(
                VoiceState.MUTED
            )

    def _on_quick(self, label):
        self.bridge.run_quick(label)

    def on_key(self, _widget, event):
        keyval = event.keyval

        ctrl = bool(
            event.state & Gdk.ModifierType.CONTROL_MASK
        )

        if keyval == Gdk.KEY_F11:
            if self._is_fullscreen:
                self.unfullscreen()
            else:
                self.fullscreen()

            return True

        if keyval == Gdk.KEY_Escape and self._is_fullscreen:
            self.unfullscreen()
            return True

        if ctrl and keyval in (
            Gdk.KEY_q,
            Gdk.KEY_Q
        ):
            self.close()
            return True

        return False

    def on_window_state(self, _widget, event):
        self._is_fullscreen = bool(
            event.new_window_state
            & Gdk.WindowState.FULLSCREEN
        )

        withdrawn = bool(
            event.new_window_state
            & Gdk.WindowState.ICONIFIED
        )

        if withdrawn:
            self.anim.pause()
        else:
            self.anim.resume()

        return False

    # ------------------------------------------------------------ timers
    def _tick_clock(self):
        now = time.localtime()

        self.clock_lb.set_text(
            time.strftime(
                "%I:%M:%S %p   |   %a, %d %b %Y",
                now
            )
        )

    def _tick_metrics(self):
        m = self.metrics

        self.sys_panel.update(m)

        batt = m.battery()

        if batt is None:
            self.batt_lb.set_text("BAT n/a")

        else:
            pct, plugged = batt

            self.batt_lb.set_text(
                "BAT %d%%%s"
                % (
                    pct,
                    " \u26a1" if plugged else ""
                )
            )

        wifi = m.wifi()

        if wifi is None:
            self.wifi_lb.set_text("WIFI n/a")

        else:
            name, quality, up = wifi

            self.wifi_lb.set_text(
                "WIFI %s %d%%"
                % (
                    "up" if up else "down",
                    quality
                )
            )

        self.bt_lb.set_text(
            "BT %s" % m.bluetooth()
        )

        self.audio_lb.set_text(
            "AUD %s" % m.audio()
        )

    def _tick_devices(self):
        m = self.metrics
        voice = self.state.voice

        mic = "Offline"

        if m.mic_present():
            mic = (
                "Active"
                if voice == VoiceState.LISTENING
                else self.bridge.listener_status()
            )

        speaker = self.bridge.speaker_status()

        if voice == VoiceState.SPEAKING and speaker == "Ready":
            speaker = "Active"

        self.device_panel.set_status({
            "Arduino": self.bridge.arduino_status(),
            "Camera": (
                "Ready"
                if m.camera_present()
                else "Offline"
            ),
            "Microphone": mic,
            "Speaker": speaker,
            "Groq AI": self.bridge.ai_status,
        })

    # ------------------------------------------------------------ teardown
    def on_destroy(self, _widget):
        if self._shutting_down:
            return

        self._shutting_down = True

        for source in self._timers:
            try:
                GLib.source_remove(source)
            except Exception:
                pass

        self._timers = []

        self.anim.shutdown()
        self.bridge.stop()


class JarvisApplication(Gtk.Application):

    def __init__(self, fullscreen=True, voice=True):
        Gtk.Application.__init__(
            self,
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )

        self._fullscreen = fullscreen
        self._voice = voice
        self._window = None
        self._css_done = False

    def do_startup(self):
        Gtk.Application.do_startup(self)

        if self._css_done:
            return

        provider = Gtk.CssProvider()

        try:
            provider.load_from_data(
                T.CSS.encode("utf-8")
            )

            screen = Gdk.Screen.get_default()

            if screen is not None:
                Gtk.StyleContext.add_provider_for_screen(
                    screen,
                    provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )

        except Exception as exc:
            print("CSS load failed: %s" % exc)

        self._css_done = True

    def do_activate(self):
        if self._window is None:
            self._window = JarvisWindow(
                self,
                fullscreen=self._fullscreen,
                voice=self._voice
            )

        self._window.present()


def run(argv=None, fullscreen=True, voice=True):
    app = JarvisApplication(
        fullscreen=fullscreen,
        voice=voice
    )

    return app.run(None)
