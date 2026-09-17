import time
from voice.listener import listen
from voice.speaker import speak
from core.commands import process_command


EXIT_COMMANDS = {
    "exit",
    "quit",
    "shutdown",
    "goodbye",
}


def main():
    print("=" * 40)
    print("        JARVIS V4")
    print("=" * 40)

    speak("Jarvis V4 is online.")

    while True:
        command = listen(show_text=True)

        if not command:
            continue

        command_lower = command.lower().strip()

        if command_lower in EXIT_COMMANDS:
            speak("Shutting down, Boss.")
            break

        response = process_command(command)

        if response:
            speak(response)

if __name__ == "__main__":
    main()
