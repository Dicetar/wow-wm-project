from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path

import pytest


_WORKSPACE_TMP_ROOT = Path(".wm-pytest-tmp")


def _workspace_tmp_root() -> Path:
    root = _WORKSPACE_TMP_ROOT.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _make_workspace_temp_dir(
    kind: str,
    *,
    suffix: str | None = None,
    prefix: str | None = None,
    dir: str | None = None,
) -> Path:
    base = Path(dir).resolve() if dir is not None else _workspace_tmp_root() / kind
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{prefix or 'tmp'}{uuid.uuid4().hex}{suffix or ''}"
    path.mkdir(parents=True, exist_ok=False)
    return path


class _WorkspaceTemporaryDirectory:
    def __init__(self, suffix: str | None = None, prefix: str | None = None, dir: str | None = None, **_: object) -> None:
        self.name = str(_make_workspace_temp_dir("tempfile", suffix=suffix, prefix=prefix, dir=dir))

    def __enter__(self) -> str:
        return self.name

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.cleanup()

    def cleanup(self) -> None:
        shutil.rmtree(self.name, ignore_errors=True)


def pytest_configure() -> None:
    root = _workspace_tmp_root()
    os.environ.setdefault("TMP", str(root))
    os.environ.setdefault("TEMP", str(root))
    os.environ.setdefault("TMPDIR", str(root))
    tempfile.tempdir = str(root)
    tempfile.TemporaryDirectory = _WorkspaceTemporaryDirectory  # type: ignore[assignment]


@pytest.fixture
def tmp_path() -> Path:
    path = _make_workspace_temp_dir("tmp_path")
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
