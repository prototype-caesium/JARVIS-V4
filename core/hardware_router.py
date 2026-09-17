from core.hardware_ai import parse_hardware_command
from hardware.arduino import send


ALLOWED_TARGETS = {"1", "2", "3", "all"}
ALLOWED_STATES = {"on", "off"}


def handle_hardware(text):
    result = parse_hardware_command(text)

    if not isinstance(result, dict):
        return None

    if result.get("action") != "led":
        return None

    target = str(result.get("target", "")).lower()
    state = str(result.get("state", "")).lower()

    # Strict local validation
    if target not in ALLOWED_TARGETS:
        print("⚠️ Invalid hardware target rejected.")
        return None

    if state not in ALLOWED_STATES:
        print("⚠️ Invalid hardware state rejected.")
        return None

    if target == "all":
        command = f"all {state}"
        spoken = f"All LEDs turned {state}, Boss."

    else:
        command = f"led {target} {state}"
        spoken = f"LED {target} turned {state}, Boss."

    if send(command):
        return spoken

    return "Arduino is not connected, Boss."
