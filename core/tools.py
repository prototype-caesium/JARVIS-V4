import datetime
import webbrowser
import threading

from core.diagnostics import (
    get_cpu,
    get_memory,
    get_disk,
    get_battery,
)

from hardware import arduino


def get_time():
    return datetime.datetime.now().strftime("%I:%M %p")


def get_date():
    return datetime.datetime.now().strftime("%A, %d %B %Y")


def get_system_status():
    cpu = get_cpu()
    memory = get_memory()
    disk = get_disk()
    battery = get_battery()

    result = {
        "cpu_percent": cpu,
        "ram_used_gb": round(memory["used_gb"], 1),
        "ram_total_gb": round(memory["total_gb"], 1),
        "ram_percent": memory["percent"],
        "storage_used_gb": round(disk["used_gb"], 1),
        "storage_total_gb": round(disk["total_gb"], 1),
        "storage_percent": disk["percent"],
    }

    if battery:
        result["battery_percent"] = battery["percent"]
        result["charging"] = battery["plugged"]
    else:
        result["battery_percent"] = None
        result["charging"] = None

    return result


def open_website(url):
    webbrowser.open(url)
    return {
        "success": True,
        "url": url,
    }


# =========================
# JARVIS LIGHT CONTROL
# =========================

def _ensure_arduino():
    """Make sure the Arduino serial connection exists."""
    if arduino.arduino is None or not arduino.arduino.is_open:
        return arduino.connect()
    return True


def turn_on_lights():
    """Turn the Arduino LED/lights on."""
    if not _ensure_arduino():
        return {
            "success": False,
            "message": "Arduino is not connected."
        }

    success = arduino.send("LIGHT_ON")

    return {
        "success": success,
        "action": "lights_on"
    }


def turn_off_lights():
    """Turn the Arduino LED/lights off."""
    if not _ensure_arduino():
        return {
            "success": False,
            "message": "Arduino is not connected."
        }

    success = arduino.send("LIGHT_OFF")

    return {
        "success": success,
        "action": "lights_off"
    }


def turn_on_lights_after(seconds):
    """Turn the lights on after a delay."""
    seconds = max(0, float(seconds))

    timer = threading.Timer(seconds, turn_on_lights)
    timer.daemon = False
    timer.start()

    return {
        "success": True,
        "action": "lights_on",
        "delay_seconds": seconds
    }


def turn_off_lights_after(seconds):
    """Turn the lights off after a delay."""
    seconds = max(0, float(seconds))

    timer = threading.Timer(seconds, turn_off_lights)
    timer.daemon = False
    timer.start()

    return {
        "success": True,
        "action": "lights_off",
        "delay_seconds": seconds
    }


TOOLS = {
    "get_time": get_time,
    "get_date": get_date,
    "get_system_status": get_system_status,
    "open_website": open_website,

    "turn_on_lights": turn_on_lights,
    "turn_off_lights": turn_off_lights,
    "turn_on_lights_after": turn_on_lights_after,
    "turn_off_lights_after": turn_off_lights_after,
}
