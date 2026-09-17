"""Glass HUD panels. Plain GTK widgets - they repaint only when data moves."""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango  # noqa: E402

from gui import theme as T  # noqa: E402

MAX_LOG_ROWS = 120


def _label(text, css=None, xalign=0.0):
    lb = Gtk.Label(label=text)
    lb.set_xalign(xalign)
    if css:
        lb.get_style_context().add_class(css)
    return lb


class Panel(Gtk.Box):
    """A titled glass panel."""

    def __init__(self, title):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.get_style_context().add_class("panel")
        self.title_label = _label(title.upper(), "panel-title")
        self.pack_start(self.title_label, False, False, 0)
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.pack_start(self.body, True, True, 0)


class MetricRow(Gtk.Box):

    def __init__(self, name):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.key = _label(name, "metric-key")
        self.key.set_size_request(46, -1)
        self.bar = Gtk.ProgressBar()
        self.bar.set_valign(Gtk.Align.CENTER)
        self.bar.set_hexpand(True)
        self.bar.set_fraction(0.0)
        self.val = _label("--", "metric-val", xalign=1.0)
        self.val.set_size_request(86, -1)
        self.pack_start(self.key, False, False, 0)
        self.pack_start(self.bar, True, True, 0)
        self.pack_start(self.val, False, False, 0)

    def update(self, fraction, text, warn=False):
        if fraction is None:
            self.bar.set_fraction(0.0)
            self.val.set_text(text)
            return
        self.bar.set_fraction(max(0.0, min(1.0, fraction)))
        ctx = self.bar.get_style_context()
        if warn:
            ctx.add_class("warn")
        else:
            ctx.remove_class("warn")
        self.val.set_text(text)


class SystemStatusPanel(Panel):

    def __init__(self):
        Panel.__init__(self, "System Status")
        self.cpu = MetricRow("CPU")
        self.ram = MetricRow("RAM")
        self.disk = MetricRow("DISK")
        self.temp = MetricRow("TEMP")
        for row in (self.cpu, self.ram, self.disk, self.temp):
            self.body.pack_start(row, False, False, 0)
        self.net = _label("NET   --", "muted")
        self.body.pack_start(self.net, False, False, 2)

    def update(self, m):
        cpu = m.cpu()
        if cpu is None:
            self.cpu.update(None, "n/a")
        else:
            self.cpu.update(cpu / 100.0, "%d%%" % int(cpu), cpu > 85)

        mem = m.memory()
        if mem is None:
            self.ram.update(None, "n/a")
        else:
            pct, used, total = mem
            self.ram.update(pct / 100.0, "%.1f / %.1f GB" % (used, total),
                            pct > 88)

        dk = m.disk()
        if dk is None:
            self.disk.update(None, "n/a")
        else:
            pct, used, total = dk
            self.disk.update(pct / 100.0, "%d%%" % int(pct), pct > 90)

        tp = m.temperature()
        if tp is None:
            self.temp.update(None, "n/a")
        else:
            self.temp.update(min(1.0, tp / 100.0), "%d\u00b0C" % int(tp),
                             tp > 80)

        self.net.set_text("NET   %s" % m.network())


class QuickCommandsPanel(Panel):

    def __init__(self, labels, on_click):
        Panel.__init__(self, "Quick Commands")
        self.buttons = []
        for text in labels:
            btn = Gtk.Button(label=text)
            btn.get_style_context().add_class("cmd")
            btn.set_relief(Gtk.ReliefStyle.NONE)
            child = btn.get_child()
            if isinstance(child, Gtk.Label):
                child.set_xalign(0.0)
            btn.connect("clicked", lambda _b, t=text: on_click(t))
            self.body.pack_start(btn, False, False, 0)
            self.buttons.append(btn)


class WeatherPanel(Panel):

    def __init__(self):
        Panel.__init__(self, "Weather")
        self.main = _label("Weather unavailable", "metric-val")
        self.sub = _label("No weather provider configured", "tiny")
        self.body.pack_start(self.main, False, False, 0)
        self.body.pack_start(self.sub, False, False, 0)

    def set_unavailable(self, reason="No weather provider configured"):
        self.main.set_text("Weather unavailable")
        self.sub.set_text(reason)

    def set_weather(self, temp_c, description, location):
        """Call this only with data from a real provider."""
        self.main.set_text("%d\u00b0C  %s" % (int(temp_c), description))
        self.sub.set_text(location)


class SchedulePanel(Panel):
    """Sample rows until a calendar source is wired in."""

    SAMPLE = [
        ("Class 9 - Study", "07:30 - 09:00"),
        ("Tuition",         "10:30 - 14:00"),
        ("Tuition",         "15:30 - 19:00"),
        ("Revision",        "19:30 - 20:15"),
        ("Sleep",           "22:30"),
    ]

    def __init__(self):
        Panel.__init__(self, "Your Day")
        for name, when in self.SAMPLE:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            marker = _label("\u2503", "metric-val")
            marker.override_color(Gtk.StateFlags.NORMAL, None)
            row.pack_start(marker, False, False, 0)
            row.pack_start(_label(name, "metric-val"), False, False, 0)
            time_lb = _label(when, "muted", xalign=1.0)
            row.pack_end(time_lb, False, False, 0)
            self.body.pack_start(row, False, False, 0)
        self.body.pack_start(_label("sample data - calendar not connected",
                                    "tiny"), False, False, 3)


class ActivityPanel(Panel):

    PREFIX = {
        "user":    ("You", T.H_WHITE),
        "jarvis":  ("JARVIS", T.H_CYAN),
        "system":  ("System", T.H_MUTED),
        "arduino": ("Arduino", T.H_GREEN),
        "error":   ("Error", T.H_RED),
    }

    def __init__(self):
        Panel.__init__(self, "Recent Activity")
        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroller.set_min_content_height(150)
        self.scroller.set_vexpand(True)
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.scroller.add(self.listbox)
        self.body.pack_start(self.scroller, True, True, 0)
        self._rows = 0

    def add_event(self, event):
        name, colour = self.PREFIX.get(event.kind, ("Log", T.H_MUTED))
        text = GLib.markup_escape_text(event.text)
        markup = ('<span foreground="%s" size="8500">%s</span>  '
                  '<span foreground="%s" size="8500"><b>%s:</b></span> '
                  '<span foreground="%s" size="8500">%s</span>'
                  % (T.H_MUTED, event.stamp(), colour, name, T.H_WHITE, text))
        lb = Gtk.Label()
        lb.set_markup(markup)
        lb.set_xalign(0.0)
        lb.set_line_wrap(True)
        lb.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        lb.set_max_width_chars(38)

        row = Gtk.ListBoxRow()
        row.set_activatable(False)
        row.set_selectable(False)
        row.add(lb)
        row.show_all()
        self.listbox.add(row)
        self._rows += 1

        while self._rows > MAX_LOG_ROWS:
            first = self.listbox.get_row_at_index(0)
            if first is None:
                break
            self.listbox.remove(first)
            self._rows -= 1

        GLib.idle_add(self._scroll_bottom, priority=GLib.PRIORITY_LOW)

    def _scroll_bottom(self):
        adj = self.scroller.get_vadjustment()
        if adj is not None:
            adj.set_value(max(0.0, adj.get_upper() - adj.get_page_size()))
        return False


class DeviceStatusPanel(Panel):

    def __init__(self, names):
        Panel.__init__(self, "Device Status")
        self.rows = {}
        for name in names:
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            box.pack_start(_label(name, "metric-val"), False, False, 0)
            value = Gtk.Label()
            value.set_xalign(1.0)
            box.pack_end(value, False, False, 0)
            self.body.pack_start(box, False, False, 0)
            self.rows[name] = value
        self.set_status(dict((n, "Unknown") for n in names))

    def set_status(self, mapping):
        for name, status in mapping.items():
            lb = self.rows.get(name)
            if lb is None:
                continue
            colour = T.status_colour(status)
            lb.set_markup('<span foreground="%s" size="8500">\u25cf %s</span>'
                          % (colour, GLib.markup_escape_text(str(status))))
