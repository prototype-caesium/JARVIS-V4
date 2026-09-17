#!/usr/bin/env python3
"""JARVIS V4 - HUD launcher.

    python gui_main.py                # fullscreen, voice on
    python gui_main.py --windowed     # windowed
    python gui_main.py --no-voice     # GUI only, no listener thread
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(description="JARVIS V4 HUD")
    parser.add_argument("--windowed", action="store_true",
                        help="start windowed instead of fullscreen")
    parser.add_argument("--no-voice", action="store_true",
                        help="do not start the voice listener thread")
    args = parser.parse_args()

    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk  # noqa: F401
    except Exception as exc:
        sys.stderr.write(
            "GTK3 / PyGObject unavailable: %s\n"
            "Install with:\n"
            "  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0\n"
            "and make sure the venv can see system packages.\n" % exc)
        return 2

    from gui.app import run
    print("JARVIS V4")
    print("ONLINE")
    return run(fullscreen=not args.windowed, voice=not args.no_voice)


if __name__ == "__main__":
    sys.exit(main())
