from __future__ import annotations

from conftest import pytest_collection_modifyitems


class _FakeItem:
    def __init__(self, *keywords: str) -> None:
        self.keywords = {key: True for key in keywords}
        self.markers: list[object] = []

    def add_marker(self, marker: object) -> None:
        self.markers.append(marker)


def test_external_dependency_markers_skip_without_env(monkeypatch):
    monkeypatch.delenv("WM_TEST_DB_HOST", raising=False)
    monkeypatch.delenv("WM_TEST_BRIDGELAB", raising=False)
    unit = _FakeItem("unit")
    db = _FakeItem("db_integration")
    content = _FakeItem("content_plan")
    bridge = _FakeItem("bridge_contract")

    pytest_collection_modifyitems(object(), [unit, db, content, bridge])  # type: ignore[arg-type]

    assert len(unit.markers) == 0
    assert len(db.markers) == 1
    assert len(content.markers) == 1
    assert len(bridge.markers) == 1


def test_external_dependency_markers_run_when_env_enabled(monkeypatch):
    monkeypatch.setenv("WM_TEST_DB_HOST", "127.0.0.1")
    monkeypatch.setenv("WM_TEST_BRIDGELAB", "1")
    db = _FakeItem("db_integration")
    content = _FakeItem("content_plan")
    bridge = _FakeItem("bridge_contract")

    pytest_collection_modifyitems(object(), [db, content, bridge])  # type: ignore[arg-type]

    assert len(db.markers) == 0
    assert len(content.markers) == 0
    assert len(bridge.markers) == 0
