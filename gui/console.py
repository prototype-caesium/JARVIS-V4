"""
console.py
----------
The bottom command console. Shows the YOU / JARVIS transcript and lets the
person either type a command (sent straight to core.commands.process_command)
or use the mic buttons to drive the real voice pipeline via gui.worker.
"""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GObject, GLib

MAX_LINES = 200


class Console(Gtk.Box):
    __gsignals__ = {
        "submit-text": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "mic-toggle": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "push-to-talk": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add_css_class("console")
        self.set_size_request(-1, 190)

        # -- transcript log --------------------------------------------------
        self.log_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        scroller = Gtk.ScrolledWindow()
        scroller.add_css_class("console-scroll")
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(self.log_box)
        scroller.set_vexpand(True)
        self._scroller = scroller
        self.append(scroller)

        self._line_count = 0
        self.add_line("JARVIS", "Standing by, Boss.")

        # -- input row ---------------------------------------------------------
        input_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self.continuous_btn = Gtk.ToggleButton(label="◉")
        self.continuous_btn.add_css_class("mic-btn")
        self.continuous_btn.set_tooltip_text("Toggle continuous listening (mirrors main.py loop)")
        self.continuous_btn.connect("toggled", lambda b: self.emit("mic-toggle"))
        input_row.append(self.continuous_btn)

        self.ptt_btn = Gtk.Button(label="⏺")
        self.ptt_btn.add_css_class("mic-btn")
        self.ptt_btn.set_tooltip_text("Push-to-talk: listen once")
        self.ptt_btn.connect("clicked", lambda b: self.emit("push-to-talk"))
        input_row.append(self.ptt_btn)

        self.entry = Gtk.Entry()
        self.entry.add_css_class("console-entry")
        self.entry.set_placeholder_text("Type a command...")
        self.entry.set_hexpand(True)
        self.entry.connect("activate", self._on_activate)
        input_row.append(self.entry)

        send_btn = Gtk.Button(label="SEND")
        send_btn.add_css_class("send-btn")
        send_btn.connect("clicked", self._on_activate)
        input_row.append(send_btn)

        self.append(input_row)

    def _on_activate(self, _widget):
        text = self.entry.get_text().strip()
        if not text:
            return
        self.entry.set_text("")
        self.emit("submit-text", text)

    def set_listening_visual(self, active: bool):
        if active:
            self.continuous_btn.add_css_class("listening")
        else:
            self.continuous_btn.remove_css_class("listening")

    def add_line(self, who: str, text: str):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        tag = Gtk.Label(label=who)
        tag.set_xalign(0)
        tag.add_css_class("console-you" if who == "YOU" else "console-jarvis")
        tag.set_size_request(56, -1)
        row.append(tag)

        msg = Gtk.Label(label=text)
        msg.set_xalign(0)
        msg.set_wrap(True)
        msg.add_css_class("status-value")
        row.append(msg)

        self.log_box.append(row)
        self._line_count += 1

        if self._line_count > MAX_LINES:
            first = self.log_box.get_first_child()
            if first is not None:
                self.log_box.remove(first)

        # scroll to bottom on next idle tick (after layout has updated)
        adj = self._scroller.get_vadjustment()
        if adj is not None:
            GLib.idle_add(self._scroll_to_bottom, adj)

    @staticmethod
    def _scroll_to_bottom(adj):
        adj.set_value(adj.get_upper())
        return False
