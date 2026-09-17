import datetime
import subprocess
import webbrowser


def handle_system(text):
    command = text.lower().strip()

    if "what time" in command or command == "time":
        return datetime.datetime.now().strftime(
            "The time is %I:%M %p."
        )

    if "what date" in command or command == "date":
        return datetime.datetime.now().strftime(
            "Today is %A, %d %B %Y."
        )

    if "open youtube" in command:
        webbrowser.open("https://www.youtube.com")
        return "Opening YouTube, Boss."

    if "open browser" in command or "open chrome" in command:
        subprocess.Popen(["google-chrome"])
        return "Opening the browser, Boss."

    return None
