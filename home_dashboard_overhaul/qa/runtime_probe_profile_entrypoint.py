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

# Importing the release probe registers the delayed, isolation-gated Anki hook.
from . import _release_probe as _release_probe  # noqa: E402,F401

if bool(_profile.get("full_screen")):
    from . import _fullscreen_profile as _fullscreen_profile  # noqa: E402,F401
