"""NativeApplier — INSERT into wm_bridge_action_request from plans/proposals.

The bridge applies typed actions atomically via wm_bridge_action_request
(see Phase 0D: the request is picked up by PollActionQueue, executed
through the per-domain TUs, status set to 'done'/'failed'). This module
is the Python-side seam: render a GrantPlan or quest proposal as one or
more INSERTs.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
from typing import Any, Protocol
from wm.abilities.grant_compiler import GrantPlan
from wm.llm.proposal_adapter import Proposal


class _DbClient(Protocol):
    def execute(self, *, host: str, port: int, user: str, password: str,
                database: str, sql: str) -> Any: ...


def _sql_str(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


@dataclass(slots=True)
class NativeApplier:
    client: Any                  # MysqlCliClient-shaped; .execute(...) is enough
    host: str
    port: int
    user: str
    password: str
    database: str = "acore_world"
    created_by: str = "wm-slice"
    risk_level: str = "low"

    def apply_grant_plan(self, plan: GrantPlan) -> dict[str, Any]:
        for i, step in enumerate(plan.steps):
            idem = f"{plan.idempotency_key}:{i}:{step.action_kind}"
            self._insert_action_request(
                idempotency_key=idem,
                player_guid=plan.character_guid,
                action_kind=step.action_kind,
                payload=step.payload,
            )
        return {"ok": True, "ability_id": plan.ability_id, "steps": len(plan.steps)}

    def insert_quest_add(self, *, character_guid: int, quest_id: int,
                         idempotency_key: str) -> dict[str, Any]:
        self._insert_action_request(
            idempotency_key=idempotency_key,
            player_guid=character_guid,
            action_kind="quest_add",
            payload={"quest_id": int(quest_id)},
        )
        return {"ok": True, "quest_id": int(quest_id)}

    def _insert_action_request(self, *, idempotency_key: str, player_guid: int,
                               action_kind: str, payload: dict[str, Any]) -> None:
        sql = (
            "INSERT INTO wm_bridge_action_request "
            "(IdempotencyKey,PlayerGUID,ActionKind,PayloadJSON,Status,CreatedBy,RiskLevel) "
            "VALUES ("
            f"{_sql_str(idempotency_key)},{int(player_guid)},"
            f"{_sql_str(action_kind)},{_sql_str(json.dumps(payload, separators=(',', ':')))},"
            f"'pending',{_sql_str(self.created_by)},{_sql_str(self.risk_level)})"
        )
        self.client.execute(host=self.host, port=self.port, user=self.user,
                            password=self.password, database=self.database, sql=sql)


def apply_quest_grant_proposal(p: Proposal, *, applier: NativeApplier) -> dict[str, Any]:
    """Slice convention: a quest proposal MAY carry `grant_quest_id` inside
    `quest_release`. If present, we fire a bridge `quest_add` action.
    Otherwise we return ok=False with a clear error (no auto quest-template
    publish in the slice — that's wm.content.release territory)."""
    qr = (p.payload or {}).get("quest_release", {})
    qid = qr.get("grant_quest_id")
    if qid is None:
        return {"ok": False, "error": "missing grant_quest_id in quest_release payload"}
    beat_id = (p.provenance or {}).get("beat_id", "watcher")
    idem = f"slice.quest_grant:{beat_id}:{qid}:{p.character_guid}"
    return applier.insert_quest_add(character_guid=p.character_guid,
                                    quest_id=int(qid), idempotency_key=idem)
