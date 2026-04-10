from __future__ import annotations

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
