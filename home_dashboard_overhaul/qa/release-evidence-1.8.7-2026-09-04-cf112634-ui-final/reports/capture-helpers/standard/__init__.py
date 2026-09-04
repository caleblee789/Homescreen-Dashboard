"""Generated capture-helper entrypoint.

``prepare_capture_helper.py`` copies this file as ``__init__.py`` beside a
resolved profile request, release probe, base probe, and capture plan.  Keeping
the entrypoint fixed makes helper contents reviewable and reproducible.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import _capture_plan as capture_plan


_plan = capture_plan.load_capture_plan()
_request = capture_plan.load_profile_request(Path(__file__), plan=_plan)
_profile_id = str(_request["id"])
_profile = _plan.profile(_profile_id)
os.environ["HDO_CAPTURE_PROFILE"] = _profile_id

# Geometry probes must not share native preferences with a normal Anki window.
_run_root = Path(os.environ.get("HDO_RELEASE_RUN_ROOT", ""))
if str(_run_root).startswith("/private/tmp/anki-release-qa."):
    from aqt.qt import QSettings

    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope,
        str(_run_root / "qt-preferences"),
    )

# Importing the release probe registers the delayed, isolation-gated Anki hook.
try:
    if os.environ.get("HDO_SETTINGS_WORKFLOW_STAGE") in {"initial", "restart"}:
        from . import _workflow_probe as _workflow_probe  # noqa: E402,F401
    else:
        from . import _release_probe as _release_probe  # noqa: E402,F401
except Exception:
    import traceback
    if str(_run_root).startswith("/private/tmp/anki-release-qa."):
        (_run_root / "probe-import-error.txt").write_text(traceback.format_exc(), encoding="utf-8")
    raise

if bool(_profile.get("full_screen")):
    from . import _fullscreen_profile as _fullscreen_profile  # noqa: E402,F401
