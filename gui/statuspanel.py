"""
statuspanel.py
---------------
Right-hand live status column: CPU / RAM / BATTERY / TEMPERATURE / MIC /
SPEAKER / CAMERA / ARDUINO, each with a small colored state dot.

Hardware presence checks (mic device list, piper+aplay binaries) are cheap
and done once at startup plus on a slow timer; CPU/RAM/temp refresh every
2s via gui.sysmonitor.
"""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

from gui import sysmonitor


class StatusRow(Gtk.Box):
    def __init__(self, name):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.add_css_class("status-row")

        self.dot = Gtk.Label(label="●")
        self.dot.add_css_class("dot-off")
        self.append(self.dot)

        name_label = Gtk.Label(label=name)
        name_label.add_css_class("status-name")
        name_label.set_xalign(0)
        name_label.set_hexpand(True)
        self.append(name_label)

        self.value = Gtk.Label(label="--")
        self.value.add_css_class("status-value")
        self.append(self.value)

    def update(self, value_text, level="ok"):
        self.value.set_label(value_text)
        for cls in ("dot-ok", "dot-warn", "dot-error", "dot-off"):
            self.dot.remove_css_class(cls)
        self.dot.add_css_class(f"dot-{level}")


class StatusPanel(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.add_css_class("statuspanel")
        self.set_size_request(230, -1)

        title = Gtk.Label(label="SYSTEM STATUS")
        title.add_css_class("panel-title")
        title.set_xalign(0)
        self.append(title)
        self.append(Gtk.Box(height_request=6))

        self.rows = {}
        for key in ("CPU", "RAM", "BATTERY", "TEMPERATURE", "MIC", "SPEAKER", "CAMERA", "ARDUINO"):
            row = StatusRow(key)
            self.rows[key] = row
            self.append(row)

        # externally-driven rows (updated by app.py when the worker reports
        # state or when the arduino/vision panels connect/disconnect)
        self.rows["ARDUINO"].update("STANDBY", "off")
        self.rows["CAMERA"].update("STANDBY", "off")

        self._probe_static_devices()
        self._refresh()
        GLib.timeout_add_seconds(2, self._refresh)

    def _probe_static_devices(self):
        # Mic: does sounddevice/PortAudio see any input device at all?
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            has_input = any(d.get("max_input_channels", 0) > 0 for d in devices)
            self.rows["MIC"].update("READY" if has_input else "NOT FOUND",
                                     "ok" if has_input else "error")
        except Exception:
            self.rows["MIC"].update("UNKNOWN", "warn")

        # Speaker: Groq Orpheus TTS + aplay
        groq_ok = sysmonitor.executable_available("aplay")

        try:
            import os
            from voice import speaker  # noqa: F401
            groq_ok = groq_ok and bool(os.environ.get("GROQ_API_KEY"))
        except Exception:
            groq_ok = False

        self.rows["SPEAKER"].update(
            "READY" if groq_ok else "CHECK GROQ TTS",
            "ok" if groq_ok else "warn"
        )

    def set_arduino_status(self, connected: bool):
        self.rows["ARDUINO"].update("CONNECTED" if connected else "DISCONNECTED",
                                     "ok" if connected else "off")

    def set_camera_status(self, active: bool):
        self.rows["CAMERA"].update("STREAMING" if active else "STANDBY",
                                    "ok" if active else "off")

    def _refresh(self):
        cpu = sysmonitor.cpu_percent()
        self.rows["CPU"].update(f"{cpu:.0f}%", "warn" if cpu > 85 else "ok")

        ram = sysmonitor.ram_percent()
        self.rows["RAM"].update(f"{ram:.0f}%", "warn" if ram > 85 else "ok")

        pct, plugged = sysmonitor.battery()
        if pct is None:
            self.rows["BATTERY"].update("N/A", "off")
        else:
            level = "ok" if (plugged or pct > 25) else "warn"
            self.rows["BATTERY"].update(f"{pct}%", level)

        temp = sysmonitor.cpu_temp_c()
        if temp is None:
            self.rows["TEMPERATURE"].update("N/A", "off")
        else:
            level = "error" if temp >= 85 else ("warn" if temp >= 70 else "ok")
            self.rows["TEMPERATURE"].update(f"{temp}°C", level)

        return True
