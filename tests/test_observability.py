from __future__ import annotations

import json

from wm.observability import WmObservabilityStore


def test_observability_records_proofs_and_timeline(tmp_path):
    store = WmObservabilityStore(root=tmp_path / "obs", autoplay_root=tmp_path / "autoplay")

    proof = store.record_proof(proof_kind="chat_action", mode="dry-run", player_guid=5408)
    proofs = store.list_proofs()
    timeline = store.list_timeline()

    assert proof["proof_kind"] == "chat_action"
    assert proof["status"] == "planned"
    assert proofs[0]["proof_id"] == proof["proof_id"]
    assert timeline[0]["kind"] == "proof"


def test_observability_includes_runtime_incidents(tmp_path):
    store = WmObservabilityStore(root=tmp_path / "obs")
    runtime = {
        "incidents": [
            {"kind": "duplicate_service", "severity": "error", "service": "panel", "message": "duplicate", "at": "2026-01-01T00:00:00Z"}
        ]
    }

    incidents = store.list_incidents(runtime_status=runtime)

    assert incidents[0]["source"] == "runtime"
    assert incidents[0]["service"] == "panel"


def test_observability_timeline_summarizes_autoplay_journal(tmp_path):
    autoplay_root = tmp_path / "autoplay"
    journal = autoplay_root / "journal"
    journal.mkdir(parents=True)
    (journal / "20260101000000-chat.json").write_text(json.dumps({
        "kind": "chat",
        "at": "2026-01-01T00:00:00Z",
        "reply": {"message": "The road ahead is clear."},
    }), encoding="utf-8")
    store = WmObservabilityStore(root=tmp_path / "obs", autoplay_root=autoplay_root)

    timeline = store.list_timeline()

    assert timeline[0]["kind"] == "autoplay.chat"
    assert timeline[0]["summary"] == "Chat: The road ahead is clear."
