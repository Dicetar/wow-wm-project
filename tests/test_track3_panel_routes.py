"""Tests for new Track III panel API routes."""
from __future__ import annotations


def _make_app():
    from pathlib import Path
    import tempfile
    from wm.panel.server import PanelApp
    from wm.panel.state import PanelState
    tmp = Path(tempfile.mkdtemp())
    return PanelApp(state=PanelState(tmp))


def test_health_route():
    app = _make_app()
    status, body = app.get("/api/health")
    assert status == 200
    assert body["ok"] is True


def test_feature_status_route():
    app = _make_app()
    status, body = app.get("/api/feature_status")
    assert status == 200
    assert "total_count" in body


def test_living_readiness_route():
    app = _make_app()
    status, body = app.get("/api/living_readiness")
    assert status == 200
    assert "dry_run_results" in body


def test_proposals_route():
    app = _make_app()
    status, body = app.get("/api/proposals")
    assert status == 200
    assert "proposals" in body


def test_llm_adopt_post():
    app = _make_app()
    status, body = app.post("/api/llm/adopt", {
        "schema_version": "wm.quest_draft.v1",
        "instruction": "test",
        "raw_response": '{"schema_version": "wm.quest_draft.v1"}',
    })
    assert status == 200
    assert body["ok"] is True
