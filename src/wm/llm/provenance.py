"""LLM proposal provenance: records and retrieves LLM-generated proposals."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class LLMProposalProvenance:
    proposal_id: int
    schema_version: str
    instruction: str
    raw_response: str
    parsed_json: dict | None
    model_id: str | None
    operator: str | None
    state: str          # PENDING | ADOPTED | REJECTED
    created_at: str
    adopted_at: str | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "schema_version": self.schema_version,
            "instruction": self.instruction,
            "raw_length": len(self.raw_response),
            "model_id": self.model_id,
            "operator": self.operator,
            "state": self.state,
            "created_at": self.created_at,
            "adopted_at": self.adopted_at,
            "metadata": self.metadata,
        }


class ProvenanceLogger:
    """Persists LLM proposal provenance to wm_llm_proposal_log."""

    def __init__(self, db_client: Any = None):
        self._db = db_client

    def log(
        self,
        *,
        schema_version: str,
        instruction: str,
        raw_response: str,
        parsed_json: dict | None = None,
        model_id: str | None = None,
        operator: str | None = None,
        metadata: dict | None = None,
    ) -> int | None:
        if self._db is None:
            return None
        result = self._db.execute(
            """
            INSERT INTO wm_llm_proposal_log
                (schema_version, instruction, raw_response, parsed_json,
                 model_id, operator, state, metadata_json)
            VALUES (%s, %s, %s, %s, %s, %s, 'PENDING', %s)
            """,
            (
                schema_version,
                instruction[:2000],
                raw_response[:16000],
                json.dumps(parsed_json) if parsed_json else None,
                model_id,
                operator,
                json.dumps(metadata) if metadata else None,
            ),
        )
        return result

    def adopt(self, proposal_id: int, operator: str | None = None) -> None:
        if self._db is None:
            return
        self._db.execute(
            "UPDATE wm_llm_proposal_log SET state = 'ADOPTED', adopted_at = NOW(), "
            "operator = COALESCE(%s, operator) WHERE id = %s",
            (operator, proposal_id),
        )

    def reject(self, proposal_id: int) -> None:
        if self._db is None:
            return
        self._db.execute(
            "UPDATE wm_llm_proposal_log SET state = 'REJECTED' WHERE id = %s",
            (proposal_id,),
        )

    def load(self, proposal_id: int) -> LLMProposalProvenance | None:
        if self._db is None:
            return None
        rows = self._db.query(
            "SELECT id, schema_version, instruction, raw_response, parsed_json, "
            "model_id, operator, state, created_at, adopted_at, metadata_json "
            "FROM wm_llm_proposal_log WHERE id = %s",
            (proposal_id,),
        )
        if not rows:
            return None
        r = rows[0]
        raw_parsed = r.get("parsed_json")
        raw_meta = r.get("metadata_json")
        return LLMProposalProvenance(
            proposal_id=int(r["id"]),
            schema_version=r.get("schema_version", ""),
            instruction=r.get("instruction", ""),
            raw_response=r.get("raw_response", ""),
            parsed_json=json.loads(raw_parsed) if raw_parsed else None,
            model_id=r.get("model_id"),
            operator=r.get("operator"),
            state=r.get("state", "PENDING"),
            created_at=str(r.get("created_at", "")),
            adopted_at=str(r["adopted_at"]) if r.get("adopted_at") else None,
            metadata=json.loads(raw_meta) if raw_meta else {},
        )

    def list_pending(self, limit: int = 50) -> list[dict[str, Any]]:
        if self._db is None:
            return []
        rows = self._db.query(
            "SELECT id, schema_version, instruction, model_id, operator, state, created_at "
            "FROM wm_llm_proposal_log WHERE state = 'PENDING' ORDER BY id DESC LIMIT %s",
            (limit,),
        )
        return [dict(r) for r in rows]
