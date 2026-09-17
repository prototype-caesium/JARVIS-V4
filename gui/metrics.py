"""System metrics.

Deliberately subprocess-free: everything comes from psutil, /proc or /sys,
so polling costs microseconds on a Celeron N4120.
"""

import glob
import os
import time

try:
    import psutil
except Exception:  # pragma: no cover
    psutil = None


class SystemMetrics(object):

    def __init__(self):
        self._disk_cache = None
        self._disk_at = 0.0
        self._temp_ok = bool(psutil and hasattr(psutil, "sensors_temperatures"))
        if psutil:
            try:
                psutil.cpu_percent(interval=None)  # prime the counter
            except Exception:
                pass

    # ---------------------------------------------------------- core
    def cpu(self):
        if not psutil:
            return None
        try:
            return psutil.cpu_percent(interval=None)
        except Exception:
            return None

    def memory(self):
        """-> (percent, used_gb, total_gb) or None"""
        if not psutil:
            return None
        try:
            m = psutil.virtual_memory()
            return (m.percent, m.used / 1073741824.0, m.total / 1073741824.0)
        except Exception:
            return None

    def disk(self):
        """-> (percent, used_gb, total_gb) or None. Cached 30s."""
        now = time.time()
        if self._disk_cache is not None and now - self._disk_at < 30.0:
            return self._disk_cache
        if not psutil:
            return None
        try:
            d = psutil.disk_usage("/")
            self._disk_cache = (d.percent,
                                d.used / 1073741824.0,
                                d.total / 1073741824.0)
            self._disk_at = now
            return self._disk_cache
        except Exception:
            return None

    def temperature(self):
        """-> celsius float or None"""
        if not self._temp_ok:
            return None
        try:
            temps = psutil.sensors_temperatures()
        except Exception:
            return None
        if not temps:
            return None
        for key in ("coretemp", "acpitz", "k10temp", "cpu_thermal", "pch_cannonlake"):
            entries = temps.get(key)
            if entries:
                for e in entries:
                    if e.current:
                        return float(e.current)
        for entries in temps.values():
            for e in entries:
                if e.current:
                    return float(e.current)
        return None

    def battery(self):
        """-> (percent, plugged_bool) or None"""
        if not psutil or not hasattr(psutil, "sensors_battery"):
            return None
        try:
            b = psutil.sensors_battery()
        except Exception:
            return None
        if b is None:
            return None
        return (int(round(b.percent)), bool(b.power_plugged))

    # ---------------------------------------------------------- links
    @staticmethod
    def _operstate(iface):
        try:
            with open("/sys/class/net/%s/operstate" % iface) as fh:
                return fh.read().strip()
        except Exception:
            return "unknown"

    def wifi(self):
        """-> (iface, quality_pct, up_bool) or None if no wireless iface."""
        try:
            with open("/proc/net/wireless") as fh:
                lines = fh.readlines()[2:]
        except Exception:
            return None
        for line in lines:
            if ":" not in line:
                continue
            name = line.split(":", 1)[0].strip()
            parts = line.split(":", 1)[1].split()
            try:
                link = float(parts[1].rstrip("."))
            except (IndexError, ValueError):
                link = 0.0
            quality = int(max(0.0, min(100.0, link / 70.0 * 100.0)))
            return (name, quality, self._operstate(name) == "up")
        return None

    def bluetooth(self):
        """-> 'On' | 'Off' | 'Blocked' | 'Unavailable'"""
        adapters = glob.glob("/sys/class/bluetooth/hci*")
        if not adapters:
            return "Unavailable"
        for rf in glob.glob("/sys/class/rfkill/rfkill*"):
            try:
                with open(os.path.join(rf, "type")) as fh:
                    if fh.read().strip() != "bluetooth":
                        continue
                with open(os.path.join(rf, "soft")) as fh:
                    if fh.read().strip() == "1":
                        return "Blocked"
            except Exception:
                continue
        return "On"

    def audio(self):
        """-> 'Ready' | 'Offline'"""
        return "Ready" if glob.glob("/dev/snd/controlC*") else "Offline"

    def mic_present(self):
        return bool(glob.glob("/dev/snd/pcmC*D*c"))

    def camera_present(self):
        return bool(glob.glob("/dev/video*"))

    def network(self):
        """-> 'Link up' | 'Offline'"""
        try:
            for iface in os.listdir("/sys/class/net"):
                if iface == "lo":
                    continue
                if self._operstate(iface) == "up":
                    return "Link up"
        except Exception:
            pass
        return "Offline"
