#!/usr/bin/env python3
"""JARVIS V4 - unified GUI + voice launcher."""

import sys

from gui_main import main as gui_main


def main():
    print("=" * 40)
    print("        JARVIS V4")
    print("   GUI + VOICE SYSTEM")
    print("=" * 40)

    # gui_main already starts the single voice listener
    # through AssistantBridge.
    return gui_main()


if __name__ == "__main__":
    sys.exit(main())
