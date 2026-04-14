from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import time
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient, MysqlCliError
from wm.sources.native_bridge.actions import NativeBridgeActionClient, NativeBridgeActionRequest
from wm.sources.native_bridge.actions import TERMINAL_ACTION_STATUSES


@dataclass(slots=True)
class NativeContextSnapshotProof:
    player_guid: int
    idempotency_key: str
    action_request: dict[str, Any] | None
    snapshot: dict[str, Any] | None
    status: str
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class NativeContextSnapshotRequester:
    def __init__(
        self,
        *,
        client: MysqlCliClient,
        settings: Settings,
        action_client: NativeBridgeActionClient | None = None,
    ) -> None:
        self.client = client
        self.settings = settings
        self.action_client = action_client or NativeBridgeActionClient(client=client, settings=settings)

    def request(
        self,
        *,
        player_guid: int,
        context_kind: str = "nearby",
        radius: int = 40,
        idempotency_key: str | None = None,
        created_by: str = "manual",
        wait_action: bool = True,
        wait_snapshot: bool = True,
        timeout_seconds: float = 10.0,
        poll_seconds: float = 0.25,
    ) -> NativeContextSnapshotProof:
        notes: list[str] = []
        guid = int(player_guid)
        idem = idempotency_key or f"context-snapshot:{guid}:{int(time.time())}"
        before_snapshot_id = self._latest_snapshot_id(player_guid=guid, notes=notes)
        if before_snapshot_id is None:
            return NativeContextSnapshotProof(
                player_guid=guid,
                idempotency_key=idem,
                action_request=None,
                snapshot=None,
                status="PARTIAL",
                notes=notes,
            )

        payload = {
            "context_kind": str(context_kind),
            "radius": int(radius),
            "requested_by": str(created_by),
        }
        try:
            action = self.action_client.submit(
                idempotency_key=idem,
                player_guid=guid,
                action_kind="context_snapshot_request",
                payload=payload,
                created_by=str(created_by),
                risk_level="low",
                expires_seconds=max(30, int(timeout_seconds) + 30),
                max_attempts=3,
                priority=5,
            )
            if wait_action:
                action = self.action_client.wait(
                    request_id=action.request_id,
                    timeout_seconds=timeout_seconds,
                    poll_seconds=poll_seconds,
                )
        except MysqlCliError as exc:
            notes.append(f"native_action: {str(exc).strip() or type(exc).__name__}")
            return NativeContextSnapshotProof(
                player_guid=guid,
                idempotency_key=idem,
                action_request=None,
                snapshot=None,
                status="BROKEN",
                notes=notes,
            )

        snapshot: dict[str, Any] | None = None
        if wait_snapshot:
            snapshot = self._wait_for_snapshot_after(
                player_guid=guid,
                min_snapshot_id=before_snapshot_id,
                timeout_seconds=timeout_seconds,
                poll_seconds=poll_seconds,
                notes=notes,
            )

        status = _proof_status(action=action, snapshot=snapshot, notes=notes)
        return NativeContextSnapshotProof(
            player_guid=guid,
            idempotency_key=idem,
            action_request=action.to_dict(),
            snapshot=snapshot,
            status=status,
            notes=notes,
        )

    def _latest_snapshot_id(self, *, player_guid: int, notes: list[str]) -> int | None:
        try:
            rows = self._query_world(
                "SELECT COALESCE(MAX(SnapshotID), 0) AS SnapshotID "
                "FROM wm_bridge_context_snapshot "
                f"WHERE PlayerGUID = {int(player_guid)}"
            )
        except MysqlCliError as exc:
            notes.append(f"snapshot_table: {str(exc).strip() or type(exc).__name__}")
            return None
        if not rows:
            return 0
        return int(rows[0].get("SnapshotID") or 0)

    def _wait_for_snapshot_after(
        self,
        *,
        player_guid: int,
        min_snapshot_id: int,
        timeout_seconds: float,
        poll_seconds: float,
        notes: list[str],
    ) -> dict[str, Any] | None:
        deadline = time.monotonic() + max(0.0, float(timeout_seconds))
        while True:
            snapshot = self._load_snapshot_after(player_guid=player_guid, min_snapshot_id=min_snapshot_id, notes=notes)
            if snapshot is not None:
                return snapshot
            if time.monotonic() >= deadline:
                notes.append("snapshot_wait: no wm_bridge_context_snapshot row appeared before timeout.")
                return None
            time.sleep(max(0.05, float(poll_seconds)))

    def _load_snapshot_after(
        self,
        *,
        player_guid: int,
        min_snapshot_id: int,
        notes: list[str],
    ) -> dict[str, Any] | None:
        try:
            rows = self._query_world(
                "SELECT SnapshotID, RequestID, OccurredAt, PlayerGUID, ContextKind, Radius, MapID, ZoneID, AreaID, Source, PayloadJSON "
                "FROM wm_bridge_context_snapshot "
                f"WHERE PlayerGUID = {int(player_guid)} "
                f"AND SnapshotID > {int(min_snapshot_id)} "
                "ORDER BY SnapshotID DESC LIMIT 1"
            )
        except MysqlCliError as exc:
            notes.append(f"snapshot_load: {str(exc).strip() or type(exc).__name__}")
            return None
        if not rows:
            return None
        row = rows[0]
        return {
            "snapshot_id": _int_or_none(row.get("SnapshotID")),
            "request_id": _int_or_none(row.get("RequestID")),
            "occurred_at": _str_or_none(row.get("OccurredAt")),
            "player_guid": _int_or_none(row.get("PlayerGUID")),
            "context_kind": _str_or_none(row.get("ContextKind")),
            "radius": _int_or_none(row.get("Radius")),
            "map_id": _int_or_none(row.get("MapID")),
            "zone_id": _int_or_none(row.get("ZoneID")),
            "area_id": _int_or_none(row.get("AreaID")),
            "source": _str_or_none(row.get("Source")),
            "payload": _parse_json_value(row.get("PayloadJSON")),
        }

    def _query_world(self, sql: str) -> list[dict[str, Any]]:
        return self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=sql,
        )


def _proof_status(
    *,
    action: NativeBridgeActionRequest,
    snapshot: dict[str, Any] | None,
    notes: list[str],
) -> str:
    if snapshot is not None:
        return "WORKING"
    if action.status in {"failed", "rejected", "expired"}:
        return "BROKEN"
    if action.status == "done":
        notes.append(
            "native_action: context_snapshot_request reached done, but current native code only queues "
            "wm_bridge_context_request unless a snapshot writer is present."
        )
    elif action.status not in TERMINAL_ACTION_STATUSES:
        notes.append(f"native_action: request remained {action.status} before timeout.")
    return "PARTIAL"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.context.snapshot")
    parser.add_argument("--player-guid", type=int, required=True)
    parser.add_argument("--context-kind", default="nearby")
    parser.add_argument("--radius", type=int, default=40)
    parser.add_argument("--idempotency-key")
    parser.add_argument("--created-by", default="manual")
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--poll-seconds", type=float, default=0.25)
    parser.add_argument("--no-wait-action", action="store_true")
    parser.add_argument("--no-wait-snapshot", action="store_true")
    parser.add_argument("--summary", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    requester = NativeContextSnapshotRequester(client=MysqlCliClient(), settings=settings)
    proof = requester.request(
        player_guid=int(args.player_guid),
        context_kind=str(args.context_kind),
        radius=int(args.radius),
        idempotency_key=args.idempotency_key,
        created_by=str(args.created_by),
        wait_action=not bool(args.no_wait_action),
        wait_snapshot=not bool(args.no_wait_snapshot),
        timeout_seconds=float(args.timeout_seconds),
        poll_seconds=float(args.poll_seconds),
    )
    payload = proof.to_dict()
    if args.summary:
        print(_render_summary(payload))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if proof.status == "WORKING" else 2


def _render_summary(payload: dict[str, Any]) -> str:
    action = payload.get("action_request") or {}
    snapshot = payload.get("snapshot") or {}
    return "\n".join(
        [
            f"status: {payload.get('status')}",
            f"player_guid: {payload.get('player_guid')}",
            f"idempotency_key: {payload.get('idempotency_key')}",
            f"action_request_id: {action.get('request_id')}",
            f"action_status: {action.get('status')}",
            f"snapshot_id: {snapshot.get('snapshot_id')}",
            f"notes: {len(payload.get('notes') or [])}",
        ]
    )


def _parse_json_value(value: Any) -> Any:
    if value in (None, ""):
        return None
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return {"raw": str(value)}


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _str_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
