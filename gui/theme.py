"""JARVIS V4 - theme constants and GTK CSS.

Pure data. No GTK imports at module scope beyond the CSS string so this
file can be imported by non-GUI code (tests, tooling) without a display.
"""

# ---------------------------------------------------------------- palette
# Cairo colours are (r, g, b) floats 0..1
BG_TOP      = (0.016, 0.031, 0.055)
BG_BOTTOM   = (0.008, 0.016, 0.031)
CYAN        = (0.239, 0.792, 1.000)
CYAN_DIM    = (0.106, 0.412, 0.596)
CYAN_DEEP   = (0.039, 0.176, 0.290)
WHITE       = (0.878, 0.960, 1.000)
AMBER       = (1.000, 0.706, 0.278)
GREEN       = (0.259, 0.902, 0.588)
RED         = (1.000, 0.353, 0.376)
GRID        = (0.078, 0.216, 0.318)

# Hex equivalents for CSS
H_CYAN      = "#3dcaff"
H_CYAN_DIM  = "#1a6998"
H_WHITE     = "#e0f5ff"
H_MUTED     = "#7fa8c0"
H_GREEN     = "#42e696"
H_AMBER     = "#ffb447"
H_RED       = "#ff5a60"
H_PANEL_BG  = "rgba(8, 24, 40, 0.55)"
H_PANEL_BRD = "rgba(61, 202, 255, 0.28)"

# Status token -> colour
STATUS_COLOURS = {
    "Connected": H_GREEN,
    "Ready":     H_GREEN,
    "Active":    H_GREEN,
    "Online":    H_GREEN,
    "Link up":   H_GREEN,
    "Charging":  H_GREEN,
    "Offline":   H_MUTED,
    "Unknown":   H_AMBER,
    "Error":     H_RED,
    "Unavailable": H_MUTED,
}


def status_colour(text):
    if not text:
        return H_MUTED
    return STATUS_COLOURS.get(text, H_CYAN)


# ---------------------------------------------------------------- fonts
# Orbitron / Rajdhani look the part but are rarely installed; the chain
# degrades to DejaVu Sans which ships with Zorin.
UI_FONT = '"Orbitron", "Rajdhani", "Titillium Web", "DejaVu Sans", sans-serif'
# Cairo "toy" font API - keep it to something guaranteed present.
CAIRO_FONT = "DejaVu Sans"

# ---------------------------------------------------------------- layout
SIDE_WIDTH = 302
PANEL_PAD = 10
GUTTER = 10

# ---------------------------------------------------------------- CSS
CSS = ("""
window.jarvis {
    background-color: #04080f;
    color: %(white)s;
    font-family: %(font)s;
}

label { color: %(white)s; }

.panel {
    background-color: %(panel_bg)s;
    border: 1px solid %(panel_brd)s;
    border-radius: 6px;
    padding: 9px 11px;
}

.panel-title {
    color: %(cyan)s;
    font-size: 10.5px;
    font-weight: bold;
    letter-spacing: 2px;
    padding-bottom: 4px;
}

.metric-key   { color: %(muted)s; font-size: 11px; }
.metric-val   { color: %(white)s; font-size: 11px; }
.muted        { color: %(muted)s; font-size: 10.5px; }
.tiny         { color: %(muted)s; font-size: 9.5px; letter-spacing: 1px; }

.topbar {
    background-color: rgba(6, 18, 32, 0.72);
    border-bottom: 1px solid %(panel_brd)s;
    padding: 6px 14px;
}
.brand {
    color: %(cyan)s;
    font-size: 15px;
    font-weight: bold;
    letter-spacing: 4px;
}
.online { color: %(green)s; font-size: 11px; font-weight: bold; letter-spacing: 2px; }
.offline-ind { color: %(red)s; font-size: 11px; font-weight: bold; letter-spacing: 2px; }
.clock { color: %(white)s; font-size: 12px; }

progressbar trough {
    min-height: 5px;
    background-color: rgba(61, 202, 255, 0.12);
    border: none;
    border-radius: 3px;
}
progressbar progress {
    min-height: 5px;
    background-image: linear-gradient(to right, %(cyandim)s, %(cyan)s);
    border: none;
    border-radius: 3px;
}
progressbar.warn progress {
    background-image: linear-gradient(to right, #8a5a10, %(amber)s);
}

button.cmd {
    background-image: none;
    background-color: rgba(12, 38, 60, 0.5);
    border: 1px solid rgba(61, 202, 255, 0.20);
    border-radius: 4px;
    color: %(white)s;
    font-size: 11px;
    padding: 5px 9px;
    text-shadow: none;
}
button.cmd:hover {
    background-color: rgba(26, 105, 152, 0.55);
    border-color: %(cyan)s;
}
button.cmd:active { background-color: rgba(61, 202, 255, 0.30); }
button.cmd:disabled { color: %(muted)s; border-color: rgba(127,168,192,0.15); }

button.mic {
    background-image: none;
    background-color: rgba(10, 32, 52, 0.75);
    border: 1px solid %(cyan)s;
    border-radius: 34px;
    color: %(cyan)s;
    font-size: 18px;
    padding: 0px;
}
button.mic:hover { background-color: rgba(61, 202, 255, 0.22); }
button.mic.muted { border-color: %(muted)s; color: %(muted)s; }

scrolledwindow { background-color: transparent; }
scrollbar { background-color: transparent; }
scrollbar slider {
    background-color: rgba(61, 202, 255, 0.28);
    border-radius: 6px;
    min-width: 5px;
}
list, row { background-color: transparent; }
row:selected { background-color: transparent; }
""" % {
    "white": H_WHITE, "cyan": H_CYAN, "cyandim": H_CYAN_DIM, "muted": H_MUTED,
    "green": H_GREEN, "amber": H_AMBER, "red": H_RED,
    "panel_bg": H_PANEL_BG, "panel_brd": H_PANEL_BRD, "font": UI_FONT,
})
