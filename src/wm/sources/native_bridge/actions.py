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
    ) -> NativeBridgeActionRequest:
        if action_kind not in NATIVE_ACTION_KIND_BY_ID:
            raise ValueError(f"Unknown native bridge action kind: {action_kind}")
        payload_json = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)
        expires_sql = "NULL" if expires_seconds is None else f"DATE_ADD(NOW(), INTERVAL {int(expires_seconds)} SECOND)"
        sql = (
            "INSERT INTO wm_bridge_action_request ("
            "IdempotencyKey, PlayerGUID, ActionKind, PayloadJSON, Status, CreatedBy, RiskLevel, ExpiresAt"
            ") VALUES ("
            f"{_sql_string(idempotency_key)}, "
            f"{int(player_guid)}, "
            f"{_sql_string(action_kind)}, "
            f"{_sql_string(payload_json)}, "
            "'pending', "
            f"{_sql_string(created_by)}, "
            f"{_sql_string(risk_level)}, "
            f"{expires_sql}"
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
            "SELECT RequestID, IdempotencyKey, PlayerGUID, ActionKind, PayloadJSON, Status, CreatedBy, RiskLevel, "
            "CreatedAt, ClaimedAt, ProcessedAt, ResultJSON, ErrorText "
            "FROM wm_bridge_action_request "
            f"WHERE RequestID = {int(request_id)}"
        )
        return _row_to_request(rows[0]) if rows else None

    def get_by_idempotency_key(self, *, idempotency_key: str) -> NativeBridgeActionRequest | None:
        rows = self._query_world(
            "SELECT RequestID, IdempotencyKey, PlayerGUID, ActionKind, PayloadJSON, Status, CreatedBy, RiskLevel, "
            "CreatedAt, ClaimedAt, ProcessedAt, ResultJSON, ErrorText "
            "FROM wm_bridge_action_request "
            f"WHERE IdempotencyKey = {_sql_string(idempotency_key)} "
            "LIMIT 1"
        )
        return _row_to_request(rows[0]) if rows else None

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
