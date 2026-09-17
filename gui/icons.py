"""
icons.py
--------
Tiny hand-drawn vector glyphs for the left nav rail. Deliberately NOT using
emoji or an icon theme: emoji rendering is inconsistent across systems/fonts
and full icon themes add weight/dependencies we don't need on a 4GB laptop.
Each glyph is a couple dozen Cairo calls - practically free to render.
"""

import math
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from gui.theme import rgba


class NavIcon(Gtk.DrawingArea):
    __gtype_name__ = "NavIcon"

    def __init__(self, kind: str, size: int = 18):
        super().__init__()
        self._kind = kind
        self._color = (0.55, 0.83, 0.92)
        self.set_content_width(size)
        self.set_content_height(size)
        self.set_draw_func(self._draw, None)

    def set_color(self, rgb):
        self._color = rgb
        self.queue_draw()

    def _draw(self, area, cr, w, h, data):
        cr.save()
        cr.translate(w / 2, h / 2)
        cr.set_line_width(1.4)
        cr.set_source_rgba(*rgba(self._color, 0.95))
        s = min(w, h) * 0.36

        fn = getattr(self, f"_glyph_{self._kind}", self._glyph_home)
        fn(cr, s)

        cr.restore()

    # -- glyphs -----------------------------------------------------------
    def _glyph_home(self, cr, s):
        cr.move_to(-s, 0)
        cr.line_to(0, -s)
        cr.line_to(s, 0)
        cr.stroke()
        cr.rectangle(-s * 0.6, 0, s * 1.2, s)
        cr.stroke()

    def _glyph_voice(self, cr, s):
        cr.save()
        cr.translate(0, -s * 0.15)
        cr.move_to(-s * 0.35, -s * 0.3)
        cr.curve_to(-s * 0.35, -s * 0.9, s * 0.35, -s * 0.9, s * 0.35, -s * 0.3)
        cr.line_to(s * 0.35, s * 0.1)
        cr.curve_to(s * 0.35, s * 0.6, -s * 0.35, s * 0.6, -s * 0.35, s * 0.1)
        cr.close_path()
        cr.stroke()
        cr.arc(0, s * 0.35, s * 0.7, 0.25 * math.pi, 0.75 * math.pi)
        cr.stroke()
        cr.move_to(0, s * 1.0)
        cr.line_to(0, s * 1.3)
        cr.stroke()
        cr.restore()

    def _glyph_system(self, cr, s):
        cr.arc(0, 0, s * 0.9, 0, 2 * math.pi)
        cr.stroke()
        for i in range(8):
            a = i * (math.pi / 4)
            cr.move_to(s * 0.9 * math.cos(a), s * 0.9 * math.sin(a))
            cr.line_to(s * 1.25 * math.cos(a), s * 1.25 * math.sin(a))
            cr.stroke()
        cr.arc(0, 0, s * 0.35, 0, 2 * math.pi)
        cr.stroke()

    def _glyph_automation(self, cr, s):
        pts = [(-s, -s * 0.6), (s * 0.2, -s), (s, s * 0.5), (-s * 0.4, s)]
        for i in range(len(pts)):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % len(pts)]
            cr.move_to(x1, y1)
            cr.line_to(x2, y2)
            cr.stroke()
        for (x, y) in pts:
            cr.arc(x, y, s * 0.14, 0, 2 * math.pi)
            cr.fill()

    def _glyph_vision(self, cr, s):
        cr.save()
        cr.scale(1.3, 0.75)
        cr.arc(0, 0, s * 0.85, 0, 2 * math.pi)
        cr.restore()
        cr.stroke()
        cr.arc(0, 0, s * 0.32, 0, 2 * math.pi)
        cr.stroke()
        cr.arc(0, 0, s * 0.08, 0, 2 * math.pi)
        cr.fill()

    def _glyph_arduino(self, cr, s):
        cr.rectangle(-s * 0.75, -s * 0.55, s * 1.5, s * 1.1)
        cr.stroke()
        for i in range(-2, 3):
            cr.move_to(i * s * 0.3, -s * 0.55)
            cr.line_to(i * s * 0.3, -s * 0.8)
            cr.stroke()
            cr.move_to(i * s * 0.3, s * 0.55)
            cr.line_to(i * s * 0.3, s * 0.8)
            cr.stroke()

    def _glyph_logs(self, cr, s):
        for i, dy in enumerate((-s * 0.6, 0, s * 0.6)):
            length = s * (1.4 if i != 1 else 0.9)
            cr.move_to(-length / 2, dy)
            cr.line_to(length / 2, dy)
            cr.stroke()

    def _glyph_settings(self, cr, s):
        teeth = 6
        for i in range(teeth):
            a = i * (2 * math.pi / teeth)
            cr.move_to(s * 0.55 * math.cos(a), s * 0.55 * math.sin(a))
            cr.line_to(s * 1.05 * math.cos(a), s * 1.05 * math.sin(a))
            cr.stroke()
        cr.arc(0, 0, s * 0.55, 0, 2 * math.pi)
        cr.stroke()
        cr.arc(0, 0, s * 0.2, 0, 2 * math.pi)
        cr.stroke()
