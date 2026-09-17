"""Voice/assistant state machine and the event record passed to the GUI."""

import time


class VoiceState(object):
    IDLE       = "idle"
    LISTENING  = "listening"
    PROCESSING = "processing"
    SPEAKING   = "speaking"
    ERROR      = "error"
    MUTED      = "muted"


STATE_TEXT = {
    VoiceState.IDLE:       "System ready, Boss.",
    VoiceState.LISTENING:  "Listening...",
    VoiceState.PROCESSING: "Processing...",
    VoiceState.SPEAKING:   "Speaking...",
    VoiceState.ERROR:      "Error - see activity log.",
    VoiceState.MUTED:      "Microphone paused.",
}


class Event(object):
    """One item in the activity feed.

    kind: 'user' | 'jarvis' | 'system' | 'arduino' | 'error' | 'state'
    """

    __slots__ = ("kind", "text", "ts")

    def __init__(self, kind, text):
        self.kind = kind
        self.text = text
        self.ts = time.time()

    def stamp(self):
        return time.strftime("%H:%M:%S", time.localtime(self.ts))

    def __repr__(self):
        return "<Event %s %r>" % (self.kind, self.text[:40])


class AppState(object):
    """Mutable snapshot the HUD reads. Written only from the GTK thread."""

    def __init__(self):
        self.voice = VoiceState.IDLE
        self.last_user = ""
        self.last_reply = ""
        self.status_line = STATE_TEXT[VoiceState.IDLE]
        self.devices = {
            "Arduino":    "Unknown",
            "Camera":     "Unknown",
            "Microphone": "Unknown",
            "Speaker":    "Unknown",
            "Gemini AI":  "Unknown",
        }

    def set_voice(self, state):
        self.voice = state
        self.status_line = STATE_TEXT.get(state, "")
