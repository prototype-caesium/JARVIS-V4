"""Adapter between the HUD and the existing JARVIS V4 modules.

Design rules:
  * Never instantiate a hardware class - that risks a second serial handle.
  * Never report success we did not observe.
  * Exactly one listener thread, daemonised, with a cooperative stop flag.
"""

from __future__ import annotations

import importlib
import inspect
import os
import shutil
import subprocess
import threading
import time
import traceback

from gui.voice_state import Event, VoiceState

# ----------------------------------------------------------- name tables
ROUTER_NAMES = ("handle_command", "process_command", "run_command",
                "execute_command", "handle", "process", "execute",
                "dispatch", "route", "respond", "get_response")
ROUTER_CLASSES = ("CommandRouter", "Commands", "CommandHandler", "Router")

SPEAK_NAMES = ("speak", "say", "talk", "speak_text", "tts")
SPEAK_CLASSES = ("Speaker", "VoiceSpeaker", "TTS", "TextToSpeech")

LISTEN_ONESHOT = ("listen_once", "listen", "take_command", "get_command",
                  "recognize", "recognize_speech", "hear", "capture")
LISTEN_LOOP = ("start_listening", "listen_loop", "listen_forever", "run_loop")
LISTEN_CLASSES = ("Listener", "VoiceListener", "Recognizer", "SpeechListener")

ARDUINO_INSTANCES = ("arduino", "ARDUINO", "board", "controller",
                     "device", "conn", "connection")
ARDUINO_CLASS_NAMES = ("Arduino", "ArduinoController", "ArduinoBoard",
                       "Board", "ArduinoSerial")

WAKE_PREFIXES = ()

EXIT_COMMANDS = {
    "exit",
    "quit",
    "shutdown",
    "shut down",
    "goodbye",
}


# ----------------------------------------------------------- discovery
def _import(name):
    try:
        return importlib.import_module(name), None
    except Exception as exc:
        return None, "%s: %s" % (type(exc).__name__, exc)


def _bind(mod, func_names, class_names, allow_construct=True):
    """Find a callable on a module, on a module-level instance, or on a
    freshly constructed class. Returns (callable_or_None, description)."""
    if mod is None:
        return None, "module unavailable"

    for name in func_names:
        fn = getattr(mod, name, None)
        if callable(fn) and not inspect.isclass(fn):
            return fn, "%s.%s()" % (mod.__name__, name)

    for attr in dir(mod):
        if attr.startswith("_"):
            continue
        obj = getattr(mod, attr, None)
        if obj is None or inspect.isclass(obj) or inspect.ismodule(obj):
            continue
        if callable(obj):
            continue
        for name in func_names:
            meth = getattr(obj, name, None)
            if callable(meth):
                return meth, "%s.%s.%s()" % (mod.__name__, attr, name)

    if allow_construct:
        for cname in class_names:
            cls = getattr(mod, cname, None)
            if not inspect.isclass(cls):
                continue
            try:
                inst = cls()
            except Exception:
                continue
            for name in func_names:
                meth = getattr(inst, name, None)
                if callable(meth):
                    return meth, "%s.%s().%s()" % (mod.__name__, cname, name)

    return None, "no matching entry point in %s" % mod.__name__


def _arity(fn):
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return 1

    n = 0
    for p in sig.parameters.values():
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD):
            if p.default is p.empty:
                n += 1
        elif p.kind == p.VAR_POSITIONAL:
            return 1

    return n


# ----------------------------------------------------------- quick cmds
def _first_present(candidates):
    for argv in candidates:
        if shutil.which(argv[0]):
            return argv
    return None


QUICK_COMMANDS = [
    ("Open Apps", "open apps", None),
    ("Lock Computer", "lock computer", [["loginctl", "lock-session"],
                                        ["gnome-screensaver-command", "-l"],
                                        ["xdg-screensaver", "lock"]]),
    ("System Settings", "open system settings", [["gnome-control-center"]]),
    ("Play Music", "play music", [["playerctl", "play-pause"]]),
    ("Take Screenshot", "take screenshot", "SCREENSHOT"),
    ("Control Arduino", "arduino status", "ARDUINO_STATUS"),
    ("Face Unlock", "face unlock", None),
]


class AssistantBridge(object):

    def __init__(self, emit):
        """emit(Event) is called from worker threads; the GUI must marshal."""
        self._emit_raw = emit
        self._stop = threading.Event()
        self._enabled = threading.Event()
        self._enabled.set()
        self._thread = None
        self._router_lock = threading.Lock()
        self._state_cb = None
        self._shutdown_cb = None

        self.ai_status = "Unknown"
        self.listen_mode = "none"

        self._discover()

    # ------------------------------------------------------ plumbing
    def emit(self, kind, text):
        try:
            self._emit_raw(Event(kind, text))
        except Exception:
            pass

    def set_state_callback(self, cb):
        self._state_cb = cb

    def set_shutdown_callback(self, cb):
        self._shutdown_cb = cb

    def _state(self, state):
        if self._state_cb:
            try:
                self._state_cb(state)
            except Exception:
                pass

    # ------------------------------------------------------ discovery
    def _discover(self):
        self.mod_cmd, err_cmd = _import("core.commands")
        self.mod_spk, err_spk = _import("voice.speaker")
        self.mod_lis, err_lis = _import("voice.listener")
        self.mod_ard, err_ard = _import("hardware.arduino")

        for label, err in (("core.commands", err_cmd),
                           ("voice.speaker", err_spk),
                           ("voice.listener", err_lis),
                           ("hardware.arduino", err_ard)):
            if err:
                self.emit("error", "import %s failed - %s" % (label, err))

        self.router, self.router_desc = _bind(
            self.mod_cmd, ROUTER_NAMES, ROUTER_CLASSES
        )

        self.speak_fn, self.speak_desc = _bind(
            self.mod_spk, SPEAK_NAMES, SPEAK_CLASSES
        )

        self.listen_fn, self.listen_desc = _bind(
            self.mod_lis, LISTEN_ONESHOT, LISTEN_CLASSES
        )

        if self.listen_fn is not None:
            self.listen_mode = "oneshot"
        else:
            self.listen_fn, self.listen_desc = _bind(
                self.mod_lis, LISTEN_LOOP, LISTEN_CLASSES
            )
            if self.listen_fn is not None:
                self.listen_mode = "loop"

        self._ard_obj = self._find_arduino()

        try:
            if self.mod_ard and hasattr(self.mod_ard, "connect"):
                self.mod_ard.connect()
        except Exception as exc:
            self.emit("error", "Arduino connection: %s" % exc)

        self.emit("system", "router   : %s" % self.router_desc)
        self.emit("system", "speaker  : %s" % self.speak_desc)
        self.emit("system", "listener : %s [%s]" %
                  (self.listen_desc, self.listen_mode))
        self.emit(
            "system",
            "arduino  : %s" %
            ("module object bound"
             if self._ard_obj is not None else "not bound")
        )

        # Key presence only - never the value.
        self.ai_status = (
            "Ready" if os.environ.get("GROQ_API_KEY") else "Offline"
        )

        if self.ai_status == "Offline":
            self.emit("error", "GROQ_API_KEY not set in this environment")

    def _find_arduino(self):
        mod = self.mod_ard

        if mod is None:
            return None

        for name in ARDUINO_INSTANCES:
            obj = getattr(mod, name, None)

            if obj is None:
                continue

            if inspect.isclass(obj) or inspect.ismodule(obj) or callable(obj):
                continue

            return obj

        for attr in dir(mod):
            if attr.startswith("_"):
                continue

            obj = getattr(mod, attr, None)

            if obj is None or inspect.isclass(obj) or inspect.ismodule(obj):
                continue

            if callable(obj):
                continue

            if type(obj).__name__ in ARDUINO_CLASS_NAMES:
                return obj

        return mod

    # ------------------------------------------------------ status
    def arduino_status(self):
        obj = self._ard_obj

        if obj is None:
            return "Offline"

        try:
            for name in (
                "is_connected",
                "connected",
                "is_open",
                "is_available",
            ):
                attr = getattr(obj, name, None)

                if attr is None:
                    continue

                val = attr() if callable(attr) else attr

                return "Connected" if bool(val) else "Offline"

            for name in ("status", "get_status", "state"):
                attr = getattr(obj, name, None)

                if attr is None:
                    continue

                val = attr() if callable(attr) else attr

                if isinstance(val, bool):
                    return "Connected" if val else "Offline"

                return str(val)

            ser = getattr(obj, "ser", None)

            if ser is None:
                ser = getattr(obj, "serial", None)

            if ser is not None and not inspect.ismodule(ser):
                return (
                    "Connected"
                    if getattr(ser, "is_open", False)
                    else "Offline"
                )

        except Exception as exc:
            self.emit("error", "arduino status: %s" % exc)
            return "Error"

        return "Unknown"

    def speaker_status(self):
        return "Ready" if self.speak_fn else "Offline"

    def listener_status(self):
        return "Ready" if self.listen_fn else "Offline"

    # ------------------------------------------------------ pipeline
    def handle_text(self, text, origin="voice"):
        """Run one utterance through the real command system."""
        if not text:
            return

        text = str(text).strip()

        if not text:
            return

        if WAKE_PREFIXES and origin == "voice":
            low = text.lower()

            if not any(low.startswith(w) for w in WAKE_PREFIXES):
                return

        self.emit("user", text)
        self._state(VoiceState.PROCESSING)

        if self.router is None:
            self.emit(
                "error",
                "command router unavailable - %s" % self.router_desc
            )
            self._state(VoiceState.ERROR)
            return

        reply = None

        try:
            with self._router_lock:
                reply = self.router(text)

        except Exception as exc:
            tb = traceback.format_exc().strip().splitlines()[-1]

            self.emit("error", "command failed: %s" % tb)

            low = ("%s %s" % (type(exc).__name__, exc)).lower()

            if "gemini" in low or "api" in low or "quota" in low:
                self.ai_status = "Error"

            self._state(VoiceState.ERROR)
            return

        if reply is None:
            self.emit("system", "command returned no response")
            self._state(VoiceState.IDLE)
            return

        reply = str(reply).strip()

        if not reply:
            self._state(VoiceState.IDLE)
            return

        if self.ai_status == "Error":
            self.ai_status = "Ready"

        self.emit("jarvis", reply)
        self.emit("arduino", self.arduino_status())

        if self.speak_fn is not None:
            self._state(VoiceState.SPEAKING)

            try:
                # IMPORTANT:
                # This blocks until Piper finishes speaking.
                self.speak_fn(reply)

            except Exception as exc:
                self.emit("error", "speaker failed: %s" % exc)

        # --------------------------------------------------------
        # GUI shutdown AFTER the spoken response has finished.
        # Only exact exit commands trigger this.
        # --------------------------------------------------------
        if text.lower().strip() in EXIT_COMMANDS:
            if self._shutdown_cb is not None:
                try:
                    self._shutdown_cb()
                except Exception as exc:
                    self.emit("error", "shutdown callback failed: %s" % exc)

            return

        self._state(VoiceState.IDLE)

    # ------------------------------------------------------ threads
    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return

        if self.listen_fn is None:
            self.emit(
                "error",
                "no voice listener bound - GUI runs without mic"
            )
            return

        self._stop.clear()

        target = (
            self._loop_oneshot
            if self.listen_mode == "oneshot"
            else self._loop_callback
        )

        self._thread = threading.Thread(
            target=target,
            name="jarvis-listener",
            daemon=True
        )

        self._thread.start()
        self.emit("system", "listener thread started")

    def _loop_oneshot(self):
        while not self._stop.is_set():

            if not self._enabled.is_set():
                self._stop.wait(0.3)
                continue

            self._state(VoiceState.LISTENING)

            try:
                text = self.listen_fn()

            except Exception as exc:
                self.emit("error", "listener: %s" % exc)
                self._state(VoiceState.ERROR)
                self._stop.wait(2.0)
                continue

            if self._stop.is_set():
                break

            if text:
                self.handle_text(text)
            else:
                self._state(VoiceState.IDLE)
                self._stop.wait(0.15)

    def _loop_callback(self):
        self._state(VoiceState.LISTENING)

        try:
            if _arity(self.listen_fn) >= 1:
                self.listen_fn(self._callback_sink)
            else:
                self.emit(
                    "error",
                    "loop listener takes no callback; cannot route speech"
                )

        except Exception as exc:
            self.emit("error", "listener loop: %s" % exc)
            self._state(VoiceState.ERROR)

    def _callback_sink(self, text, *_args, **_kw):
        if self._stop.is_set() or not self._enabled.is_set():
            return

        self.handle_text(text)
        self._state(VoiceState.LISTENING)

    def set_enabled(self, on):
        if on:
            self._enabled.set()
        else:
            self._enabled.clear()

    def is_enabled(self):
        return self._enabled.is_set()

    def stop(self):
        self._stop.set()
        self._enabled.clear()

    # ------------------------------------------------------ quick cmds
    def run_quick(self, label):
        threading.Thread(
            target=self._run_quick,
            args=(label,),
            name="jarvis-quick",
            daemon=True
        ).start()

    def _run_quick(self, label):
        spec = None

        for item in QUICK_COMMANDS:
            if item[0] == label:
                spec = item
                break

        if spec is None:
            self.emit("error", "unknown quick command %r" % label)
            return

        _, phrase, fallback = spec

        self.emit("user", "[button] %s" % label)

        if self.router is not None:
            try:
                with self._router_lock:
                    reply = self.router(phrase)

            except Exception as exc:
                self.emit(
                    "error",
                    "%s via router failed: %s" % (label, exc)
                )
                reply = None

            if reply:
                self.emit("jarvis", str(reply).strip())
                self.emit("arduino", self.arduino_status())
                return

        if fallback == "ARDUINO_STATUS":
            self.emit("arduino", self.arduino_status())
            return

        if fallback == "SCREENSHOT":
            path = os.path.expanduser(
                "~/Pictures/jarvis-%s.png"
                % time.strftime("%Y%m%d-%H%M%S")
            )

            argv = _first_present([
                ["gnome-screenshot", "-f", path],
                ["spectacle", "-b", "-n", "-o", path],
                ["import", "-window", "root", path],
            ])

            if argv is None:
                self.emit(
                    "error",
                    "no screenshot tool found "
                    "(install gnome-screenshot)"
                )
                return

            self._spawn(argv, "screenshot saved to %s" % path)
            return

        if fallback is None:
            self.emit(
                "error",
                "%s: no handler in core/commands.py and "
                "no local fallback" % label
            )
            return

        argv = _first_present(fallback)

        if argv is None:
            names = ", ".join(c[0] for c in fallback)
            self.emit(
                "error",
                "%s: none of [%s] installed" % (label, names)
            )
            return

        self._spawn(argv, "%s -> %s" % (label, argv[0]))

    def _spawn(self, argv, ok_msg):
        try:
            proc = subprocess.run(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=20
            )

        except FileNotFoundError:
            self.emit("error", "%s not found" % argv[0])
            return

        except subprocess.TimeoutExpired:
            self.emit("error", "%s timed out" % argv[0])
            return

        except Exception as exc:
            self.emit("error", "%s: %s" % (argv[0], exc))
            return

        if proc.returncode == 0:
            self.emit("system", ok_msg)

        else:
            err = (
                (proc.stderr or b"")
                .decode("utf-8", "replace")
                .strip()
            )

            self.emit(
                "error",
                "%s exited %d %s"
                % (argv[0], proc.returncode, err[:120])
            )
