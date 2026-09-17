"""
sysmonitor.py
-------------
Thin wrapper around psutil for the top bar and right-hand status panel.
Every read here is cheap (psutil caches internally / non-blocking after
first call) so it's safe to poll every 1-2 seconds even on the N4120.

This module is standalone and does not import anything from the existing
JARVIS core - it only reports host machine stats for the GUI chrome.
"""

import shutil
import subprocess

import psutil

# Prime psutil's internal delta counter. The first call to cpu_percent()
# always returns 0.0 / a meaningless value; calling it once at import time
# means the first real poll from the GUI returns a sane number.
psutil.cpu_percent(interval=None)


def cpu_percent() -> float:
    return psutil.cpu_percent(interval=None)


def ram_percent() -> float:
    return psutil.virtual_memory().percent


def battery():
    """Returns (percent, plugged) or (None, None) if no battery is present."""
    try:
        batt = psutil.sensors_battery()
    except Exception:
        batt = None
    if batt is None:
        return None, None
    return round(batt.percent), batt.power_plugged


def cpu_temp_c():
    """Best-effort CPU temperature in Celsius, or None if unavailable."""
    try:
        temps = psutil.sensors_temperatures()
    except Exception:
        return None
    if not temps:
        return None
    for key in ("coretemp", "k10temp", "cpu_thermal", "acpitz"):
        if key in temps and temps[key]:
            return round(temps[key][0].current)
    # fall back to whatever the first sensor group reports
    for entries in temps.values():
        if entries:
            return round(entries[0].current)
    return None


def wifi_status():
    """
    Returns (connected: bool, label: str). Tries nmcli first (present on
    Zorin/Ubuntu by default), falls back to a basic interface-up check.
    """
    if shutil.which("nmcli"):
        try:
            out = subprocess.run(
                ["nmcli", "-t", "-f", "TYPE,STATE,CONNECTION", "device"],
                capture_output=True, text=True, timeout=1.5,
            )
            for line in out.stdout.strip().splitlines():
                parts = line.split(":")
                if len(parts) >= 3 and parts[0] == "wifi" and parts[1] == "connected":
                    return True, parts[2] or "CONNECTED"
            return False, "OFFLINE"
        except Exception:
            pass

    # Fallback: any interface whose name looks like wifi and is up
    try:
        stats = psutil.net_if_stats()
        for name, st in stats.items():
            if name.lower().startswith(("wl", "wifi")) and st.isup:
                return True, "CONNECTED"
    except Exception:
        pass
    return False, "UNKNOWN"


def executable_available(name: str) -> bool:
    return shutil.which(name) is not None
