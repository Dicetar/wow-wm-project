"""Frozen evidence and first-writer-wins decisions for player requests."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any

from wm.autoplay.decision import DirectorDecision
from wm.autoplay.durable_native import DirectorLedger


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True, slots=True)
class Intake:
    origin_key: str
    player_guid: int
    evidence: dict[str, Any]
    evidence_hash: str
    decision: DirectorDecision | None


class DirectorIntakeLedger(DirectorLedger):
    def await_capability(self, *, origin_key: str, player_guid: int,
                         request: str, capability: str, reason: str) -> dict[str, Any]:
        if not capability.strip():
            raise ValueError("missing capability key")
        task = {
            "task_version": "wm.development_request.v1",
            "status": "proposed",
            "requested_experience": request[:1000],
            "missing_capability": capability[:191],
            "origin_request_refs": [origin_key],
            "reason": reason[:500],
            "deployment_authority": "separate_release_step",
        }
        conn = self._open()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT PlayerGUID, State, Revision, DecisionJSON FROM wm_director_intake "
                    "WHERE OriginKey=%s FOR UPDATE", (origin_key,),
                )
                row = cursor.fetchone()
                if row is None or int(row["PlayerGUID"]) != player_guid:
                    raise ValueError("development task origin or player scope changed")
                decision = json.loads(row["DecisionJSON"]) if row["DecisionJSON"] else None
                if (not decision or decision.get("outcome") != "needs_capability"
                        or decision.get("capability") != capability):
                    raise ValueError("development task requires matching typed decision")
                cursor.execute(
                    "INSERT INTO wm_director_development_task "
                    "(OriginKey, PlayerGUID, CapabilityKey, TaskJSON) VALUES (%s,%s,%s,%s) "
                    "ON DUPLICATE KEY UPDATE OriginKey=OriginKey",
                    (origin_key, player_guid, capability[:191], _json(task)),
                )
                cursor.execute(
                    "SELECT TaskID, PlayerGUID, CapabilityKey, TaskJSON FROM "
                    "wm_director_development_task WHERE OriginKey=%s", (origin_key,),
                )
                saved = cursor.fetchone()
                if (saved is None or int(saved["PlayerGUID"]) != player_guid
                        or saved["CapabilityKey"] != capability[:191]
                        or saved["TaskJSON"] != _json(task)):
                    raise ValueError("development task origin already has different content")
                if row["State"] == "decided":
                    cursor.execute(
                        "UPDATE wm_director_intake SET State='awaiting_capability', "
                        "Revision=Revision+1 WHERE OriginKey=%s AND State='decided' AND Revision=%s",
                        (origin_key, int(row["Revision"])),
                    )
                    if cursor.rowcount != 1:
                        raise RuntimeError("development task lost revision race")
                elif row["State"] != "awaiting_capability":
                    raise ValueError("director intake is not awaiting a capability")
            conn.commit()
            return {"task_id": int(saved["TaskID"]), **task}
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def prepare(self, *, origin_key: str, player_guid: int, evidence: dict[str, Any]) -> Intake:
        if not origin_key or len(origin_key) > 191 or player_guid <= 0:
            raise ValueError("invalid director intake origin or player scope")
        payload = _json(evidence)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        conn = self._open()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO wm_director_intake "
                    "(OriginKey, PlayerGUID, EvidenceHash, EvidenceJSON) VALUES (%s,%s,%s,%s) "
                    "ON DUPLICATE KEY UPDATE OriginKey=OriginKey",
                    (origin_key, player_guid, digest, payload),
                )
                cursor.execute(
                    "SELECT PlayerGUID, EvidenceHash, EvidenceJSON, DecisionJSON "
                    "FROM wm_director_intake WHERE OriginKey=%s FOR UPDATE", (origin_key,),
                )
                row = cursor.fetchone()
                if (row is None or int(row["PlayerGUID"]) != player_guid
                        or row["EvidenceHash"] != digest or row["EvidenceJSON"] != payload):
                    raise ValueError("director origin already belongs to different evidence")
            conn.commit()
            decision = DirectorDecision(**json.loads(row["DecisionJSON"])) if row["DecisionJSON"] else None
            return Intake(origin_key, player_guid, evidence, digest, decision)
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def decide(self, intake: Intake, *, decision: DirectorDecision) -> DirectorDecision:
        conn = self._open()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT PlayerGUID, EvidenceHash, DecisionJSON, State, Revision "
                    "FROM wm_director_intake WHERE OriginKey=%s FOR UPDATE", (intake.origin_key,),
                )
                row = cursor.fetchone()
                if (row is None or int(row["PlayerGUID"]) != intake.player_guid
                        or row["EvidenceHash"] != intake.evidence_hash):
                    raise ValueError("director decision scope or evidence changed")
                if row["DecisionJSON"]:
                    conn.commit()
                    return DirectorDecision(**json.loads(row["DecisionJSON"]))
                if row["State"] != "received" or int(row["Revision"]) != 0:
                    raise RuntimeError("director intake is no longer awaiting a decision")
                cursor.execute(
                    "UPDATE wm_director_intake SET DecisionJSON=%s, State='decided', "
                    "Revision=Revision+1, DecidedAt=NOW() "
                    "WHERE OriginKey=%s AND State='received' AND Revision=0",
                    (_json(asdict(decision)), intake.origin_key),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("director decision lost revision race")
            conn.commit()
            return decision
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_recent(self, *, player_guid: int, limit: int = 30) -> list[dict[str, Any]]:
        if player_guid <= 0:
            raise ValueError("player scope is required")
        conn = self._open()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT intake.OriginKey, intake.EvidenceHash, intake.EvidenceJSON, "
                    "intake.DecisionJSON, intake.State, intake.CreatedAt, intake.DecidedAt, "
                    "task.TaskID, task.TaskJSON FROM wm_director_intake intake LEFT JOIN "
                    "wm_director_development_task task ON task.OriginKey=intake.OriginKey "
                    "WHERE intake.PlayerGUID=%s ORDER BY intake.CreatedAt DESC LIMIT %s",
                    (player_guid, max(1, min(int(limit), 100))),
                )
                rows = cursor.fetchall()
            return [{"origin_key": row["OriginKey"], "evidence_hash": row["EvidenceHash"],
                     "evidence": json.loads(row["EvidenceJSON"]),
                     "decision": json.loads(row["DecisionJSON"]) if row["DecisionJSON"] else None,
                     "state": row["State"], "development_task_id": row["TaskID"],
                     "development_task": json.loads(row["TaskJSON"]) if row["TaskJSON"] else None,
                     "created_at": row["CreatedAt"].isoformat(),
                     "decided_at": row["DecidedAt"].isoformat() if row["DecidedAt"] else None}
                    for row in rows]
        finally:
            conn.close()
