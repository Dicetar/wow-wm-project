"""Tests for the panel approval-gate-UI endpoints (Blocker #1 of the slice).

These cover the /api/slice/* surface that fronts the SliceRuntime built
in slice_demo.py. The factory + discoverer are injected so the tests
don't hit MySQL or the real demo content files.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tempfile
import unittest
from typing import Any

from wm.panel.catalog import CommandCatalog, CommandEntry
from wm.panel.server import PanelApp
from wm.panel.state import PanelState


# --- minimal stand-ins for the SliceRuntime surface ---------------------


@dataclass(slots=True)
class _FakeProposalKind:
    value: str


@dataclass(slots=True)
class _FakeProposal:
    kind: _FakeProposalKind
    payload: dict
    character_guid: int
    narrative_summary: str = ""
    provenance: dict = field(default_factory=dict)
    is_blocked: bool = False
    block_reason: str = ""


@dataclass(slots=True)
class _FakePendingProposal:
    id: int
    proposal: _FakeProposal


@dataclass(slots=True)
class _FakeIssue:
    id: int
    reason: str
    kind: str
    character_guid: int
    payload: dict
    provenance: dict = field(default_factory=dict)


class _FakeApprovalGate:
    def __init__(self) -> None:
        self._pending: list[_FakePendingProposal] = []
        self.approved: list[int] = []
        self.rejected: list[tuple[int, str]] = []

    def pending(self) -> list[_FakePendingProposal]:
        return list(self._pending)

    def approve(self, pid: int) -> Any:
        self.approved.append(pid)
        @dataclass(slots=True)
        class _R:
            ok: bool = True
            detail: dict | None = None
            error: str | None = None
        return _R(ok=True, detail={"applied": pid})

    def reject(self, pid: int, *, reason: str) -> None:
        self.rejected.append((pid, reason))

    def rollback(self, *, artifact_type: str, artifact_entry: int, mode: str = "apply") -> Any:
        self.rolled_back = getattr(self, "rolled_back", [])
        self.rolled_back.append((artifact_type, artifact_entry, mode))
        @dataclass(slots=True)
        class _R:
            ok: bool = True
            detail: dict | None = None
            error: str | None = None
        return _R(ok=True, detail={"artifact_type": artifact_type, "artifact_entry": artifact_entry})


class _FakeIssuesQueue:
    def __init__(self) -> None:
        self._items: list[_FakeIssue] = []

    def list_open(self) -> list[_FakeIssue]:
        return list(self._items)


class _FakeRunnerModule:
    def __init__(self, character_guid: int) -> None:
        self.character_guid = character_guid


class _FakeRunner:
    def __init__(self, character_guid: int) -> None:
        self.module = _FakeRunnerModule(character_guid)
        self.current_beat_id = "b00_onboarding"


@dataclass(slots=True)
class _FakeRuntime:
    character_guid: int
    gate: _FakeApprovalGate = field(default_factory=_FakeApprovalGate)
    issues: _FakeIssuesQueue = field(default_factory=_FakeIssuesQueue)
    runner: _FakeRunner = field(default=None)  # type: ignore[assignment]
    applied_log: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.runner is None:
            self.runner = _FakeRunner(self.character_guid)


class _FakePump:
    def __init__(self) -> None:
        self.calls = 0
        self.last_seen_event_id = 0

    def poll_once(self) -> int:
        self.calls += 1
        return 3 if self.calls == 1 else 0


# --- fixtures -----------------------------------------------------------


def _catalog() -> CommandCatalog:
    return CommandCatalog(
        [
            CommandEntry(
                id="test.read",
                label="Read",
                category="test",
                kind="read_only",
                dry_run_argv=("python", "-c", "print('read')"),
            )
        ]
    )


def _make_app(*, factory=None, discoverer=None, pump_factory=None, marker_discoverer=None) -> PanelApp:
    temp = tempfile.TemporaryDirectory()
    app = PanelApp(
        state=PanelState(Path(temp.name)),
        command_catalog=_catalog(),
        slice_factory=factory,
        slice_discoverer=discoverer,
        slice_pump_factory=pump_factory,
        marker_discoverer=marker_discoverer,
    )
    # keep temp alive for the app's lifetime
    app._test_temp = temp  # type: ignore[attr-defined]
    return app


# --- tests --------------------------------------------------------------


class SliceBootstrapTests(unittest.TestCase):
    def test_bootstrap_with_explicit_character_guid_initializes_runtime(self) -> None:
        seen: dict[str, Any] = {}

        def factory(*, character_guid: int) -> _FakeRuntime:
            seen["character_guid"] = character_guid
            return _FakeRuntime(character_guid=character_guid)

        app = _make_app(factory=factory)

        code, body = app.post("/api/slice/bootstrap", {"character_guid": 5408})

        self.assertEqual(code, 200, body)
        self.assertTrue(body["ok"], body)
        self.assertEqual(body["character_guid"], 5408)
        self.assertEqual(seen["character_guid"], 5408)

    def test_bootstrap_without_guid_discovers_from_spine(self) -> None:
        def factory(*, character_guid: int) -> _FakeRuntime:
            return _FakeRuntime(character_guid=character_guid)

        def discoverer() -> int | None:
            return 5408

        app = _make_app(factory=factory, discoverer=discoverer)

        code, body = app.post("/api/slice/bootstrap", {})

        self.assertEqual(code, 200, body)
        self.assertEqual(body["character_guid"], 5408)

    def test_bootstrap_returns_error_when_discoverer_finds_nothing(self) -> None:
        def factory(*, character_guid: int) -> _FakeRuntime:
            return _FakeRuntime(character_guid=character_guid)

        def discoverer() -> int | None:
            return None

        app = _make_app(factory=factory, discoverer=discoverer)

        code, body = app.post("/api/slice/bootstrap", {})

        self.assertEqual(code, 400)
        self.assertFalse(body["ok"])
        self.assertIn("character_guid", body["error"])


class WmSessionEndpointTests(unittest.TestCase):
    def test_wm_session_bootstrap_with_explicit_guid_persists_session(self) -> None:
        def factory(*, character_guid: int) -> _FakeRuntime:
            return _FakeRuntime(character_guid=character_guid)

        app = _make_app(factory=factory)

        code, body = app.post("/api/wm/session/bootstrap", {"character_guid": 5410, "character_name": "Tester"})

        self.assertEqual(code, 200, body)
        self.assertEqual(body["character_guid"], 5410)
        self.assertEqual(body["session"]["source"], "explicit_guid")
        self.assertEqual(body["session"]["character_name"], "Tester")
        self.assertEqual(app.state.load_session()["character_guid"], 5410)  # type: ignore[index]

    def test_wm_session_bootstrap_from_marker_candidate(self) -> None:
        def factory(*, character_guid: int) -> _FakeRuntime:
            return _FakeRuntime(character_guid=character_guid)

        def marker_discoverer(**_kwargs):
            return [{
                "bridge_event_id": 77,
                "player_guid": 5411,
                "character_name": "MarkerUser",
                "spell_id": 946602,
            }]

        app = _make_app(factory=factory, marker_discoverer=marker_discoverer)

        code, body = app.post("/api/wm/session/bootstrap", {})

        self.assertEqual(code, 200, body)
        self.assertEqual(body["character_guid"], 5411)
        self.assertEqual(body["session"]["source"], "marker")
        self.assertEqual(body["session"]["bridge_event_id"], 77)
        self.assertEqual(body["session"]["character_name"], "MarkerUser")

    def test_wm_marker_scan_returns_candidates(self) -> None:
        seen: dict[str, int] = {}

        def marker_discoverer(**kwargs):
            seen.update({key: int(value) for key, value in kwargs.items()})
            return [{"player_guid": 5412, "bridge_event_id": 88, "spell_id": kwargs["marker_spell_id"]}]

        app = _make_app(marker_discoverer=marker_discoverer)

        code, body = app.get("/api/wm/markers?marker_spell_id=946602&since_seconds=120&limit=3")

        self.assertEqual(code, 200, body)
        self.assertTrue(body["ok"])
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["candidates"][0]["player_guid"], 5412)
        self.assertEqual(seen, {"since_seconds": 120, "limit": 3, "marker_spell_id": 946602})

    def test_wm_session_aliases_share_slice_runtime(self) -> None:
        def factory(*, character_guid: int) -> _FakeRuntime:
            return _FakeRuntime(character_guid=character_guid)

        app = _make_app(factory=factory)
        code, _ = app.post("/api/wm/session/bootstrap", {"character_guid": 5413})
        self.assertEqual(code, 200)

        code, body = app.get("/api/slice/status")
        self.assertEqual(code, 200, body)
        self.assertEqual(body["character_guid"], 5413)

        code, body = app.get("/api/wm/session/status")
        self.assertEqual(code, 200, body)
        self.assertEqual(body["session"]["character_guid"], 5413)

    def test_marker_spell_constant_matches_native_marker_default(self) -> None:
        from wm.panel.slice_wiring import MARKER_SPELL_ID
        from wm.sources.native_bridge.player_marker import DEFAULT_MARKER_SPELL_ID

        self.assertEqual(MARKER_SPELL_ID, DEFAULT_MARKER_SPELL_ID)


class SliceReadEndpointTests(unittest.TestCase):
    def _bootstrap(self, app: PanelApp, *, character_guid: int = 5408) -> _FakeRuntime:
        code, _ = app.post("/api/slice/bootstrap", {"character_guid": character_guid})
        self.assertEqual(code, 200)
        return app._slice  # type: ignore[attr-defined,return-value]

    def _seed_pending(self, rt: _FakeRuntime, *items: tuple[int, str, str, dict]) -> None:
        for pid, kind, narrative, payload in items:
            rt.gate._pending.append(_FakePendingProposal(
                id=pid,
                proposal=_FakeProposal(
                    kind=_FakeProposalKind(value=kind),
                    payload=payload,
                    character_guid=rt.character_guid,
                    narrative_summary=narrative,
                    provenance={"source": "test"},
                ),
            ))

    def _seed_issues(self, rt: _FakeRuntime, *items: tuple[int, str, str]) -> None:
        for iid, kind, reason in items:
            rt.issues._items.append(_FakeIssue(
                id=iid, reason=reason, kind=kind,
                character_guid=rt.character_guid,
                payload={"x": iid}, provenance={},
            ))

    def test_status_returns_404_before_bootstrap(self) -> None:
        app = _make_app()
        code, body = app.get("/api/slice/status")
        self.assertEqual(code, 404)
        self.assertFalse(body["ok"])

    def test_status_after_bootstrap_summarizes_counts(self) -> None:
        def factory(*, character_guid: int) -> _FakeRuntime:
            return _FakeRuntime(character_guid=character_guid)

        app = _make_app(factory=factory)
        rt = self._bootstrap(app)
        self._seed_pending(rt, (1, "quest", "open b01", {"q": 1}), (2, "ability", "grant", {"a": 1}))
        self._seed_issues(rt, (1, "quest", "blocked"))
        rt.applied_log.append({"kind": "quest", "narrative": "b00"})

        code, body = app.get("/api/slice/status")

        self.assertEqual(code, 200, body)
        self.assertEqual(body["character_guid"], 5408)
        self.assertEqual(body["current_beat"], "b00_onboarding")
        self.assertEqual(body["pending_count"], 2)
        self.assertEqual(body["issues_count"], 1)
        self.assertEqual(body["applied_log_size"], 1)

    def test_pending_returns_list_of_serialized_proposals(self) -> None:
        def factory(*, character_guid: int) -> _FakeRuntime:
            return _FakeRuntime(character_guid=character_guid)

        app = _make_app(factory=factory)
        rt = self._bootstrap(app)
        self._seed_pending(rt,
                            (1, "quest", "open zone intro", {"quest_id": 783}),
                            (2, "ability", "grant shadow pulse", {"ability_id": "x"}))

        code, body = app.get("/api/slice/pending")

        self.assertEqual(code, 200)
        self.assertEqual(len(body["pending"]), 2)
        first = body["pending"][0]
        self.assertEqual(first["id"], 1)
        self.assertEqual(first["kind"], "quest")
        self.assertEqual(first["character_guid"], 5408)
        self.assertEqual(first["narrative_summary"], "open zone intro")
        self.assertEqual(first["payload"], {"quest_id": 783})
        self.assertEqual(first["provenance"], {"source": "test"})

    def test_inbox_aggregates_pending_across_all_lanes(self) -> None:
        def factory(*, character_guid: int) -> _FakeRuntime:
            return _FakeRuntime(character_guid=character_guid)

        app = _make_app(factory=factory)
        rt = self._bootstrap(app)
        self._seed_pending(rt,
                            (1, "quest", "open zone intro", {"q": 1}),
                            (2, "item", "grant lens", {"item_entry": 910013}),
                            (3, "spell", "echo blast", {"spell_entry": 946099}))

        code, body = app.get("/api/wm/inbox")

        self.assertEqual(code, 200, body)
        self.assertEqual(len(body["pending"]), 3)
        self.assertEqual({p["kind"] for p in body["pending"]}, {"quest", "item", "spell"})

    def test_inbox_filters_by_kind(self) -> None:
        def factory(*, character_guid: int) -> _FakeRuntime:
            return _FakeRuntime(character_guid=character_guid)

        app = _make_app(factory=factory)
        rt = self._bootstrap(app)
        self._seed_pending(rt,
                            (1, "quest", "q", {"q": 1}),
                            (2, "spell", "s", {"spell_entry": 946099}))

        code, body = app.get("/api/wm/inbox?kind=spell")

        self.assertEqual(code, 200, body)
        self.assertEqual(len(body["pending"]), 1)
        self.assertEqual(body["pending"][0]["kind"], "spell")

    def test_rollback_endpoint_drives_gate_rollback(self) -> None:
        def factory(*, character_guid: int) -> _FakeRuntime:
            return _FakeRuntime(character_guid=character_guid)

        app = _make_app(factory=factory)
        rt = self._bootstrap(app)

        code, body = app.post("/api/wm/rollback", {"artifact_type": "spell", "artifact_entry": 946099})

        self.assertEqual(code, 200, body)
        self.assertTrue(body["ok"], body)
        self.assertEqual(rt.gate.rolled_back, [("spell", 946099, "apply")])

    def test_issues_returns_list_of_open_issues(self) -> None:
        def factory(*, character_guid: int) -> _FakeRuntime:
            return _FakeRuntime(character_guid=character_guid)

        app = _make_app(factory=factory)
        rt = self._bootstrap(app)
        self._seed_issues(rt, (7, "quest", "compiler_exception: boom"))

        code, body = app.get("/api/slice/issues")

        self.assertEqual(code, 200)
        self.assertEqual(len(body["issues"]), 1)
        issue = body["issues"][0]
        self.assertEqual(issue["id"], 7)
        self.assertEqual(issue["reason"], "compiler_exception: boom")
        self.assertEqual(issue["kind"], "quest")

    def test_log_returns_recent_applied_entries(self) -> None:
        def factory(*, character_guid: int) -> _FakeRuntime:
            return _FakeRuntime(character_guid=character_guid)

        app = _make_app(factory=factory)
        rt = self._bootstrap(app)
        for n in range(50):
            rt.applied_log.append({"kind": "quest", "n": n})

        code, body = app.get("/api/slice/log")

        self.assertEqual(code, 200)
        # default limit returns the tail; expose all but cap at 50 by default
        self.assertLessEqual(len(body["log"]), 50)
        self.assertGreater(len(body["log"]), 0)
        # most-recent-last ordering matches applied_log
        self.assertEqual(body["log"][-1]["n"], 49)


class SliceSpineDiscoveryTests(unittest.TestCase):
    def test_picks_player_guid_from_most_recent_applied_marker_row(self) -> None:
        from wm.panel.slice_wiring import discover_guid_from_rows

        # rows arrive ordered DESC by BridgeEventID (most recent first)
        rows = [
            {"PlayerGUID": "5408", "BridgeEventID": "200"},
            {"PlayerGUID": "5406", "BridgeEventID": "100"},
        ]
        self.assertEqual(discover_guid_from_rows(rows), 5408)

    def test_returns_none_when_no_rows(self) -> None:
        from wm.panel.slice_wiring import discover_guid_from_rows

        self.assertIsNone(discover_guid_from_rows([]))

    def test_skips_rows_with_unparseable_guid(self) -> None:
        from wm.panel.slice_wiring import discover_guid_from_rows

        rows = [
            {"PlayerGUID": "NULL", "BridgeEventID": "300"},
            {"PlayerGUID": "5408", "BridgeEventID": "200"},
        ]
        self.assertEqual(discover_guid_from_rows(rows), 5408)


class SliceActionEndpointTests(unittest.TestCase):
    def _make(self) -> tuple[PanelApp, _FakeRuntime, _FakePump]:
        pump = _FakePump()

        def factory(*, character_guid: int) -> _FakeRuntime:
            return _FakeRuntime(character_guid=character_guid)

        def pump_factory(rt: _FakeRuntime) -> _FakePump:
            return pump

        app = _make_app(factory=factory, pump_factory=pump_factory)
        code, _ = app.post("/api/slice/bootstrap", {"character_guid": 5408})
        self.assertEqual(code, 200)
        return app, app._slice, pump  # type: ignore[return-value]

    def test_approve_calls_gate_approve_and_reports_ok(self) -> None:
        app, rt, _pump = self._make()
        rt.gate._pending.append(_FakePendingProposal(
            id=7,
            proposal=_FakeProposal(
                kind=_FakeProposalKind(value="quest"),
                payload={"q": 1}, character_guid=5408,
            ),
        ))

        code, body = app.post("/api/slice/approve", {"id": 7})

        self.assertEqual(code, 200, body)
        self.assertTrue(body["ok"])
        self.assertEqual(body["id"], 7)
        self.assertEqual(rt.gate.approved, [7])

    def test_approve_missing_id_returns_400(self) -> None:
        app, _rt, _pump = self._make()

        code, body = app.post("/api/slice/approve", {})

        self.assertEqual(code, 400)
        self.assertFalse(body["ok"])

    def test_reject_records_reason(self) -> None:
        app, rt, _pump = self._make()

        code, body = app.post("/api/slice/reject", {"id": 3, "reason": "operator-rejected"})

        self.assertEqual(code, 200, body)
        self.assertTrue(body["ok"])
        self.assertEqual(rt.gate.rejected, [(3, "operator-rejected")])

    def test_reject_defaults_reason_when_not_provided(self) -> None:
        app, rt, _pump = self._make()

        code, body = app.post("/api/slice/reject", {"id": 9})

        self.assertEqual(code, 200, body)
        self.assertEqual(len(rt.gate.rejected), 1)
        self.assertEqual(rt.gate.rejected[0][0], 9)

    def test_poll_drives_pump_and_returns_count(self) -> None:
        app, _rt, pump = self._make()

        code, body = app.post("/api/slice/poll", {})

        self.assertEqual(code, 200, body)
        self.assertEqual(body["events_seen"], 3)
        self.assertEqual(pump.calls, 1)

        # second call returns 0 events but still 200
        code, body = app.post("/api/slice/poll", {})
        self.assertEqual(code, 200)
        self.assertEqual(body["events_seen"], 0)
        self.assertEqual(pump.calls, 2)

    def test_poll_without_pump_returns_409(self) -> None:
        def factory(*, character_guid: int) -> _FakeRuntime:
            return _FakeRuntime(character_guid=character_guid)

        app = _make_app(factory=factory)  # no pump_factory
        code, _ = app.post("/api/slice/bootstrap", {"character_guid": 5408})
        self.assertEqual(code, 200)

        code, body = app.post("/api/slice/poll", {})

        self.assertEqual(code, 409)
        self.assertFalse(body["ok"])

    def test_action_endpoints_404_before_bootstrap(self) -> None:
        app = _make_app()

        for path in ("/api/slice/approve", "/api/slice/reject", "/api/slice/poll"):
            code, body = app.post(path, {"id": 1, "reason": "x"})
            self.assertEqual(code, 404, f"{path} -> {body}")


def test_wm_session_overview_uses_active_session_guid():
    from wm.panel.server import PanelApp
    from wm.panel.state import PanelState
    from wm.character.reader import CharacterStateBundle
    import tempfile
    from pathlib import Path

    captured = {}

    def fake_reader(player_guid: int) -> CharacterStateBundle:
        captured["guid"] = player_guid
        return CharacterStateBundle(status="WORKING", arc_states=[object()])

    with tempfile.TemporaryDirectory() as d:
        state = PanelState(Path(d))
        state.ensure()
        state.save_session({"character_guid": 5408, "marker_spell_id": 946602})
        app = PanelApp(state=state, character_reader=fake_reader)
        status, payload = app.get("/api/wm/session/overview")

    assert status == 200
    assert payload["ok"] is True
    assert captured["guid"] == 5408
    assert payload["overview"]["player_guid"] == 5408
    assert payload["overview"]["status"] == "WORKING"
    assert payload["overview"]["counts"]["arc_states"] == 1


def test_wm_session_overview_400_without_active_session():
    from wm.panel.server import PanelApp
    from wm.panel.state import PanelState
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        state = PanelState(Path(d))
        state.ensure()
        app = PanelApp(state=state, character_reader=lambda player_guid: None)
        status, payload = app.get("/api/wm/session/overview")
    assert status == 400
    assert payload["ok"] is False


def test_wm_session_overview_reader_failure_returns_200_ok_false():
    from wm.panel.server import PanelApp
    from wm.panel.state import PanelState
    import tempfile
    from pathlib import Path

    def bad_reader(player_guid: int):
        raise RuntimeError("db gone")

    with tempfile.TemporaryDirectory() as d:
        state = PanelState(Path(d))
        state.ensure()
        state.save_session({"character_guid": 5408})
        app = PanelApp(state=state, character_reader=bad_reader)
        status, payload = app.get("/api/wm/session/overview")
    assert status == 200
    assert payload["ok"] is False
    assert payload["overview"] is None
    assert "character read failed" in payload["error"]


if __name__ == "__main__":
    unittest.main()
