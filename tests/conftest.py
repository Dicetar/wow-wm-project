"""Pytest configuration.

This file points stdlib tempfile and pytest's tmp_path machinery at a fresh
per-process workspace root and replaces ``TemporaryDirectory`` with a narrow
test-only wrapper because Python 3.14's stdlib implementation creates
inaccessible 0o700 directories on this Windows host.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

import pytest

_RUN_TEMP_ROOT: Path | None = None


def pytest_configure(config: object) -> None:
    global _RUN_TEMP_ROOT
    del config
    root = _make_run_temp_root()
    _RUN_TEMP_ROOT = root
    for var in ("TMPDIR", "TEMP", "TMP"):
        os.environ[var] = str(root)
    tempfile.tempdir = str(root)
    tempfile.mkdtemp = _mkdtemp_factory(root)  # type: ignore[assignment]
    tempfile.TemporaryDirectory = _temporary_directory_factory(root)  # type: ignore[assignment]


def pytest_collection_modifyitems(config: object, items: list[pytest.Item]) -> None:
    del config
    skip_db = pytest.mark.skip(reason="no DB configured; set WM_TEST_DB_HOST to enable")
    skip_bridge = pytest.mark.skip(reason="no BridgeLab configured; set WM_TEST_BRIDGELAB=1 to enable")
    db_enabled = bool(os.getenv("WM_TEST_DB_HOST"))
    bridge_enabled = os.getenv("WM_TEST_BRIDGELAB", "").strip().lower() in {"1", "true", "yes", "on"}
    for item in items:
        if "bridge_contract" in item.keywords and not bridge_enabled:
            item.add_marker(skip_bridge)
        if ("db_integration" in item.keywords or "content_plan" in item.keywords) and not db_enabled:
            item.add_marker(skip_db)


@pytest.fixture
def tmp_path() -> Path:
    root = _RUN_TEMP_ROOT
    if root is None:
        root = _make_run_temp_root()
    return _make_temp_dir(root, prefix="pytest-")


def _make_run_temp_root() -> Path:
    run_name = f"run-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    raw_candidates = [
        os.environ.get("WM_PYTEST_STDLIB_TEMP_ROOT"),
        ".wm-test-runs",
        "../wm-project-pytest-stdlib",
        str(Path(os.environ.get("TEMP") or tempfile.gettempdir()) / "wm-project-pytest-stdlib"),
    ]
    errors: list[str] = []
    for raw in raw_candidates:
        if not raw:
            continue
        root = Path(raw).resolve() / run_name
        try:
            root.mkdir(parents=True, exist_ok=False)
        except OSError as exc:
            errors.append(f"{root}: {exc}")
            continue
        return root
    raise RuntimeError("could not create pytest stdlib temp root; " + " | ".join(errors))


def _temporary_directory_factory(root: Path) -> type:
    class SafeTemporaryDirectory:
        def __init__(
            self,
            suffix: str | None = None,
            prefix: str | None = None,
            dir: str | os.PathLike[str] | None = None,
            ignore_cleanup_errors: bool = False,
            *,
            delete: bool = True,
        ) -> None:
            del ignore_cleanup_errors
            name_prefix = "tmp" if prefix is None else prefix
            name_suffix = "" if suffix is None else suffix
            self.name = str(_make_temp_dir(root, prefix=name_prefix, suffix=name_suffix, dir=dir))
            self._delete = delete

        def __enter__(self) -> str:
            return self.name

        def __exit__(self, exc: Any, value: Any, traceback: Any) -> None:
            del exc, value, traceback
            self.cleanup()

        def cleanup(self) -> None:
            if self._delete:
                shutil.rmtree(self.name, ignore_errors=True)

    return SafeTemporaryDirectory


def _mkdtemp_factory(root: Path):
    def mkdtemp(suffix: str | None = None, prefix: str | None = None, dir: str | os.PathLike[str] | None = None) -> str:
        return str(_make_temp_dir(
            root,
            prefix="tmp" if prefix is None else prefix,
            suffix="" if suffix is None else suffix,
            dir=dir,
        ))

    return mkdtemp


def _make_temp_dir(
    root: Path,
    *,
    prefix: str = "tmp",
    suffix: str = "",
    dir: str | os.PathLike[str] | None = None,
) -> Path:
    base = Path(dir).resolve() if dir is not None else root
    base.mkdir(parents=True, exist_ok=True)
    for _ in range(100):
        candidate = base / f"{prefix}{uuid.uuid4().hex}{suffix}"
        try:
            candidate.mkdir()
        except FileExistsError:
            continue
        return candidate
    raise FileExistsError(f"could not allocate temp dir under {base}")
