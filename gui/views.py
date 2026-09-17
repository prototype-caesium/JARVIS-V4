"""Backwards-compatible surface for older imports of gui.views.

The HUD widgets now live in gui.panels and gui.hud. Anything that used to do
`from gui.views import ...` keeps working through these re-exports.
"""

from gui.hud import Animator, CoreWidget, WaveformWidget  # noqa: F401
from gui.panels import (ActivityPanel, DeviceStatusPanel,  # noqa: F401
                        MetricRow, Panel, QuickCommandsPanel,
                        SchedulePanel, SystemStatusPanel, WeatherPanel)

__all__ = [
    "Animator", "CoreWidget", "WaveformWidget",
    "Panel", "MetricRow", "SystemStatusPanel", "QuickCommandsPanel",
    "WeatherPanel", "SchedulePanel", "ActivityPanel", "DeviceStatusPanel",
]


def build_main_view(*_args, **_kwargs):
    """Legacy hook. The window is assembled in gui.app.JarvisWindow now."""
    raise NotImplementedError(
        "gui.views.build_main_view was replaced by gui.app.JarvisWindow")
