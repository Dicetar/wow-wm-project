from __future__ import annotations

import unittest
from typing import Any

from wm.config import Settings
from wm.context.snapshot import NativeContextSnapshotRequester, _render_summary
from wm.db.mysql_cli import MysqlCliError
from wm.sources.native_bridge.actions import NativeBridgeActionRequest


class ContextSnapshotRequesterTests(unittest.TestCase):
    def test_request_reports_working_when_new_snapshot_appears(self) -> None:
        client = _FakeMysqlClient(snapshot_rows=[_snapshot_row()])
        action_client = _FakeActionClient(wait_status="done")
        requester = NativeContextSnapshotRequester(
            client=client,  # type: ignore[arg-type]
            settings=Settings(),
            action_client=action_client,  # type: ignore[arg-type]
        )

        proof = requester.request(
            player_guid=5406,
            idempotency_key="snapshot:test",
            timeout_seconds=0,
        )

        self.assertEqual(proof.status, "WORKING")
        self.assertEqual(proof.snapshot["snapshot_id"] if proof.snapshot else None, 91)
        self.assertEqual(action_client.submitted["action_kind"], "context_snapshot_request")
        self.assertEqual(action_client.submitted["payload"]["context_kind"], "nearby")

    def test_request_reports_partial_when_action_done_but_no_snapshot_appears(self) -> None:
        client = _FakeMysqlClient(snapshot_rows=[])
        requester = NativeContextSnapshotRequester(
            client=client,  # type: ignore[arg-type]
            settings=Settings(),
            action_client=_FakeActionClient(wait_status="done"),  # type: ignore[arg-type]
        )

        proof = requester.request(
            player_guid=5406,
            idempotency_key="snapshot:test",
            timeout_seconds=0,
        )

        self.assertEqual(proof.status, "PARTIAL")
        self.assertIsNone(proof.snapshot)
        self.assertTrue(any("context_snapshot_request reached done" in note for note in proof.notes))

    def test_request_reports_partial_when_player_is_offline(self) -> None:
        client = _FakeMysqlClient(snapshot_rows=[])
        requester = NativeContextSnapshotRequester(
            client=client,  # type: ignore[arg-type]
            settings=Settings(),
            action_client=_FakeActionClient(wait_status="failed", error_text="player_not_online"),  # type: ignore[arg-type]
        )

        proof = requester.request(
            player_guid=5406,
            idempotency_key="snapshot:test",
            timeout_seconds=0,
        )

        self.assertEqual(proof.status, "PARTIAL")
        self.assertTrue(any("player_not_online" in note for note in proof.notes))

    def test_request_reports_partial_without_submitting_when_snapshot_table_missing(self) -> None:
        action_client = _FakeActionClient(wait_status="done")
        requester = NativeContextSnapshotRequester(
            client=_FakeMysqlClient(snapshot_rows=[], fail_max=True),  # type: ignore[arg-type]
            settings=Settings(),
            action_client=action_client,  # type: ignore[arg-type]
        )

        proof = requester.request(player_guid=5406, idempotency_key="snapshot:test")

        self.assertEqual(proof.status, "PARTIAL")
        self.assertFalse(action_client.was_submitted)
        self.assertTrue(any(note.startswith("snapshot_table:") for note in proof.notes))

    def test_summary_is_operator_readable(self) -> None:
        summary = _render_summary(
            {
                "status": "PARTIAL",
                "player_guid": 5406,
                "idempotency_key": "snapshot:test",
                "action_request": {"request_id": 12, "status": "done"},
                "snapshot": None,
                "notes": ["missing"],
            }
        )

        self.assertIn("status: PARTIAL", summary)
        self.assertIn("action_request_id: 12", summary)
        self.assertIn("snapshot_id: None", summary)


class _FakeMysqlClient:
    def __init__(self, *, snapshot_rows: list[dict[str, Any]], fail_max: bool = False) -> None:
        self.snapshot_rows = snapshot_rows
        self.fail_max = fail_max
        self.queries: list[str] = []

    def query(
        self,
        *,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        sql: str,
    ) -> list[dict[str, Any]]:
        del host, port, user, password, database
        self.queries.append(sql)
        if "MAX(SnapshotID)" in sql:
            if self.fail_max:
                raise MysqlCliError("wm_bridge_context_snapshot missing")
            return [{"SnapshotID": "90"}]
        if "SnapshotID >" in sql:
            return list(self.snapshot_rows)
        return []


class _FakeActionClient:
    def __init__(self, *, wait_status: str, error_text: str | None = None) -> None:
        self.wait_status = wait_status
        self.error_text = error_text
        self.submitted: dict[str, Any] = {}
        self.was_submitted = False

    def submit(self, **kwargs: Any) -> NativeBridgeActionRequest:
        self.was_submitted = True
        self.submitted = kwargs
        return _request(status="pending")

    def wait(self, *, request_id: int, timeout_seconds: float, poll_seconds: float) -> NativeBridgeActionRequest:
        del request_id, timeout_seconds, poll_seconds
        return _request(status=self.wait_status, error_text=self.error_text)


def _request(*, status: str, error_text: str | None = None) -> NativeBridgeActionRequest:
    return NativeBridgeActionRequest(
        request_id=12,
        idempotency_key="snapshot:test",
        player_guid=5406,
        action_kind="context_snapshot_request",
        payload={"context_kind": "nearby", "radius": 40},
        status=status,
        created_by="test",
        risk_level="low",
        error_text=error_text,
    )


def _snapshot_row() -> dict[str, Any]:
    return {
        "SnapshotID": "91",
        "RequestID": "22",
        "OccurredAt": "2026-04-14 12:00:00",
        "PlayerGUID": "5406",
        "ContextKind": "nearby",
        "Radius": "40",
        "MapID": "0",
        "ZoneID": "12",
        "AreaID": "87",
        "Source": "native_bridge",
        "PayloadJSON": '{"nearby_creatures":[]}',
    }


if __name__ == "__main__":
    unittest.main()
