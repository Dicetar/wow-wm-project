"""Pytest configuration.

Temp handling is deliberately NOT monkeypatched. Test temp directories use
pytest's native ``tmp_path`` / ``tmp_path_factory`` fixtures.

We root pytest's temp tree inside the workspace (``.wm-pytest-tmp/``, excluded
from collection by ``norecursedirs``) by pointing the standard temp env vars at
it -- NOT by pinning a single ``--basetemp`` dir. That matters for two reasons
seen on this Windows host:

* A fixed ``--basetemp=.wm-pytest-tmp/pt`` fails from a clean workspace because
  pytest ``mkdir()``s the basetemp without creating its parent.
* A fixed basetemp is ``rmtree``+recreated every run, so a lingering Windows
  file lock makes the *next* run fail.

Using pytest's default temp scheme instead gives numbered ``pytest-<N>`` dirs
with keep-last-3 cleanup, which is robust to repeated runs. We only guarantee
the workspace root exists and steer the temp env at it.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def pytest_configure(config: object) -> None:
    # Respect an explicit --basetemp passed by the caller.
    if getattr(getattr(config, "option", None), "basetemp", None):
        return
    root = Path(".wm-pytest-tmp").resolve()
    root.mkdir(parents=True, exist_ok=True)
    for var in ("TMPDIR", "TEMP", "TMP"):
        os.environ[var] = str(root)
    # Drop tempfile's cached default so the env above is honored on first use.
    tempfile.tempdir = None
