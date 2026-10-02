"""Durable work records for the existing autoplay compiler and executor."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from wm.autoplay.durable_native import DirectorLedger


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True, slots=True)
class FrozenWork:
    kind: str
    payload: dict[str, Any]
    artifact_hash: str
    effect_kinds: tuple[str, ...]

    @classmethod
    def from_runtime(cls, runtime: dict[str, Any]) -> "FrozenWork":
        kind = str(runtime.get("kind") or "")
        if kind == "control":
            proposals = runtime.get("proposals") or []
            payload = {"kind": kind, "proposals": [proposal.model_dump(mode="json") for proposal in proposals]}
            effect_kinds = tuple(str(
                proposal.action.payload.get("native_action_kind")
                if proposal.action.kind == "native_bridge_action" else proposal.action.kind
            ) for proposal in proposals)
        elif kind == "plan":
            plan = runtime["plan"]
            payload = {"kind": kind, "plan": plan.to_dict()}
            effect_kinds = tuple(action.kind for action in plan.actions)
        else:
            raise ValueError(f"Unsupported durable runtime kind: {kind}")
        if not effect_kinds:
            raise ValueError("Durable work needs at least one effect")
        digest = hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()
        return cls(kind=kind, payload=payload, artifact_hash=digest, effect_kinds=effect_kinds)

    def thaw(self) -> dict[str, Any]:
        if self.kind == "control":
            from wm.control.models import ControlProposal

            return {"kind": "control", "proposals": [
                ControlProposal.model_validate(raw) for raw in self.payload["proposals"]
            ]}
        from wm.events.models import PlannedAction, ReactionCooldownKey, ReactionPlan, SubjectRef

        raw = self.payload["plan"]
        subject = raw["subject"]
        cooldown = raw.get("cooldown_key")
        plan = ReactionPlan(
            plan_key=raw["plan_key"], opportunity_type=raw["opportunity_type"],
            rule_type=raw["rule_type"], player_guid=int(raw["player_guid"]),
            subject=SubjectRef(subject_type=subject["subject_type"], subject_entry=int(subject["subject_entry"])),
            actions=[PlannedAction(**action) for action in raw["actions"]],
            metadata=raw.get("metadata") or {},
            cooldown_key=ReactionCooldownKey(
                rule_type=cooldown["rule_type"], player_guid=int(cooldown["player_guid"]),
                subject_type=cooldown["subject_type"], subject_entry=int(cooldown["subject_entry"]),
            ) if cooldown else None,
            cooldown_seconds=raw.get("cooldown_seconds"),
        )
        return {"kind": "plan", "plan": plan}


@dataclass(frozen=True, slots=True)
class WorkRequest:
    request_id: int
    origin_key: str
    player_guid: int
    state: str
    revision: int
    artifact_hash: str
    artifact: FrozenWork


class DirectorWorkLedger(DirectorLedger):
    def load_review(self, *, request_id: int, player_guid: int) -> tuple[WorkRequest, dict[str, Any]]:
        if request_id <= 0 or player_guid <= 0:
            raise ValueError("director review requires a request and player scope")
        conn = self._open()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT req.OriginKey, artifact.PreviewJSON, artifact.EvidenceJSON "
                    "FROM wm_director_request req JOIN wm_director_artifact artifact "
                    "ON artifact.RequestID=req.RequestID "
                    "WHERE req.RequestID=%s AND req.PlayerGUID=%s",
                    (request_id, player_guid),
                )
                row = cursor.fetchone()
        finally:
            conn.close()
        if row is None:
            raise ValueError("director work not found for selected player")
        work = self.load(row["OriginKey"])
        if work is None or work.request_id != request_id or work.player_guid != player_guid:
            raise ValueError("director work scope changed")
        return work, {"preview": json.loads(row["PreviewJSON"]),
                      "evidence": json.loads(row["EvidenceJSON"])}

    def reject(self, work: WorkRequest, *, reason: str) -> WorkRequest:
        if work.state != "received":
            raise ValueError("only unapproved work can be rejected")
        conn = self._open()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE wm_director_request SET State='rejected', Revision=Revision+1 "
                    "WHERE RequestID=%s AND PlayerGUID=%s AND ProposalHash=%s "
                    "AND State='received' AND Revision=%s",
                    (work.request_id, work.player_guid, work.artifact_hash, work.revision),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("director rejection lost revision race")
                cursor.execute(
                    "INSERT INTO wm_director_transition "
                    "(RequestID, Revision, FromState, ToState, Reason) "
                    "VALUES (%s,%s,'received','rejected',%s)",
                    (work.request_id, work.revision + 1, str(reason or "operator_rejected")[:191]),
                )
            conn.commit()
            return WorkRequest(work.request_id, work.origin_key, work.player_guid, "rejected",
                               work.revision + 1, work.artifact_hash, work.artifact)
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
                    "SELECT req.RequestID, req.OriginKey, req.Verb, req.State, req.Revision, "
                    "req.CreatedAt, artifact.ArtifactHash, artifact.ArtifactJSON, "
                    "artifact.PreviewJSON, artifact.EvidenceJSON, "
                    "auth.Mode, auth.Principal, auth.ExpiresAt, proof.ProofJSON "
                    "FROM wm_director_request req "
                    "JOIN wm_director_artifact artifact ON artifact.RequestID=req.RequestID "
                    "LEFT JOIN wm_director_authorization auth ON auth.RequestID=req.RequestID "
                    "LEFT JOIN wm_director_proof proof ON proof.RequestID=req.RequestID "
                    "WHERE req.PlayerGUID=%s ORDER BY req.RequestID DESC LIMIT %s",
                    (player_guid, max(1, min(int(limit), 100))),
                )
                rows = cursor.fetchall()
                request_ids = [int(row["RequestID"]) for row in rows]
                effects: dict[int, list[dict[str, Any]]] = {request_id: [] for request_id in request_ids}
                if request_ids:
                    placeholders = ",".join(["%s"] * len(request_ids))
                    cursor.execute(
                        f"SELECT RequestID, StepOrdinal, EffectKey, Kind, State, ReceiptJSON "
                        f"FROM wm_director_effect WHERE RequestID IN ({placeholders}) "
                        "ORDER BY RequestID DESC, StepOrdinal", request_ids,
                    )
                    for effect in cursor.fetchall():
                        effects[int(effect["RequestID"])].append({
                            "step": int(effect["StepOrdinal"]), "effect_key": effect["EffectKey"],
                            "kind": effect["Kind"], "state": effect["State"],
                            "receipt": json.loads(effect["ReceiptJSON"]) if effect["ReceiptJSON"] else None,
                        })
            return [{
                "request_id": int(row["RequestID"]), "origin_key": row["OriginKey"],
                "lane": row["Verb"], "state": row["State"], "revision": int(row["Revision"]),
                "created_at": row["CreatedAt"].isoformat(), "artifact_hash": row["ArtifactHash"],
                "artifact": json.loads(row["ArtifactJSON"]),
                "preview": json.loads(row["PreviewJSON"]),
                "evidence": json.loads(row["EvidenceJSON"]),
                "authorization": ({"mode": row["Mode"], "principal": row["Principal"],
                                   "expires_at": row["ExpiresAt"].isoformat()} if row["Mode"] else None),
                "effects": effects[int(row["RequestID"])],
                "proof": json.loads(row["ProofJSON"]) if row["ProofJSON"] else None,
            } for row in rows]
        finally:
            conn.close()

    def load(self, origin_key: str) -> WorkRequest | None:
        conn = self._open()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT req.RequestID, req.OriginKey, req.PlayerGUID, req.State, req.Revision, "
                    "artifact.ArtifactHash, artifact.ArtifactJSON "
                    "FROM wm_director_request req JOIN wm_director_artifact artifact "
                    "ON artifact.RequestID=req.RequestID WHERE req.OriginKey=%s", (origin_key,),
                )
                row = cursor.fetchone()
            if row is None:
                return None
            payload = json.loads(row["ArtifactJSON"])
            digest = hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()
            if digest != row["ArtifactHash"]:
                raise ValueError("stored director artifact hash does not match its payload")
            kind = payload["kind"]
            effect_kinds = (
                tuple(proposal["action"]["payload"].get("native_action_kind")
                      if proposal["action"]["kind"] == "native_bridge_action"
                      else proposal["action"]["kind"] for proposal in payload["proposals"])
                if kind == "control" else tuple(action["kind"] for action in payload["plan"]["actions"])
            )
            artifact = FrozenWork(kind=kind, payload=payload, artifact_hash=digest, effect_kinds=effect_kinds)
            return WorkRequest(int(row["RequestID"]), row["OriginKey"], int(row["PlayerGUID"]),
                               row["State"], int(row["Revision"]), digest, artifact)
        finally:
            conn.close()

    def prepare(
        self, *, origin_key: str, player_guid: int, lane: str, artifact: FrozenWork,
        preview: dict[str, Any], evidence: dict[str, Any],
    ) -> WorkRequest:
        if not origin_key or len(origin_key) > 191 or player_guid <= 0:
            raise ValueError("invalid director work origin or player scope")
        native_key = "director:" + hashlib.sha256(origin_key.encode("utf-8")).hexdigest()
        conn = self._open()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO wm_director_request "
                    "(OriginKey, PlayerGUID, Verb, ProposalHash, NativeKey) VALUES (%s,%s,%s,%s,%s) "
                    "ON DUPLICATE KEY UPDATE RequestID=LAST_INSERT_ID(RequestID)",
                    (origin_key, player_guid, lane, artifact.artifact_hash, native_key),
                )
                request_id = int(cursor.lastrowid)
                cursor.execute("SELECT * FROM wm_director_request WHERE RequestID=%s FOR UPDATE", (request_id,))
                row = cursor.fetchone()
                if (row is None or row["OriginKey"] != origin_key or int(row["PlayerGUID"]) != player_guid
                        or row["Verb"] != lane or row["ProposalHash"] != artifact.artifact_hash):
                    raise ValueError("director origin already belongs to different work")
                cursor.execute("SELECT ArtifactHash, ArtifactJSON FROM wm_director_artifact WHERE RequestID=%s", (request_id,))
                stored = cursor.fetchone()
                if stored is None:
                    cursor.execute(
                        "INSERT INTO wm_director_artifact "
                        "(RequestID, ArtifactHash, ArtifactJSON, PreviewJSON, EvidenceJSON) "
                        "VALUES (%s,%s,%s,%s,%s)",
                        (request_id, artifact.artifact_hash, _json(artifact.payload), _json(preview), _json(evidence)),
                    )
                    for index, kind in enumerate(artifact.effect_kinds):
                        cursor.execute(
                            "INSERT INTO wm_director_effect (RequestID, StepOrdinal, EffectKey, Kind) "
                            "VALUES (%s,%s,%s,%s)",
                            (request_id, index, f"director:{request_id}:{index}:{artifact.artifact_hash[:24]}", kind),
                        )
                    cursor.execute(
                        "INSERT IGNORE INTO wm_director_transition "
                        "(RequestID, Revision, FromState, ToState, Reason) VALUES (%s,0,NULL,'received','prepared')",
                        (request_id,),
                    )
                elif stored["ArtifactHash"] != artifact.artifact_hash or json.loads(stored["ArtifactJSON"]) != artifact.payload:
                    raise ValueError("director artifact changed after first preview")
            conn.commit()
            return WorkRequest(request_id, origin_key, player_guid, row["State"], int(row["Revision"]),
                               artifact.artifact_hash, artifact)
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def authorize(
        self, work: WorkRequest, *, policy: dict[str, Any], mode: str,
        expires_seconds: int = 120, principal: str = "wm.policy",
    ) -> WorkRequest:
        if mode not in {"automatic", "operator"} or not policy.get("ok"):
            raise ValueError("authorization requires an allowing policy and known principal")
        if expires_seconds <= 0:
            raise ValueError("authorization expiry must be positive")
        conn = self._open()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT State, Revision, PlayerGUID, ProposalHash FROM wm_director_request "
                               "WHERE RequestID=%s FOR UPDATE", (work.request_id,))
                row = cursor.fetchone()
                if row is None or int(row["PlayerGUID"]) != work.player_guid or row["ProposalHash"] != work.artifact_hash:
                    raise ValueError("authorization scope or artifact changed")
                if row["State"] != "received" or int(row["Revision"]) != work.revision:
                    raise RuntimeError("director work is no longer awaiting authorization")
                cursor.execute(
                    "INSERT INTO wm_director_authorization "
                    "(RequestID, ArtifactHash, PlayerGUID, Mode, Principal, PolicyJSON, ExpiresAt) "
                    "VALUES (%s,%s,%s,%s,%s,%s,DATE_ADD(NOW(), INTERVAL %s SECOND))",
                    (work.request_id, work.artifact_hash, work.player_guid, mode, principal[:96],
                     _json(policy), int(expires_seconds)),
                )
                cursor.execute(
                    "UPDATE wm_director_request SET State='authorized', Revision=Revision+1 "
                    "WHERE RequestID=%s AND State='received' AND Revision=%s",
                    (work.request_id, work.revision),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("director authorization lost revision race")
                cursor.execute(
                    "INSERT INTO wm_director_transition (RequestID, Revision, FromState, ToState, Reason) "
                    "VALUES (%s,%s,'received','authorized',%s)",
                    (work.request_id, work.revision + 1, mode),
                )
            conn.commit()
            return WorkRequest(work.request_id, work.origin_key, work.player_guid, "authorized",
                               work.revision + 1, work.artifact_hash, work.artifact)
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def claim(self, work: WorkRequest) -> WorkRequest:
        if work.state != "authorized":
            raise ValueError("only authorized work can dispatch")
        conn = self._open()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE wm_director_request req JOIN wm_director_authorization auth "
                    "ON auth.RequestID=req.RequestID "
                    "SET req.State='dispatching', req.Revision=req.Revision+1 "
                    "WHERE req.RequestID=%s AND req.State='authorized' AND req.Revision=%s "
                    "AND auth.ArtifactHash=%s AND auth.PlayerGUID=%s AND auth.ExpiresAt>NOW()",
                    (work.request_id, work.revision, work.artifact_hash, work.player_guid),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("authorization expired or another worker claimed the work")
                cursor.execute(
                    "INSERT INTO wm_director_transition (RequestID, Revision, FromState, ToState, Reason) "
                    "VALUES (%s,%s,'authorized','dispatching','dispatch_intent_committed')",
                    (work.request_id, work.revision + 1),
                )
                cursor.execute(
                    "UPDATE wm_director_effect SET State='dispatching', Revision=Revision+1 "
                    "WHERE RequestID=%s AND State='pending'", (work.request_id,),
                )
            conn.commit()
            return WorkRequest(work.request_id, work.origin_key, work.player_guid, "dispatching",
                               work.revision + 1, work.artifact_hash, work.artifact)
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def record_result(self, work: WorkRequest, *, results: list[Any]) -> WorkRequest:
        if work.state != "dispatching":
            raise ValueError("only dispatching work can record effects")
        if work.artifact.kind == "control":
            receipts = [(item.status, item.to_dict()) for item in results]
        else:
            plan_result = results[0] if len(results) == 1 else None
            receipts = [(step.status, step.to_dict()) for step in (getattr(plan_result, "steps", []) or [])]
        applied = len(receipts) == len(work.artifact.effect_kinds) and all(
            status == "applied" for status, _ in receipts
        )
        state = "applied" if applied else "uncertain"
        conn = self._open()
        try:
            with conn.cursor() as cursor:
                for index, (step_status, receipt) in enumerate(receipts):
                    cursor.execute(
                        "UPDATE wm_director_effect SET State=%s, Revision=Revision+1, ReceiptJSON=%s "
                        "WHERE RequestID=%s AND StepOrdinal=%s AND State='dispatching'",
                        ("applied" if step_status == "applied" else "uncertain", _json(receipt),
                         work.request_id, index),
                    )
                cursor.execute(
                    "UPDATE wm_director_request SET State=%s, Revision=Revision+1, ResultJSON=%s "
                    "WHERE RequestID=%s AND State='dispatching' AND Revision=%s",
                    (state, _json([item.to_dict() for item in results]), work.request_id, work.revision),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("director result lost revision race")
                cursor.execute(
                    "INSERT INTO wm_director_transition (RequestID, Revision, FromState, ToState, Reason) "
                    "VALUES (%s,%s,'dispatching',%s,'executor_receipt')",
                    (work.request_id, work.revision + 1, state),
                )
            conn.commit()
            return WorkRequest(work.request_id, work.origin_key, work.player_guid, state,
                               work.revision + 1, work.artifact_hash, work.artifact)
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def mark_uncertain(self, work: WorkRequest, *, reason: str) -> WorkRequest:
        if work.state != "dispatching":
            raise ValueError("only dispatching work can become uncertain")
        conn = self._open()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE wm_director_request SET State='uncertain', Revision=Revision+1 "
                    "WHERE RequestID=%s AND State='dispatching' AND Revision=%s",
                    (work.request_id, work.revision),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("director uncertainty lost revision race")
                cursor.execute(
                    "INSERT INTO wm_director_transition (RequestID, Revision, FromState, ToState, Reason) "
                    "VALUES (%s,%s,'dispatching','uncertain',%s)",
                    (work.request_id, work.revision + 1, reason[:160]),
                )
                cursor.execute(
                    "UPDATE wm_director_effect SET State='uncertain', Revision=Revision+1 "
                    "WHERE RequestID=%s AND State='dispatching'", (work.request_id,),
                )
            conn.commit()
            return WorkRequest(work.request_id, work.origin_key, work.player_guid, "uncertain",
                               work.revision + 1, work.artifact_hash, work.artifact)
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def verify(self, work: WorkRequest, *, proof: dict[str, Any]) -> WorkRequest:
        if work.state != "applied" or not proof.get("ok"):
            raise ValueError("verification requires applied work and positive independent proof")
        conn = self._open()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE wm_director_request SET State='verified', Revision=Revision+1 "
                    "WHERE RequestID=%s AND State='applied' AND Revision=%s",
                    (work.request_id, work.revision),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("director verification lost revision race")
                cursor.execute(
                    "INSERT INTO wm_director_proof (RequestID, ProofJSON) VALUES (%s,%s)",
                    (work.request_id, _json(proof)),
                )
                cursor.execute(
                    "INSERT INTO wm_director_transition (RequestID, Revision, FromState, ToState, Reason) "
                    "VALUES (%s,%s,'applied','verified',%s)",
                    (work.request_id, work.revision + 1, str(proof.get("source") or "proof")[:160]),
                )
            conn.commit()
            return WorkRequest(work.request_id, work.origin_key, work.player_guid, "verified",
                               work.revision + 1, work.artifact_hash, work.artifact)
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()
