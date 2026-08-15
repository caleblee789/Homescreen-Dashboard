"""Home Dashboard - Overhaul add-on entry point."""

from __future__ import annotations

try:
    from aqt import mw
except ImportError:  # Pure modules and tests remain usable outside Anki.
    mw = None  # type: ignore[assignment]
    controller = None
else:
    from .controller import DashboardController

    if getattr(mw, "_home_dashboard_overhaul_controller", None) is None:
        controller = DashboardController()
        controller.start()
        mw._home_dashboard_overhaul_controller = controller
    else:
        controller = mw._home_dashboard_overhaul_controller


__all__ = ["controller"]
