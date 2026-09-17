"""
sidebar.py
----------
Vertical nav rail: HOME / VOICE / SYSTEM / AUTOMATION / VISION / ARDUINO /
LOGS / SETTINGS. Emits "page-selected" with the page id when clicked;
app.py listens and swaps the Gtk.Stack page.
"""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GObject

from gui.icons import NavIcon

NAV_ITEMS = [
    ("home", "HOME"),
    ("voice", "VOICE"),
    ("system", "SYSTEM"),
    ("automation", "AUTOMATION"),
    ("vision", "VISION"),
    ("arduino", "ARDUINO"),
    ("logs", "LOGS"),
    ("settings", "SETTINGS"),
]


class Sidebar(Gtk.Box):
    __gsignals__ = {
        "page-selected": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.add_css_class("sidebar")
        self.set_size_request(76, -1)

        self._buttons = {}
        for page_id, label in NAV_ITEMS:
            btn = self._make_button(page_id, label)
            self._buttons[page_id] = btn
            self.append(btn)

        self.set_active("home")

    def _make_button(self, page_id, label_text):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_halign(Gtk.Align.CENTER)

        icon = NavIcon(page_id)
        box.append(icon)

        label = Gtk.Label(label=label_text)
        label.add_css_class("nav-label")
        box.append(label)

        btn = Gtk.Button()
        btn.add_css_class("nav-btn")
        btn.set_child(box)
        btn.connect("clicked", lambda b, pid=page_id: self._on_click(pid))
        return btn

    def _on_click(self, page_id):
        self.set_active(page_id)
        self.emit("page-selected", page_id)

    def set_active(self, page_id):
        for pid, btn in self._buttons.items():
            if pid == page_id:
                btn.add_css_class("active")
            else:
                btn.remove_css_class("active")
