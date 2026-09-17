"""
worker.py
---------
This is the ONLY place the GUI touches your existing JARVIS engine.
`listen()`, `speak()` and `process_command()` are imported unmodified from
your real modules and called exactly as main.py already calls them - just
from a background thread instead of a blocking `while True` in main().

All GTK-facing updates are marshalled back onto the main thread with
GLib.idle_add(), because GTK widgets must only be touched from the UI
thread. The rest of your codebase needs no changes at all.
"""

import threading
import time

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GObject, GLib

# --- existing JARVIS modules, imported as-is -------------------------------
from voice.listener import listen
from voice.speaker import speak
from core.commands import process_command

EXIT_WORDS = {"exit", "quit", "shutdown", "goodbye"}


class JarvisWorker(GObject.GObject):
    """
    Signals
    -------
    state-changed(str)   : idle | listening | processing | speaking | error | offline
    message(str, str)    : (speaker, text)  speaker is "YOU" or "JARVIS"
    error(str)           : human-readable error text
    """

    __gsignals__ = {
        "state-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "message": (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
        "error": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self):
        super().__init__()
        self._continuous = False
        self._stop = False
        self._busy_lock = threading.Lock()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    # Thread-safe signal emitters
    # ------------------------------------------------------------------
    def _emit_state(self, state):
        GLib.idle_add(self.emit, "state-changed", state)

    def _emit_message(self, who, text):
        GLib.idle_add(self.emit, "message", who, text)

    def _emit_error(self, text):
        GLib.idle_add(self.emit, "error", text)

    # ------------------------------------------------------------------
    # Public controls (called from the UI thread)
    # ------------------------------------------------------------------
    def set_continuous(self, enabled: bool):
        """Turn the always-listening loop on/off (mirrors main.py's while-loop)."""
        self._continuous = enabled
        if not enabled:
            self._emit_state("idle")

    def is_continuous(self) -> bool:
        return self._continuous

    def listen_once(self):
        """Push-to-talk: run a single listen -> process -> speak cycle."""
        threading.Thread(target=self._one_cycle, daemon=True).start()

    def send_text_command(self, text: str):
        """Bypass the microphone entirely - type a command straight into commands.py."""
        threading.Thread(target=self._handle_typed, args=(text,), daemon=True).start()

    def shutdown(self):
        self._stop = True
        self._continuous = False

    # ------------------------------------------------------------------
    # Internal worker logic
    # ------------------------------------------------------------------
    def _run_loop(self):
        """Background thread: mirrors main.py's while-loop, gated by self._continuous."""
        while not self._stop:
            if not self._continuous:
                time.sleep(0.15)
                continue
            self._one_cycle()

    def _one_cycle(self):
        if not self._busy_lock.acquire(blocking=False):
            return  # a cycle is already running (voice or typed) - don't overlap
        try:
            self._emit_state("listening")
            command = listen()

            if not command:
                self._emit_state("idle")
                return

            self._emit_message("YOU", command)

            if command.lower().strip() in EXIT_WORDS:
                farewell = "Shutting down. Goodbye."
                self._emit_state("speaking")
                speak(farewell)
                self._emit_message("JARVIS", farewell)
                self._continuous = False
                self._emit_state("offline")
                return

            self._emit_state("processing")
            response = process_command(command)
            self._emit_message("JARVIS", response)

            self._emit_state("speaking")
            speak(response)
            self._emit_state("idle")

        except Exception as exc:  # noqa: BLE001 - surface anything unexpected to the HUD
            self._emit_error(str(exc))
            self._emit_state("error")
            time.sleep(1.0)
            self._emit_state("idle")
        finally:
            self._busy_lock.release()

    def _handle_typed(self, text):
        if not self._busy_lock.acquire(blocking=False):
            return
        try:
            self._emit_message("YOU", text)
            self._emit_state("processing")
            response = process_command(text)
            self._emit_message("JARVIS", response)
            self._emit_state("speaking")
            speak(response)
            self._emit_state("idle")
        except Exception as exc:  # noqa: BLE001
            self._emit_error(str(exc))
            self._emit_state("error")
            time.sleep(1.0)
            self._emit_state("idle")
        finally:
            self._busy_lock.release()
