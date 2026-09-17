import shutil

import psutil


def get_cpu():
    return round(float(psutil.cpu_percent(interval=0.15)))


def get_memory():
    mem = psutil.virtual_memory()

    return {
        "used_gb": mem.used / (1024 ** 3),
        "total_gb": mem.total / (1024 ** 3),
        "percent": round(mem.percent),
    }


def get_disk():
    disk = shutil.disk_usage("/")

    used = disk.used / (1024 ** 3)
    total = disk.total / (1024 ** 3)
    percent = (disk.used / disk.total) * 100

    return {
        "used_gb": used,
        "total_gb": total,
        "percent": round(percent),
    }


def get_battery():
    battery = psutil.sensors_battery()

    if battery is None:
        return None

    return {
        "percent": round(battery.percent),
        "plugged": battery.power_plugged,
    }


def system_report():
    cpu = get_cpu()
    memory = get_memory()
    disk = get_disk()
    battery = get_battery()

    response = (
        f"System check complete. "
        f"CPU is at {cpu} percent. "
        f"RAM usage is {memory['used_gb']:.1f} "
        f"of {memory['total_gb']:.1f} gigabytes. "
        f"Storage is {disk['percent']} percent used."
    )

    if battery:
        state = "charging" if battery["plugged"] else "on battery"

        response += (
            f" Battery is at {battery['percent']} percent, "
            f"{state}."
        )

    return response


def handle_diagnostics(text):
    command = text.lower().strip()

    # Full system diagnosis
    diagnosis_words = (
        "check my computer",
        "check my system",
        "diagnose my computer",
        "diagnose my system",
        "system check",
        "computer check",
        "computer health",
        "how is my computer",
        "how's my computer",
        "how is my system",
        "how's my system",
        "what's wrong with my computer",
        "what is wrong with my computer",
    )

    if any(phrase in command for phrase in diagnosis_words):
        return system_report()

    # CPU
    if (
        "cpu usage" in command
        or "processor usage" in command
        or "how much cpu" in command
    ):
        return f"CPU usage is {get_cpu()} percent, Boss."

    # RAM
    if (
        "ram usage" in command
        or "memory usage" in command
        or "how much ram" in command
        or "how much memory" in command
    ):
        memory = get_memory()

        return (
            f"RAM usage is {memory['used_gb']:.1f} "
            f"of {memory['total_gb']:.1f} gigabytes, "
            f"which is {memory['percent']} percent."
        )

    # Storage
    if (
        "storage" in command
        or "disk usage" in command
        or "disk space" in command
        or "hard drive space" in command
    ):
        disk = get_disk()

        return (
            f"Storage is {disk['percent']} percent used. "
            f"You are using {disk['used_gb']:.1f} "
            f"of {disk['total_gb']:.1f} gigabytes."
        )

    # Battery
    if "battery" in command:
        battery = get_battery()

        if battery is None:
            return "I cannot detect a battery on this system, Boss."

        state = "charging" if battery["plugged"] else "on battery"

        return (
            f"Battery is at {battery['percent']} percent "
            f"and the system is {state}."
        )

    return None
