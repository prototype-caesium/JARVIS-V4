"""Cairo-drawn holographic core and waveform.

Everything is vector maths - no textures, no GL, no shaders. Both widgets
paint an opaque backdrop inside their own allocation so GTK never has to
repaint an ancestor when they invalidate.
"""

import math
import random

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

import cairo  # noqa: E402

from gui import theme as T  # noqa: E402
from gui.voice_state import VoiceState  # noqa: E402

TWO_PI = math.pi * 2.0

FPS_ACTIVE = 24
FPS_IDLE = 5

STATE_ACCENT = {
    VoiceState.IDLE:       T.CYAN,
    VoiceState.LISTENING:  (0.45, 0.90, 1.00),
    VoiceState.PROCESSING: T.AMBER,
    VoiceState.SPEAKING:   T.GREEN,
    VoiceState.ERROR:      T.RED,
    VoiceState.MUTED:      (0.45, 0.55, 0.62),
}


def _ellipse(cr, cx, cy, rx, ry):
    """Path an ellipse without scaling the eventual stroke width."""
    if rx <= 0.4 or ry <= 0.4:
        return
    cr.save()
    cr.translate(cx, cy)
    cr.scale(rx, ry)
    cr.new_sub_path()
    cr.arc(0.0, 0.0, 1.0, 0.0, TWO_PI)
    cr.restore()


class Animator(object):
    """Single adaptive-rate clock shared by the HUD widgets."""

    def __init__(self):
        self._widgets = []
        self._source = None
        self._fps = FPS_IDLE
        self._running = False
        self.phase = 0.0
        self.reduced = False
        settings = Gtk.Settings.get_default()
        if settings is not None:
            try:
                self.reduced = not settings.get_property("gtk-enable-animations")
            except Exception:
                self.reduced = False

    def add(self, widget):
        self._widgets.append(widget)

    def start(self):
        if self._running:
            return
        self._running = True
        self._arm()

    def _arm(self):
        if self._source is not None:
            GLib.source_remove(self._source)
            self._source = None
        if not self._running:
            return
        interval = int(1000.0 / max(1, self._fps))
        self._source = GLib.timeout_add(interval, self._tick)

    def set_fps(self, fps):
        fps = max(1, int(fps))
        if fps == self._fps:
            return
        self._fps = fps
        self._arm()

    def set_active(self, active):
        if self.reduced:
            self.set_fps(2)
            return
        self.set_fps(FPS_ACTIVE if active else FPS_IDLE)

    def pause(self):
        self._running = False
        if self._source is not None:
            GLib.source_remove(self._source)
            self._source = None

    def resume(self):
        if not self._running:
            self._running = True
            self._arm()

    def _tick(self):
        self.phase += 1.0 / float(self._fps)
        for w in self._widgets:
            if w.get_mapped():
                w.queue_draw()
        return True

    def shutdown(self):
        self.pause()
        self._widgets = []


class CoreWidget(Gtk.DrawingArea):
    """The central holographic sphere."""

    def __init__(self, animator):
        Gtk.DrawingArea.__init__(self)
        self.anim = animator
        self.state = VoiceState.IDLE
        self.set_size_request(380, 400)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.connect("draw", self.on_draw)
        rng = random.Random(20260916)
        self.particles = [
            (rng.uniform(1.12, 1.68),                 # radius factor
             rng.uniform(0.0, TWO_PI),                # phase offset
             rng.choice((-1.0, 1.0)) * rng.uniform(0.10, 0.34),  # speed
             rng.uniform(0.55, 1.7),                  # dot radius
             rng.uniform(0.18, 0.55))                 # alpha
            for _ in range(22)
        ]
        animator.add(self)

    def set_state(self, state):
        self.state = state
        self.queue_draw()

    # ------------------------------------------------------------- draw
    def on_draw(self, widget, cr):
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        if w < 8 or h < 8:
            return False

        t = self.anim.phase
        accent = STATE_ACCENT.get(self.state, T.CYAN)

        # opaque backdrop so GTK never repaints ancestors
        bg = cairo.LinearGradient(0, 0, 0, h)
        bg.add_color_stop_rgb(0.0, *T.BG_TOP)
        bg.add_color_stop_rgb(1.0, *T.BG_BOTTOM)
        cr.set_source(bg)
        cr.paint()

        cx = w * 0.5
        cy = h * 0.44
        R = min(w * 0.42, h * 0.36)

        self._glow(cr, cx, cy, R, accent, t)
        self._platform(cr, cx, h * 0.80, R, accent, t)
        self._rings(cr, cx, cy, R, accent, t)
        self._sphere(cr, cx, cy, R, accent, t)
        self._scan(cr, cx, cy, R, accent, t)
        self._particles(cr, cx, cy, R, accent, t)
        self._text(cr, cx, cy, R, accent)
        return False

    def _glow(self, cr, cx, cy, R, accent, t):
        pulse = 0.5 + 0.5 * math.sin(t * 1.5)
        grad = cairo.RadialGradient(cx, cy, R * 0.1, cx, cy, R * 2.05)
        grad.add_color_stop_rgba(0.0, accent[0], accent[1], accent[2],
                                 0.20 + 0.10 * pulse)
        grad.add_color_stop_rgba(0.45, accent[0] * 0.5, accent[1] * 0.6,
                                 accent[2] * 0.8, 0.10)
        grad.add_color_stop_rgba(1.0, 0, 0, 0, 0.0)
        cr.set_source(grad)
        cr.arc(cx, cy, R * 2.05, 0, TWO_PI)
        cr.fill()

    def _sphere(self, cr, cx, cy, R, accent, t):
        grad = cairo.RadialGradient(cx - R * 0.28, cy - R * 0.32, R * 0.05,
                                    cx, cy, R)
        grad.add_color_stop_rgba(0.0, 0.62, 0.92, 1.0, 0.55)
        grad.add_color_stop_rgba(0.42, accent[0] * 0.55, accent[1] * 0.70,
                                 accent[2] * 0.95, 0.34)
        grad.add_color_stop_rgba(0.88, T.CYAN_DEEP[0], T.CYAN_DEEP[1],
                                 T.CYAN_DEEP[2], 0.42)
        grad.add_color_stop_rgba(1.0, 0.02, 0.09, 0.16, 0.16)
        cr.set_source(grad)
        cr.arc(cx, cy, R, 0, TWO_PI)
        cr.fill()

        # wireframe globe, clipped to the disc
        cr.save()
        cr.arc(cx, cy, R * 0.985, 0, TWO_PI)
        cr.clip()
        cr.set_line_width(0.9)

        for j in range(-3, 4):
            frac = j / 4.0
            ry_off = R * math.sin(frac * math.pi * 0.5)
            rx = R * math.cos(frac * math.pi * 0.5)
            cr.set_source_rgba(accent[0], accent[1], accent[2],
                               0.30 - 0.03 * abs(j))
            _ellipse(cr, cx, cy + ry_off, rx, rx * 0.20)
            cr.stroke()

        spin = t * 0.34
        for k in range(7):
            ang = spin + k * math.pi / 7.0
            rx = abs(math.cos(ang)) * R
            cr.set_source_rgba(accent[0], accent[1], accent[2],
                               0.13 + 0.20 * abs(math.cos(ang)))
            _ellipse(cr, cx, cy, rx, R)
            cr.stroke()
        cr.restore()

        # rim
        cr.set_line_width(1.3)
        cr.set_source_rgba(accent[0], accent[1], accent[2], 0.75)
        cr.arc(cx, cy, R, 0, TWO_PI)
        cr.stroke()

    def _rings(self, cr, cx, cy, R, accent, t):
        specs = ((1.20, 0.55, 3, 0.62, 1.5),
                 (1.36, -0.34, 5, 0.40, 1.0),
                 (1.55, 0.22, 2, 0.74, 2.0),
                 (1.72, -0.15, 8, 0.28, 0.8))
        for factor, speed, segments, fill, lw in specs:
            radius = R * factor
            base = t * speed
            cr.set_line_width(lw)
            for k in range(segments):
                start = base + k * TWO_PI / segments
                span = (TWO_PI / segments) * fill
                alpha = 0.22 + 0.22 * (0.5 + 0.5 * math.sin(base * 2.0 + k))
                cr.set_source_rgba(accent[0], accent[1], accent[2], alpha)
                cr.arc(cx, cy, radius, start, start + span)
                cr.stroke()

        # tick marks on the outer ring
        cr.set_line_width(1.0)
        outer = R * 1.86
        for k in range(48):
            ang = t * 0.08 + k * TWO_PI / 48.0
            long_tick = (k % 6 == 0)
            r0 = outer
            r1 = outer + (7.0 if long_tick else 3.0)
            cr.set_source_rgba(accent[0], accent[1], accent[2],
                               0.42 if long_tick else 0.18)
            cr.move_to(cx + r0 * math.cos(ang), cy + r0 * math.sin(ang))
            cr.line_to(cx + r1 * math.cos(ang), cy + r1 * math.sin(ang))
            cr.stroke()

    def _platform(self, cr, cx, base_y, R, accent, t):
        """Projector rings on the 'floor' under the sphere."""
        for i in range(4):
            spread = 0.55 + i * 0.30
            rx = R * spread * 1.45
            ry = rx * 0.17
            alpha = 0.30 - i * 0.055 + 0.05 * math.sin(t * 1.2 + i)
            if alpha <= 0.01:
                continue
            cr.set_line_width(1.6 - i * 0.28)
            cr.set_source_rgba(accent[0], accent[1], accent[2], alpha)
            _ellipse(cr, cx, base_y, rx, ry)
            cr.stroke()

        cone = cairo.LinearGradient(cx, base_y - R * 1.1, cx, base_y)
        cone.add_color_stop_rgba(0.0, accent[0], accent[1], accent[2], 0.0)
        cone.add_color_stop_rgba(1.0, accent[0], accent[1], accent[2], 0.10)
        cr.set_source(cone)
        cr.move_to(cx - R * 0.30, base_y - R * 1.1)
        cr.line_to(cx + R * 0.30, base_y - R * 1.1)
        cr.line_to(cx + R * 1.05, base_y)
        cr.line_to(cx - R * 1.05, base_y)
        cr.close_path()
        cr.fill()

    def _scan(self, cr, cx, cy, R, accent, t):
        span = R * 2.0
        y = cy - R + ((t * 58.0) % span)
        cr.save()
        cr.arc(cx, cy, R * 0.99, 0, TWO_PI)
        cr.clip()
        grad = cairo.LinearGradient(cx - R, y - 9, cx + R, y + 9)
        grad.add_color_stop_rgba(0.0, accent[0], accent[1], accent[2], 0.0)
        grad.add_color_stop_rgba(0.5, 0.85, 0.97, 1.0, 0.30)
        grad.add_color_stop_rgba(1.0, accent[0], accent[1], accent[2], 0.0)
        cr.set_source(grad)
        cr.rectangle(cx - R, y - 1.2, R * 2.0, 2.4)
        cr.fill()

        # static scan lines, cheap
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.10)
        yy = cy - R
        while yy < cy + R:
            cr.rectangle(cx - R, yy, R * 2.0, 1.0)
            yy += 4.0
        cr.fill()
        cr.restore()

    def _particles(self, cr, cx, cy, R, accent, t):
        for factor, offset, speed, size, alpha in self.particles:
            ang = offset + t * speed
            radius = R * factor
            px = cx + radius * math.cos(ang)
            py = cy + radius * math.sin(ang) * 0.42
            cr.set_source_rgba(accent[0], accent[1], accent[2],
                               alpha * (0.6 + 0.4 * math.sin(t + offset)))
            cr.arc(px, py, size, 0, TWO_PI)
            cr.fill()

    def _text(self, cr, cx, cy, R, accent):
        cr.select_font_face(T.CAIRO_FONT, cairo.FONT_SLANT_NORMAL,
                            cairo.FONT_WEIGHT_BOLD)
        size = max(18.0, R * 0.30)
        cr.set_font_size(size)
        label = "JARVIS"
        ext = cr.text_extents(label)
        tx = cx - ext.width / 2.0 - ext.x_bearing
        ty = cy + ext.height / 2.0

        cr.set_source_rgba(accent[0], accent[1], accent[2], 0.35)
        cr.move_to(tx + 1.4, ty + 1.4)
        cr.show_text(label)
        cr.set_source_rgba(0.96, 0.99, 1.0, 0.96)
        cr.move_to(tx, ty)
        cr.show_text(label)

        cr.select_font_face(T.CAIRO_FONT, cairo.FONT_SLANT_NORMAL,
                            cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(size * 0.42)
        sub = "V4"
        ext2 = cr.text_extents(sub)
        cr.set_source_rgba(accent[0], accent[1], accent[2], 0.88)
        cr.move_to(cx - ext2.width / 2.0 - ext2.x_bearing, ty + size * 0.72)
        cr.show_text(sub)


class WaveformWidget(Gtk.DrawingArea):
    """Voice activity bars.

    NOTE: amplitudes are synthesised from the current voice state, not from
    live microphone samples - opening a second audio stream would contend
    with the recogniser. Feed real values via push_level() if you later
    expose RMS from voice/listener.py.
    """

    BARS = 58

    def __init__(self, animator):
        Gtk.DrawingArea.__init__(self)
        self.anim = animator
        self.state = VoiceState.IDLE
        self.levels = [0.04] * self.BARS
        self._external = None
        self.set_size_request(-1, 62)
        self.set_hexpand(True)
        self.connect("draw", self.on_draw)
        animator.add(self)

    def set_state(self, state):
        self.state = state

    def push_level(self, value):
        """Optional hook for real RMS in 0..1."""
        self._external = max(0.0, min(1.0, float(value)))

    def _target(self, i, t):
        if self._external is not None:
            base = self._external
        elif self.state == VoiceState.LISTENING:
            base = 0.55
        elif self.state == VoiceState.SPEAKING:
            base = 0.72
        elif self.state == VoiceState.PROCESSING:
            base = 0.22
        elif self.state == VoiceState.ERROR:
            base = 0.12
        else:
            base = 0.05

        centre = 1.0 - abs((i / float(self.BARS - 1)) - 0.5) * 2.0
        envelope = 0.25 + 0.75 * (centre ** 1.4)
        wob = (math.sin(t * 7.3 + i * 0.55) * 0.5
               + math.sin(t * 3.1 + i * 0.21) * 0.32
               + math.sin(t * 13.7 + i * 0.93) * 0.18)
        return max(0.03, base * envelope * (0.55 + 0.45 * abs(wob)))

    def on_draw(self, widget, cr):
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        if w < 8 or h < 8:
            return False

        cr.set_source_rgb(*T.BG_BOTTOM)
        cr.paint()

        t = self.anim.phase
        accent = STATE_ACCENT.get(self.state, T.CYAN)
        mid = h * 0.5
        slot = w / float(self.BARS)
        bar_w = max(1.4, slot * 0.42)

        for i in range(self.BARS):
            target = self._target(i, t)
            self.levels[i] += (target - self.levels[i]) * 0.35
            amp = self.levels[i] * (h * 0.46)
            x = slot * (i + 0.5)
            alpha = 0.30 + 0.60 * self.levels[i]
            cr.set_source_rgba(accent[0], accent[1], accent[2], alpha)
            cr.rectangle(x - bar_w / 2.0, mid - amp, bar_w, amp * 2.0)
            cr.fill()

        cr.set_line_width(1.0)
        cr.set_source_rgba(accent[0], accent[1], accent[2], 0.16)
        cr.move_to(0, mid)
        cr.line_to(w, mid)
        cr.stroke()
        return False
