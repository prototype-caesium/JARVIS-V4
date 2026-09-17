from core.hardware_router import handle_hardware
from core.diagnostics import handle_diagnostics
from core.weather import handle_weather
from core.system_router import handle_system
from core.ai import ask_ai


EXIT_COMMANDS = {
    "exit",
    "quit",
    "goodbye",
    "shut down jarvis",
}


def normalize(command):
    command = command.lower().strip()

    for prefix in (
        "jarvis ",
        "hey jarvis ",
        "okay jarvis ",
        "ok jarvis ",
    ):
        if command.startswith(prefix):
            command = command[len(prefix):].strip()

    return command


def fast_local_command(command):
    """
    Handle extremely common local commands without Gemini.
    This keeps simple JARVIS operations nearly instant.
    """

    import datetime

    if (
        command == "time"
        or "what time is it" in command
        or "what's the time" in command
        or "tell me the time" in command
    ):
        return datetime.datetime.now().strftime(
            "The time is %I:%M %p."
        )

    if (
        command == "date"
        or "what date is it" in command
        or "what is today's date" in command
        or "what's today's date" in command
    ):
        return datetime.datetime.now().strftime(
            "Today is %A, %d %B %Y."
        )

    return None


def process_command(command):
    command = normalize(command)

    if not command:
        return ""

    if command in EXIT_COMMANDS:
        return "Goodbye, Boss."

    # ⚡ Instant local commands
    response = fast_local_command(command)

    if response:
        print("[JARVIS FAST] Local command")
        return response

    # Existing systems
    response = handle_hardware(command)
    if response:
        return response

    response = handle_diagnostics(command)
    if response:
        return response

    response = handle_weather(command)
    if response:
        return response

    response = handle_system(command)
    if response:
        return response

    # Everything else → Gemini
    return ask_ai(command)
