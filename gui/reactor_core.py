"""
reactor_core.py
----------------
An ORIGINAL geometric "AI core" widget drawn entirely with Cairo vector
primitives (arcs, lines, dashed strokes). No bitmap assets, no 3D, no
external icon/font dependency - this keeps it cheap enough to redraw at
~20 FPS on an Intel Celeron N4120.

This is a self-contained Gtk.DrawingArea. It knows nothing about JARVIS'
voice/AI code - the app wires it up by calling `core.set_state(name)`
where name is one of: idle, listening, processing, speaking, error, offline.
"""

import math
import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

from gui.theme import CORE_STATES, rgba

FRAME_INTERVAL_MS = 42  # ~24 FPS - smooth enough, light enough for low-end CPUs


class ReactorCore(Gtk.DrawingArea):
    __gtype_name__ = "ReactorCore"

    def __init__(self):
        super().__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_content_width(340)
        self.set_content_height(340)

        self._state = "idle"
        self._t = 0.0
        self._pulse_energy = 0.0  # extra kick for speaking/processing bursts

        self.set_draw_func(self._on_draw, None)
        GLib.timeout_add(FRAME_INTERVAL_MS, self._tick)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_state(self, state: str):
        if state not in CORE_STATES:
            state = "idle"
        if state != self._state:
            self._state = state
            self._pulse_energy = 1.0

    def get_state(self) -> str:
        return self._state

    # ------------------------------------------------------------------
    # Animation clock
    # ------------------------------------------------------------------
    def _tick(self):
        cfg = CORE_STATES[self._state]
        self._t += cfg["speed"]
        if self._pulse_energy > 0:
            self._pulse_energy = max(0.0, self._pulse_energy - 0.04)
        self.queue_draw()
        return True  # keep the timeout alive

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def _on_draw(self, area, cr, width, height, data):
        cfg = CORE_STATES[self._state]
        cx, cy = width / 2.0, height / 2.0
        r = min(width, height) * 0.44
        t = self._t

        ring_c = cfg["color"]
        glow_c = cfg["glow"]

        cr.save()
        cr.translate(cx, cy)

        self._draw_outer_dial(cr, r, ring_c, t)
        self._draw_segmented_rings(cr, r, ring_c, glow_c, t)
        self._draw_diagnostic_ticks(cr, r, ring_c)
        self._draw_particles(cr, r, glow_c, t)
        self._draw_core(cr, r, ring_c, glow_c, t)
        self._draw_readout(cr, r, ring_c)

        cr.restore()

    # -- outer dial: thin ring with alternating tick marks --------------
    def _draw_outer_dial(self, cr, r, color, t):
        radius = r * 1.18
        cr.set_line_width(1.0)
        cr.set_source_rgba(*rgba(color, 0.35))
        cr.arc(0, 0, radius, 0, 2 * math.pi)
        cr.stroke()

        ticks = 72
        for i in range(ticks):
            angle = (2 * math.pi / ticks) * i + t * 0.3
            major = (i % 6 == 0)
            inner = radius - (10 if major else 5)
            outer = radius
            alpha = 0.85 if major else 0.3
            cr.set_source_rgba(*rgba(color, alpha))
            cr.set_line_width(1.4 if major else 0.8)
            cr.move_to(inner * math.cos(angle), inner * math.sin(angle))
            cr.line_to(outer * math.cos(angle), outer * math.sin(angle))
            cr.stroke()

    # -- concentric rotating rings with dashed segments ------------------
    def _draw_segmented_rings(self, cr, r, color, glow, t):
        ring_defs = [
            (r * 1.0, 10, t * 1.0, 0.9),
            (r * 0.82, 14, -t * 1.6, 0.6),
            (r * 0.64, 8, t * 2.3, 0.8),
        ]
        for radius, segments, rotation, alpha in ring_defs:
            gap = (2 * math.pi / segments)
            arc_len = gap * 0.55
            cr.set_line_width(2.2)
            cr.set_source_rgba(*rgba(color, alpha))
            for i in range(segments):
                start = i * gap + rotation
                cr.arc(0, 0, radius, start, start + arc_len)
                cr.stroke()

    # -- small diagnostic markings (originally authored, not copied) -----
    def _draw_diagnostic_ticks(self, cr, r, color):
        cr.set_source_rgba(*rgba(color, 0.55))
        cr.select_font_face("monospace", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(7)
        labels = [
            (-r * 1.34, -r * 1.02, "SYS.CORE"),
            (r * 0.78, -r * 1.16, "V4"),
            (-r * 1.34, r * 1.14, "RX-09"),
            (r * 0.9, r * 1.14, "AUX"),
        ]
        for x, y, text in labels:
            cr.move_to(x, y)
            cr.show_text(text)

    # -- orbiting particles ------------------------------------------------
    def _draw_particles(self, cr, r, color, t):
        count = 10
        for i in range(count):
            phase = (i / count) * 2 * math.pi
            orbit_r = r * (0.72 + 0.22 * math.sin(t * 1.3 + i))
            angle = phase + t * (1.1 if i % 2 == 0 else -0.8)
            x = orbit_r * math.cos(angle)
            y = orbit_r * math.sin(angle)
            alpha = 0.25 + 0.35 * (0.5 + 0.5 * math.sin(t * 2 + i))
            cr.set_source_rgba(*rgba(color, alpha))
            cr.arc(x, y, 1.4, 0, 2 * math.pi)
            cr.fill()

    # -- pulsing energy center --------------------------------------------
    def _draw_core(self, cr, r, color, glow, t):
        breathing = 0.5 + 0.5 * math.sin(t * 2.2)
        kick = self._pulse_energy * 0.5
        core_r = r * (0.26 + 0.04 * breathing + kick * 0.08)

        gradient = cairo.RadialGradient(0, 0, 0, 0, 0, core_r * 2.2)
        gradient.add_color_stop_rgba(0.0, *rgba(glow, 0.9))
        gradient.add_color_stop_rgba(0.35, *rgba(color, 0.55))
        gradient.add_color_stop_rgba(1.0, *rgba(color, 0.0))
        cr.set_source(gradient)
        cr.arc(0, 0, core_r * 2.2, 0, 2 * math.pi)
        cr.fill()

        cr.set_source_rgba(*rgba(glow, 0.95))
        cr.arc(0, 0, core_r * 0.55, 0, 2 * math.pi)
        cr.fill()

        # thin inner core ring
        cr.set_line_width(1.2)
        cr.set_source_rgba(*rgba(color, 0.8))
        cr.arc(0, 0, core_r, 0, 2 * math.pi)
        cr.stroke()

        # speaking / processing: extra spiking waveform ring
        if self._state in ("speaking", "processing"):
            cr.set_line_width(1.0)
            cr.set_source_rgba(*rgba(glow, 0.7))
            points = 48
            cr.move_to((core_r * 1.35), 0)
            for i in range(1, points + 1):
                a = (2 * math.pi / points) * i
                spike = 1.0
                if self._state == "speaking":
                    spike += 0.18 * math.sin(a * 7 + t * 9)
                else:
                    spike += 0.10 * math.sin(a * 11 - t * 14)
                rad = core_r * 1.35 * spike
                cr.line_to(rad * math.cos(a), rad * math.sin(a))
            cr.close_path()
            cr.stroke()

    # -- status text beneath the core --------------------------------------
    def _draw_readout(self, cr, r, color):
        cfg = CORE_STATES[self._state]
        cr.select_font_face("monospace", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(11)
        text = cfg["label"]
        extents = cr.text_extents(text)
        cr.set_source_rgba(*rgba(color, 0.95))
        cr.move_to(-extents.width / 2, r * 1.55)
        cr.show_text(text)
