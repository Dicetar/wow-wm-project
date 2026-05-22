"""Pytest configuration.

Temp handling is deliberately NOT monkeypatched here. Test temp directories use
pytest's native ``tmp_path`` / ``tmp_path_factory`` fixtures, relocated into the
workspace via ``--basetemp`` in ``pytest.ini`` (``.wm-pytest-tmp/`` is excluded
from collection by ``norecursedirs``). This keeps tests deterministic across
machines without globally replacing ``tempfile.TemporaryDirectory`` or shadowing
the built-in ``tmp_path`` fixture.
"""
from __future__ import annotations
