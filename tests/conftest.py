from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path


class _WorkspaceTemporaryDirectory:
    def __init__(self, suffix: str | None = None, prefix: str | None = None, dir: str | None = None, **_: object) -> None:
        base = Path(dir) if dir is not None else Path(".pytest-tmp")
        base.mkdir(parents=True, exist_ok=True)
        name = f"{prefix or 'tmp'}{uuid.uuid4().hex}{suffix or ''}"
        self.name = str(base / name)
        Path(self.name).mkdir(parents=True, exist_ok=False)

    def __enter__(self) -> str:
        return self.name

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.cleanup()

    def cleanup(self) -> None:
        shutil.rmtree(self.name, ignore_errors=True)


def pytest_configure() -> None:
    tempfile.TemporaryDirectory = _WorkspaceTemporaryDirectory  # type: ignore[assignment]
