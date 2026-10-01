"""Crash-safe pilot for one event-origin native action.

This does not retry an unknown submission. The native queue receipt is the
authority for whether a world effect ran; an absent receipt after dispatch is
an operator case, not permission to submit again.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Callable

from wm.config import Settings


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def native_key_for(proposal: Any, verb: str) -> str:
    return f"{proposal.idempotency_key}:no_source_event:native:{verb}"


@dataclass(frozen=True, slots=True)
class LedgerRequest:
    request_id: int
    origin_key: str
    player_guid: int
    verb: str
    proposal_hash: str
    native_key: str
    state: str
    revision: int
    native_request_id: int | None
    result: dict[str, Any] | None
    age_seconds: int | None


def _request_from_row(row: dict[str, Any]) -> LedgerRequest:
    raw_result = row.get("ResultJSON")
    return LedgerRequest(
        request_id=int(row["RequestID"]), origin_key=str(row["OriginKey"]),
        player_guid=int(row["PlayerGUID"]), verb=str(row["Verb"]),
        proposal_hash=str(row["ProposalHash"]), native_key=str(row["NativeKey"]),
        state=str(row["State"]), revision=int(row["Revision"]),
        native_request_id=int(row["NativeRequestID"]) if row.get("NativeRequestID") is not None else None,
        result=json.loads(raw_result) if raw_result else None,
        age_seconds=int(row["AgeSeconds"]) if row.get("AgeSeconds") is not None else None,
    )


class DirectorLedger:
    def __init__(self, *, settings: Settings, connect: Callable[..., Any] | None = None) -> None:
        if connect is None:
            import pymysql

            connect = pymysql.connect
        self.settings = settings
        self.connect = connect

    def _open(self) -> Any:
        import pymysql

        return self.connect(
            host=self.settings.world_db_host, port=self.settings.world_db_port,
            user=self.settings.world_db_user, password=self.settings.world_db_password,
            database=self.settings.world_db_name, charset="utf8mb4", autocommit=False,
            connect_timeout=3, read_timeout=3, write_timeout=3,
            cursorclass=pymysql.cursors.DictCursor,
        )

    def accept(self, *, origin_key: str, player_guid: int, verb: str, proposal: Any) -> LedgerRequest:
        if not origin_key or len(origin_key) > 191:
            raise ValueError("origin_key must be 1-191 characters")
        proposal_hash = hashlib.sha256(_json(proposal.model_dump(mode="json")).encode("utf-8")).hexdigest()
        native_key = native_key_for(proposal, verb)
        if len(native_key) > 191:
            raise ValueError("native idempotency key exceeds ledger limit")
        conn = self._open()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO wm_director_request "
                    "(OriginKey, PlayerGUID, Verb, ProposalHash, NativeKey) VALUES (%s,%s,%s,%s,%s) "
                    "ON DUPLICATE KEY UPDATE RequestID = LAST_INSERT_ID(RequestID)",
                    (origin_key, int(player_guid), verb, proposal_hash, native_key),
                )
                request_id = int(cursor.lastrowid)
                cursor.execute(
                    "SELECT *, TIMESTAMPDIFF(SECOND, UpdatedAt, NOW()) AS AgeSeconds "
                    "FROM wm_director_request WHERE RequestID=%s FOR UPDATE", (request_id,),
                )
                row = cursor.fetchone()
                if row is None or row["OriginKey"] != origin_key or row["ProposalHash"] != proposal_hash:
                    raise ValueError("origin key already belongs to a different proposal")
                if int(row["PlayerGUID"]) != int(player_guid) or row["Verb"] != verb:
                    raise ValueError("origin key scope mismatch")
                if int(row["Revision"]) == 0:
                    cursor.execute(
                        "INSERT IGNORE INTO wm_director_transition "
                        "(RequestID, Revision, FromState, ToState, Reason) VALUES (%s,0,NULL,'received','accepted')",
                        (request_id,),
                    )
            conn.commit()
            return _request_from_row(row)
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get(self, origin_key: str) -> LedgerRequest | None:
        conn = self._open()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT *, TIMESTAMPDIFF(SECOND, UpdatedAt, NOW()) AS AgeSeconds "
                    "FROM wm_director_request WHERE OriginKey=%s", (origin_key,),
                )
                row = cursor.fetchone()
            return _request_from_row(row) if row else None
        finally:
            conn.close()

    def transition(
        self, request: LedgerRequest, *, state: str, reason: str,
        native_request_id: int | None = None, result: dict[str, Any] | None = None,
    ) -> LedgerRequest:
        allowed = {
            "received": {"dispatching"},
            "dispatching": {"verified", "failed", "needs_operator"},
            "needs_operator": {"verified", "failed"},
        }
        if state not in allowed.get(request.state, set()):
            raise ValueError(f"invalid director transition: {request.state} -> {state}")
        conn = self._open()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE wm_director_request SET State=%s, Revision=Revision+1, "
                    "NativeRequestID=COALESCE(%s,NativeRequestID), ResultJSON=COALESCE(%s,ResultJSON) "
                    "WHERE RequestID=%s AND State=%s AND Revision=%s",
                    (state, native_request_id, _json(result) if result is not None else None,
                     request.request_id, request.state, request.revision),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("director request was changed by another worker")
                cursor.execute(
                    "INSERT INTO wm_director_transition "
                    "(RequestID, Revision, FromState, ToState, Reason) VALUES (%s,%s,%s,%s,%s)",
                    (request.request_id, request.revision + 1, request.state, state, reason[:160]),
                )
                cursor.execute(
                    "SELECT *, TIMESTAMPDIFF(SECOND, UpdatedAt, NOW()) AS AgeSeconds "
                    "FROM wm_director_request WHERE RequestID=%s", (request.request_id,),
                )
                row = cursor.fetchone()
            conn.commit()
            return _request_from_row(row)
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()


def run_durable_native_intent(
    *, ledger: DirectorLedger, origin_key: str, player_guid: int, verb: str,
    proposal: Any, apply: Callable[[], Any], lookup_native: Callable[[str], Any],
) -> dict[str, Any]:
    request = ledger.accept(origin_key=origin_key, player_guid=player_guid, verb=verb, proposal=proposal)
    if request.state in {"verified", "failed"}:
        return {"state": request.state, "request_id": request.request_id, "result": request.result}
    if request.state in {"dispatching", "needs_operator"}:
        receipt = lookup_native(request.native_key)
        if receipt is None:
            if request.state == "dispatching" and request.age_seconds is not None and request.age_seconds >= 30:
                request = ledger.transition(request, state="needs_operator", reason="native_receipt_absent_after_dispatch")
        elif receipt.status == "uncertain":
            if request.state == "dispatching":
                request = ledger.transition(
                    request, state="needs_operator", reason="native_claim_expired_outcome_unknown",
                    native_request_id=receipt.request_id, result=receipt.to_dict(),
                )
        elif receipt.status in {"done", "failed", "rejected", "expired"}:
            request = ledger.transition(
                request, state="verified" if receipt.status == "done" else "failed",
                reason=f"native_receipt_{receipt.status}", native_request_id=receipt.request_id,
                result=receipt.to_dict(),
            )
        return {"state": request.state, "request_id": request.request_id, "result": request.result}
    request = ledger.transition(request, state="dispatching", reason="dispatch_intent_committed")
    try:
        apply_result = apply()
    except Exception:
        # Submission may have succeeded before the exception. Reconcile on next call.
        return {"state": "dispatching", "request_id": request.request_id, "result": None}
    if getattr(apply_result, "status", None) == "rejected":
        request = ledger.transition(request, state="failed", reason="control_rejected_before_native_submit")
        return {"state": request.state, "request_id": request.request_id, "result": request.result}
    receipt = lookup_native(request.native_key)
    if receipt is None:
        request = ledger.transition(request, state="needs_operator", reason="native_receipt_absent_after_apply")
    elif receipt.status == "uncertain":
        request = ledger.transition(
            request, state="needs_operator", reason="native_claim_expired_outcome_unknown",
            native_request_id=receipt.request_id, result=receipt.to_dict(),
        )
    elif receipt.status in {"done", "failed", "rejected", "expired"}:
        request = ledger.transition(
            request, state="verified" if receipt.status == "done" else "failed",
            reason=f"native_receipt_{receipt.status}", native_request_id=receipt.request_id,
            result=receipt.to_dict(),
        )
    return {"state": request.state, "request_id": request.request_id,
            "result": request.result, "apply_status": getattr(apply_result, "status", None)}
