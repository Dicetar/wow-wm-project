from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import time
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.events.store import _sql_int_or_null
from wm.events.store import _sql_string
from wm.events.store import _sql_string_or_null
from wm.sources.native_bridge.action_kinds import NATIVE_ACTION_KIND_BY_ID


TERMINAL_ACTION_STATUSES = {"done", "failed", "rejected", "expired"}


@dataclass(slots=True)
class NativeBridgeActionRequest:
    request_id: int
    idempotency_key: str
    player_guid: int
    action_kind: str
    payload: dict[str, Any]
    status: str
    created_by: str
    risk_level: str
    created_at: str | None = None
    claimed_at: str | None = None
    processed_at: str | None = None
    result: dict[str, Any] = field(default_factory=dict)
    error_text: str | None = None
    claim_expires_at: str | None = None
    attempt_count: int = 0
    max_attempts: int = 3
    sequence_id: str | None = None
    sequence_order: int = 0
    wait_for_prior: bool = False
    priority: int = 5
    purge_after: str | None = None
    target_map_id: int | None = None
    target_x: float | None = None
    target_y: float | None = None
    target_z: float | None = None
    target_o: float | None = None
    target_player_guid: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class NativeBridgeActionClient:
    def __init__(self, *, client: MysqlCliClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def submit(
        self,
        *,
        idempotency_key: str,
        player_guid: int,
        action_kind: str,
        payload: dict[str, Any] | None = None,
        created_by: str = "wm",
        risk_level: str = "low",
        expires_seconds: int | None = 60,
        max_attempts: int = 3,
        sequence_id: str | None = None,
        sequence_order: int = 0,
        wait_for_prior: bool = False,
        priority: int = 5,
        purge_after_seconds: int | None = None,
        target_map_id: int | None = None,
        target_x: float | None = None,
        target_y: float | None = None,
        target_z: float | None = None,
        target_o: float | None = None,
        target_player_guid: int | None = None,
    ) -> NativeBridgeActionRequest:
        if action_kind not in NATIVE_ACTION_KIND_BY_ID:
            raise ValueError(f"Unknown native bridge action kind: {action_kind}")
        payload_json = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)
        expires_sql = "NULL" if expires_seconds is None else f"DATE_ADD(NOW(), INTERVAL {int(expires_seconds)} SECOND)"
        purge_after_sql = "NULL" if purge_after_seconds is None else f"DATE_ADD(NOW(), INTERVAL {int(purge_after_seconds)} SECOND)"
        sql = (
            "INSERT INTO wm_bridge_action_request ("
            "IdempotencyKey, PlayerGUID, ActionKind, PayloadJSON, Status, CreatedBy, RiskLevel, ExpiresAt, "
            "MaxAttempts, SequenceID, SequenceOrder, WaitForPrior, Priority, PurgeAfter, "
            "TargetMapID, TargetX, TargetY, TargetZ, TargetO, TargetPlayerGUID"
            ") VALUES ("
            f"{_sql_string(idempotency_key)}, "
            f"{int(player_guid)}, "
            f"{_sql_string(action_kind)}, "
            f"{_sql_string(payload_json)}, "
            "'pending', "
            f"{_sql_string(created_by)}, "
            f"{_sql_string(risk_level)}, "
            f"{expires_sql}, "
            f"{max(1, int(max_attempts))}, "
            f"{_sql_string_or_null(sequence_id)}, "
            f"{int(sequence_order)}, "
            f"{1 if wait_for_prior else 0}, "
            f"{max(1, min(9, int(priority)))}, "
            f"{purge_after_sql}, "
            f"{_sql_int_or_null(target_map_id)}, "
            f"{_sql_float_or_null(target_x)}, "
            f"{_sql_float_or_null(target_y)}, "
            f"{_sql_float_or_null(target_z)}, "
            f"{_sql_float_or_null(target_o)}, "
            f"{_sql_int_or_null(target_player_guid)}"
            ") ON DUPLICATE KEY UPDATE "
            "RequestID = LAST_INSERT_ID(RequestID), "
            "UpdatedAt = CURRENT_TIMESTAMP; "
            "SELECT LAST_INSERT_ID() AS RequestID"
        )
        rows = self._query_world(sql)
        request_id = int(rows[0]["RequestID"]) if rows else 0
        if request_id <= 0:
            existing = self.get_by_idempotency_key(idempotency_key=idempotency_key)
            if existing is None:
                raise RuntimeError("Native bridge action request was not created and no duplicate row was found.")
            return existing
        result = self.get(request_id=request_id)
        if result is None:
            raise RuntimeError(f"Native bridge action request {request_id} was created but could not be loaded.")
        return result

    def get(self, *, request_id: int) -> NativeBridgeActionRequest | None:
        rows = self._query_world(
            _request_select_sql() + " "
            "FROM wm_bridge_action_request "
            f"WHERE RequestID = {int(request_id)}"
        )
        return _row_to_request(rows[0]) if rows else None

    def get_by_idempotency_key(self, *, idempotency_key: str) -> NativeBridgeActionRequest | None:
        rows = self._query_world(
            _request_select_sql() + " "
            "FROM wm_bridge_action_request "
            f"WHERE IdempotencyKey = {_sql_string(idempotency_key)} "
            "LIMIT 1"
        )
        return _row_to_request(rows[0]) if rows else None

    def list_requests(
        self,
        *,
        player_guid: int | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> list[NativeBridgeActionRequest]:
        predicates: list[str] = []
        if player_guid is not None:
            predicates.append(f"PlayerGUID = {int(player_guid)}")
        if status is not None:
            predicates.append(f"Status = {_sql_string(status)}")
        where_clause = f"WHERE {' AND '.join(predicates)} " if predicates else ""
        rows = self._query_world(
            _request_select_sql() + " "
            "FROM wm_bridge_action_request "
            f"{where_clause}"
            "ORDER BY RequestID DESC "
            f"LIMIT {int(limit)}"
        )
        return [_row_to_request(row) for row in rows]

    def recover_stale_claims(self) -> dict[str, int]:
        requeued = self._query_world(
            "UPDATE wm_bridge_action_request "
            "SET Status = 'pending', ClaimedAt = NULL, ClaimExpiresAt = NULL, ErrorText = 'claim_expired_requeued', "
            "UpdatedAt = CURRENT_TIMESTAMP "
            "WHERE Status = 'claimed' AND ClaimExpiresAt IS NOT NULL AND ClaimExpiresAt <= NOW() AND AttemptCount < MaxAttempts; "
            "SELECT ROW_COUNT() AS Requeued"
        )
        failed = self._query_world(
            "UPDATE wm_bridge_action_request "
            "SET Status = 'failed', ProcessedAt = NOW(), ResultJSON = "
            "'{\"ok\":false,\"action_kind\":\"action_queue\",\"message\":\"claim_expired_max_attempts\"}', "
            "ErrorText = 'claim_expired_max_attempts', UpdatedAt = CURRENT_TIMESTAMP "
            "WHERE Status = 'claimed' AND ClaimExpiresAt IS NOT NULL AND ClaimExpiresAt <= NOW() AND AttemptCount >= MaxAttempts; "
            "SELECT ROW_COUNT() AS Failed"
        )
        return {
            "requeued": _int_from_first_row(requeued, "Requeued"),
            "failed": _int_from_first_row(failed, "Failed"),
        }

    def cleanup_terminal_requests(self, *, older_than_seconds: int | None = None, limit: int = 500) -> dict[str, int]:
        predicates = ["Status IN ('done', 'failed', 'rejected', 'expired')"]
        if older_than_seconds is not None:
            predicates.append(f"UpdatedAt <= DATE_SUB(NOW(), INTERVAL {int(older_than_seconds)} SECOND)")
        else:
            predicates.append("PurgeAfter IS NOT NULL AND PurgeAfter <= NOW()")
        rows = self._query_world(
            "DELETE FROM wm_bridge_action_request "
            f"WHERE {' AND '.join(predicates)} "
            "ORDER BY RequestID ASC "
            f"LIMIT {int(limit)}; "
            "SELECT ROW_COUNT() AS Deleted"
        )
        return {"deleted": _int_from_first_row(rows, "Deleted")}

    def wait(self, *, request_id: int, timeout_seconds: float | None = None, poll_seconds: float | None = None) -> NativeBridgeActionRequest:
        timeout = self.settings.native_bridge_action_wait_seconds if timeout_seconds is None else float(timeout_seconds)
        interval = self.settings.native_bridge_action_poll_seconds if poll_seconds is None else float(poll_seconds)
        deadline = time.monotonic() + timeout
        last = self.get(request_id=request_id)
        while last is not None and last.status not in TERMINAL_ACTION_STATUSES and time.monotonic() < deadline:
            time.sleep(max(interval, 0.05))
            last = self.get(request_id=request_id)
        if last is None:
            raise RuntimeError(f"Native bridge action request {request_id} disappeared.")
        return last

    def enable_player_scope(
        self,
        *,
        player_guid: int,
        profile: str = "default",
        enabled: bool = True,
        reason: str | None = None,
        expires_seconds: int | None = None,
    ) -> None:
        expires_sql = "NULL" if expires_seconds is None else f"DATE_ADD(NOW(), INTERVAL {int(expires_seconds)} SECOND)"
        self._query_world(
            "INSERT INTO wm_bridge_player_scope (PlayerGUID, Profile, Enabled, Reason, ExpiresAt) VALUES ("
            f"{int(player_guid)}, {_sql_string(profile)}, {1 if enabled else 0}, {_sql_string_or_null(reason)}, {expires_sql}"
            ") ON DUPLICATE KEY UPDATE "
            "Enabled = VALUES(Enabled), Reason = VALUES(Reason), ExpiresAt = VALUES(ExpiresAt), UpdatedAt = CURRENT_TIMESTAMP"
        )

    def set_action_policy(
        self,
        *,
        action_kind: str,
        profile: str = "default",
        enabled: bool,
        max_risk_level: str | None = None,
        cooldown_ms: int | None = None,
        burst_limit: int | None = None,
        admin_only: bool | None = None,
    ) -> None:
        if action_kind not in NATIVE_ACTION_KIND_BY_ID:
            raise ValueError(f"Unknown native bridge action kind: {action_kind}")
        kind = NATIVE_ACTION_KIND_BY_ID[action_kind]
        self._query_world(
            "INSERT INTO wm_bridge_action_policy ("
            "ActionKind, Profile, Enabled, MaxRiskLevel, CooldownMS, BurstLimit, AdminOnly"
            ") VALUES ("
            f"{_sql_string(action_kind)}, "
            f"{_sql_string(profile)}, "
            f"{1 if enabled else 0}, "
            f"{_sql_string(max_risk_level or kind.default_risk)}, "
            f"{_sql_int_or_null(cooldown_ms)}, "
            f"{_sql_int_or_null(burst_limit)}, "
            f"{1 if (kind.admin_only if admin_only is None else admin_only) else 0}"
            ") ON DUPLICATE KEY UPDATE "
            "Enabled = VALUES(Enabled), MaxRiskLevel = VALUES(MaxRiskLevel), CooldownMS = VALUES(CooldownMS), "
            "BurstLimit = VALUES(BurstLimit), AdminOnly = VALUES(AdminOnly), UpdatedAt = CURRENT_TIMESTAMP"
        )

    def _query_world(self, sql: str) -> list[dict[str, Any]]:
        return self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=sql,
        )


def _row_to_request(row: dict[str, Any]) -> NativeBridgeActionRequest:
    return NativeBridgeActionRequest(
        request_id=int(row["RequestID"]),
        idempotency_key=str(row["IdempotencyKey"]),
        player_guid=int(row["PlayerGUID"]),
        action_kind=str(row["ActionKind"]),
        payload=_parse_json(row.get("PayloadJSON")),
        status=str(row["Status"]),
        created_by=str(row.get("CreatedBy") or ""),
        risk_level=str(row.get("RiskLevel") or "low"),
        created_at=_str_or_none(row.get("CreatedAt")),
        claimed_at=_str_or_none(row.get("ClaimedAt")),
        processed_at=_str_or_none(row.get("ProcessedAt")),
        result=_parse_json(row.get("ResultJSON")),
        error_text=_str_or_none(row.get("ErrorText")),
        claim_expires_at=_str_or_none(row.get("ClaimExpiresAt")),
        attempt_count=_int_or_default(row.get("AttemptCount"), 0),
        max_attempts=_int_or_default(row.get("MaxAttempts"), 3),
        sequence_id=_str_or_none(row.get("SequenceID")),
        sequence_order=_int_or_default(row.get("SequenceOrder"), 0),
        wait_for_prior=_bool_from_db(row.get("WaitForPrior")),
        priority=_int_or_default(row.get("Priority"), 5),
        purge_after=_str_or_none(row.get("PurgeAfter")),
        target_map_id=_int_or_none(row.get("TargetMapID")),
        target_x=_float_or_none(row.get("TargetX")),
        target_y=_float_or_none(row.get("TargetY")),
        target_z=_float_or_none(row.get("TargetZ")),
        target_o=_float_or_none(row.get("TargetO")),
        target_player_guid=_int_or_none(row.get("TargetPlayerGUID")),
    )


def _request_select_sql() -> str:
    return (
        "SELECT RequestID, IdempotencyKey, PlayerGUID, ActionKind, PayloadJSON, Status, CreatedBy, RiskLevel, "
        "CreatedAt, ClaimedAt, ClaimExpiresAt, AttemptCount, MaxAttempts, ProcessedAt, ResultJSON, ErrorText, "
        "SequenceID, SequenceOrder, WaitForPrior, Priority, PurgeAfter, "
        "TargetMapID, TargetX, TargetY, TargetZ, TargetO, TargetPlayerGUID"
    )


def _parse_json(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return {"raw": str(value)}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def _str_or_none(value: Any) -> str | None:
    return None if value in (None, "") else str(value)


def _int_or_none(value: Any) -> int | None:
    return None if value in (None, "") else int(value)


def _int_or_default(value: Any, default: int) -> int:
    return default if value in (None, "") else int(value)


def _float_or_none(value: Any) -> float | None:
    return None if value in (None, "") else float(value)


def _bool_from_db(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _sql_float_or_null(value: float | None) -> str:
    if value is None:
        return "NULL"
    return str(float(value))


def _int_from_first_row(rows: list[dict[str, Any]], key: str) -> int:
    if not rows:
        return 0
    value = rows[0].get(key)
    return 0 if value in (None, "") else int(value)
