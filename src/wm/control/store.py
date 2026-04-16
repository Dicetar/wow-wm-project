from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
import json
import subprocess
from typing import Any

from wm.config import Settings
from wm.control.models import ControlProposal
from wm.control.models import ControlValidationResult
from wm.db.mysql_cli import MysqlCliClient, MysqlCliError
from wm.events.store import _sql_int_or_null
from wm.events.store import _sql_string
from wm.events.store import _sql_string_or_null


@dataclass(slots=True)
class ControlAuditRecord:
    proposal_id: int
    idempotency_key: str
    schema_version: str
    registry_hash: str | None
    schema_hash: str | None
    author_mode: str
    author_name: str | None
    player_guid: int | None
    source_event_id: int | None
    source_event_key: str | None
    selected_recipe: str
    action_kind: str
    status: str
    raw_proposal: dict[str, Any]
    normalized_proposal: dict[str, Any] | None
    validation: dict[str, Any] | None
    dry_run: dict[str, Any] | None
    apply: dict[str, Any] | None
    policy_decision: dict[str, Any] | None
    created_at: str | None
    updated_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ControlAuditStore:
    def __init__(self, *, client: MysqlCliClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def get_status(self, *, idempotency_key: str) -> str | None:
        rows = self._query_world(
            "SELECT Status FROM wm_control_proposal "
            f"WHERE IdempotencyKey = {_sql_string(idempotency_key)} "
            "LIMIT 1"
        )
        if not rows:
            return None
        return str(rows[0]["Status"])

    def get_record(self, *, idempotency_key: str) -> ControlAuditRecord | None:
        rows = self._query_world(
            _control_proposal_select_sql()
            + " FROM wm_control_proposal "
            + f"WHERE IdempotencyKey = {_sql_string(idempotency_key)} "
            + "LIMIT 1"
        )
        return _row_to_record(rows[0]) if rows else None

    def list_records(
        self,
        *,
        source_event_id: int | None = None,
        player_guid: int | None = None,
        limit: int = 20,
    ) -> list[ControlAuditRecord]:
        predicates: list[str] = []
        if source_event_id is not None:
            predicates.append(f"SourceEventID = {int(source_event_id)}")
        if player_guid is not None:
            predicates.append(f"PlayerGUID = {int(player_guid)}")
        where_clause = f"WHERE {' AND '.join(predicates)} " if predicates else ""
        rows = self._query_world(
            _control_proposal_select_sql()
            + " FROM wm_control_proposal "
            + where_clause
            + "ORDER BY ProposalID DESC "
            + f"LIMIT {max(1, min(200, int(limit)))}"
        )
        return [_row_to_record(row) for row in rows]

    def record_proposal(
        self,
        *,
        proposal: ControlProposal,
        validation: ControlValidationResult,
        status: str,
    ) -> None:
        normalized = validation.normalized_proposal or proposal.model_dump(mode="json")
        source_event_id = proposal.source_event.event_id if proposal.source_event is not None else None
        source_event_key = proposal.source_event.source_event_key if proposal.source_event is not None else None
        idempotency_key = proposal.idempotency_key or ""
        sql = (
            "INSERT INTO wm_control_proposal ("
            "IdempotencyKey, SchemaVersion, RegistryHash, SchemaHash, AuthorMode, AuthorName, PlayerGUID, "
            "SourceEventID, SourceEventKey, SelectedRecipe, ActionKind, Status, RawProposalJSON, "
            "NormalizedProposalJSON, ValidationJSON, PolicyDecisionJSON"
            ") VALUES ("
            f"{_sql_string(idempotency_key)}, "
            f"{_sql_string(proposal.schema_version)}, "
            f"{_sql_string_or_null(validation.registry_hash)}, "
            f"{_sql_string_or_null(validation.schema_hash)}, "
            f"{_sql_string(proposal.author.kind)}, "
            f"{_sql_string_or_null(proposal.author.name)}, "
            f"{int(proposal.player.guid)}, "
            f"{_sql_int_or_null(source_event_id)}, "
            f"{_sql_string_or_null(source_event_key)}, "
            f"{_sql_string(proposal.selected_recipe)}, "
            f"{_sql_string(proposal.action.kind)}, "
            f"{_sql_string(status)}, "
            f"{_sql_string(proposal.model_dump_json())}, "
            f"{_sql_string(json.dumps(normalized, ensure_ascii=False, sort_keys=True))}, "
            f"{_sql_string(validation.model_dump_json())}, "
            f"{_sql_string(json.dumps(validation.policy, ensure_ascii=False, sort_keys=True))}"
            ") ON DUPLICATE KEY UPDATE "
            "Status = IF(wm_control_proposal.Status = 'applied', wm_control_proposal.Status, VALUES(Status)), "
            "RawProposalJSON = IF(wm_control_proposal.Status = 'applied', wm_control_proposal.RawProposalJSON, VALUES(RawProposalJSON)), "
            "NormalizedProposalJSON = IF(wm_control_proposal.Status = 'applied', wm_control_proposal.NormalizedProposalJSON, VALUES(NormalizedProposalJSON)), "
            "ValidationJSON = IF(wm_control_proposal.Status = 'applied', wm_control_proposal.ValidationJSON, VALUES(ValidationJSON)), "
            "PolicyDecisionJSON = IF(wm_control_proposal.Status = 'applied', wm_control_proposal.PolicyDecisionJSON, VALUES(PolicyDecisionJSON)), "
            "UpdatedAt = CURRENT_TIMESTAMP"
        )
        self._execute_world(sql)

    def update_dry_run(self, *, idempotency_key: str, status: str, result: dict[str, Any]) -> None:
        self._execute_world(
            "UPDATE wm_control_proposal "
            f"SET Status = {_sql_string(status)}, DryRunJSON = {_sql_string(json.dumps(result, ensure_ascii=False, sort_keys=True))}, "
            "UpdatedAt = CURRENT_TIMESTAMP "
            f"WHERE IdempotencyKey = {_sql_string(idempotency_key)}"
        )

    def update_apply(self, *, idempotency_key: str, status: str, result: dict[str, Any]) -> None:
        self._execute_world(
            "UPDATE wm_control_proposal "
            f"SET Status = {_sql_string(status)}, ApplyJSON = {_sql_string(json.dumps(result, ensure_ascii=False, sort_keys=True))}, "
            "UpdatedAt = CURRENT_TIMESTAMP "
            f"WHERE IdempotencyKey = {_sql_string(idempotency_key)}"
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

    def _execute_world(self, sql: str) -> None:
        command = [
            str(self.client.mysql_bin_path),
            f"--host={self.settings.world_db_host}",
            f"--port={self.settings.world_db_port}",
            f"--user={self.settings.world_db_user}",
            f"--password={self.settings.world_db_password}",
            f"--database={self.settings.world_db_name}",
            f"--execute={sql}",
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0:
            raise MysqlCliError(completed.stderr.strip() or completed.stdout.strip() or "mysql execute failed")


def _control_proposal_select_sql() -> str:
    return (
        "SELECT ProposalID, IdempotencyKey, SchemaVersion, RegistryHash, SchemaHash, AuthorMode, AuthorName, "
        "PlayerGUID, SourceEventID, SourceEventKey, SelectedRecipe, ActionKind, Status, RawProposalJSON, "
        "NormalizedProposalJSON, ValidationJSON, DryRunJSON, ApplyJSON, PolicyDecisionJSON, CreatedAt, UpdatedAt"
    )


def _row_to_record(row: dict[str, Any]) -> ControlAuditRecord:
    return ControlAuditRecord(
        proposal_id=int(row["ProposalID"]),
        idempotency_key=str(row["IdempotencyKey"]),
        schema_version=str(row["SchemaVersion"]),
        registry_hash=_str_or_none(row.get("RegistryHash")),
        schema_hash=_str_or_none(row.get("SchemaHash")),
        author_mode=str(row["AuthorMode"]),
        author_name=_str_or_none(row.get("AuthorName")),
        player_guid=_int_or_none(row.get("PlayerGUID")),
        source_event_id=_int_or_none(row.get("SourceEventID")),
        source_event_key=_str_or_none(row.get("SourceEventKey")),
        selected_recipe=str(row["SelectedRecipe"]),
        action_kind=str(row["ActionKind"]),
        status=str(row["Status"]),
        raw_proposal=_json_object_or_default(row.get("RawProposalJSON")),
        normalized_proposal=_json_object_or_none(row.get("NormalizedProposalJSON")),
        validation=_json_object_or_none(row.get("ValidationJSON")),
        dry_run=_json_object_or_none(row.get("DryRunJSON")),
        apply=_json_object_or_none(row.get("ApplyJSON")),
        policy_decision=_json_object_or_none(row.get("PolicyDecisionJSON")),
        created_at=_str_or_none(row.get("CreatedAt")),
        updated_at=_str_or_none(row.get("UpdatedAt")),
    )


def _json_object_or_default(value: Any) -> dict[str, Any]:
    return _json_object_or_none(value) or {}


def _json_object_or_none(value: Any) -> dict[str, Any] | None:
    if value in (None, ""):
        return None
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return {"raw": str(value)}
    if isinstance(parsed, dict):
        return parsed
    return {"value": parsed}


def _str_or_none(value: Any) -> str | None:
    return None if value in (None, "") else str(value)


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)
