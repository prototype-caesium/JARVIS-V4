"""
camera_feed.py
---------------
Your existing `vision/camera.py::camera_test()` opens its own OpenCV window
and is left completely untouched - the Vision panel's "Open Test Window"
button still calls it exactly as before.

This module ADDS a lightweight embedded preview option so the GUI's Vision
panel can show a live thumbnail without a second window. It reuses
CAMERA_INDEX from your existing vision/camera.py so both stay in sync, but
manages its own VideoCapture handle and thread - it never calls into
camera_test() itself (that function blocks and owns its own cv2 window).
"""

import threading
import time

import cv2
import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, GLib

from vision.camera import CAMERA_INDEX

PREVIEW_WIDTH = 320
PREVIEW_FPS_INTERVAL = 1.0 / 12.0  # 12 fps preview is plenty and stays cheap


class CameraFeed:
    """Runs a low-fps capture loop on a background thread and hands GdkPixbuf
    frames back to the caller's on_frame callback via GLib.idle_add."""

    def __init__(self, on_frame, on_error=None):
        self._on_frame = on_frame
        self._on_error = on_error
        self._cap = None
        self._thread = None
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _run(self):
        try:
            self._cap = cv2.VideoCapture(CAMERA_INDEX)
            if not self._cap.isOpened():
                if self._on_error:
                    GLib.idle_add(self._on_error, "Camera could not be opened.")
                self._running = False
                return

            while self._running:
                ok, frame = self._cap.read()
                if not ok:
                    time.sleep(0.2)
                    continue

                pixbuf = self._frame_to_pixbuf(frame)
                if pixbuf is not None:
                    GLib.idle_add(self._on_frame, pixbuf)

                time.sleep(PREVIEW_FPS_INTERVAL)
        except Exception as exc:  # noqa: BLE001
            if self._on_error:
                GLib.idle_add(self._on_error, str(exc))
        finally:
            if self._cap is not None:
                self._cap.release()
            self._running = False

    @staticmethod
    def _frame_to_pixbuf(frame):
        h, w = frame.shape[:2]
        scale = PREVIEW_WIDTH / w
        new_w, new_h = PREVIEW_WIDTH, int(h * scale)
        small = cv2.resize(frame, (new_w, new_h))
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        return GdkPixbuf.Pixbuf.new_from_data(
            rgb.tobytes(), GdkPixbuf.Colorspace.RGB, False, 8,
            new_w, new_h, new_w * 3, None, None,
        )
