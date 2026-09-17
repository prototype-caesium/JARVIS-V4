"""
topbar.py
---------
JARVIS / AI SYSTEM // V4 / SYSTEM ONLINE + live CPU/RAM/battery/wifi/clock.
Polls gui.sysmonitor on a 1s GLib timer - psutil calls here are all cheap.
"""

import time

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

from gui import sysmonitor


class TopBar(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        self.add_css_class("topbar")

        # -- brand block ---------------------------------------------------
        brand_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        title = Gtk.Label(label="JARVIS")
        title.add_css_class("brand-title")
        title.set_xalign(0)
        sub = Gtk.Label(label="AI SYSTEM // V4")
        sub.add_css_class("brand-sub")
        sub.set_xalign(0)
        brand_box.append(title)
        brand_box.append(sub)
        self.append(brand_box)

        # -- online indicator ------------------------------------------------
        self.online_label = Gtk.Label(label="● SYSTEM ONLINE")
        self.online_label.add_css_class("status-online")
        self.append(self.online_label)

        spacer = Gtk.Box(hexpand=True)
        self.append(spacer)

        # -- metric chips -----------------------------------------------------
        self.cpu_chip = self._make_chip("CPU 0%")
        self.ram_chip = self._make_chip("RAM 0%")
        self.batt_chip = self._make_chip("BATT --")
        self.wifi_chip = self._make_chip("WIFI --")
        for chip in (self.cpu_chip, self.ram_chip, self.batt_chip, self.wifi_chip):
            self.append(chip)

        self.clock_label = Gtk.Label(label="--:--:--")
        self.clock_label.add_css_class("clock-chip")
        self.append(self.clock_label)

        self._refresh_clock()
        self._refresh_metrics()
        GLib.timeout_add_seconds(1, self._refresh_clock)
        GLib.timeout_add_seconds(2, self._refresh_metrics)

    def _make_chip(self, text):
        chip = Gtk.Label(label=text)
        chip.add_css_class("metric-chip")
        return chip

    def set_online(self, online: bool):
        if online:
            self.online_label.set_label("● SYSTEM ONLINE")
            self.online_label.remove_css_class("error-text")
            self.online_label.add_css_class("status-online")
        else:
            self.online_label.set_label("● SYSTEM OFFLINE")
            self.online_label.remove_css_class("status-online")
            self.online_label.add_css_class("error-text")

    def _refresh_clock(self):
        self.clock_label.set_label(time.strftime("%H:%M:%S"))
        return True

    def _refresh_metrics(self):
        self.cpu_chip.set_label(f"CPU {sysmonitor.cpu_percent():.0f}%")
        self.ram_chip.set_label(f"RAM {sysmonitor.ram_percent():.0f}%")

        pct, plugged = sysmonitor.battery()
        if pct is None:
            self.batt_chip.set_label("BATT N/A")
        else:
            icon = "⚡" if plugged else ""
            self.batt_chip.set_label(f"BATT {pct}%{icon}")

        connected, _label = sysmonitor.wifi_status()
        self.wifi_chip.set_label("WIFI ON" if connected else "WIFI OFF")
        return True
