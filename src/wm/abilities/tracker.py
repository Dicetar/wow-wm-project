from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any

from wm.abilities.models import (
    ActiveEffect,
    EffectApplyRequest,
    EffectApplyResult,
    EffectEndResult,
    EffectState,
    EndReason,
    TargetKind,
)


def _make_effect_key(ability_key: str, target_kind: str, target_guid: int) -> str:
    raw = f"{ability_key}:{target_kind}:{target_guid}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24] + f"_{target_guid}"


def _row_to_effect(row: dict[str, Any]) -> ActiveEffect:
    params_raw = row.get("effect_params_json") or "{}"
    if isinstance(params_raw, str):
        params = json.loads(params_raw)
    else:
        params = params_raw or {}
    return ActiveEffect(
        effect_key=row["effect_key"],
        target_kind=row["target_kind"],
        target_guid=int(row["target_guid"]),
        source_player_guid=int(row["source_player_guid"]),
        ability_key=row["ability_key"],
        aura_spell_id=int(row["aura_spell_id"]),
        effect_kind=row["effect_kind"],
        effect_params=params,
        state=row["state"],
        applied_at=row["applied_at"] if isinstance(row["applied_at"], datetime) else datetime.fromisoformat(str(row["applied_at"])),
        expires_at=row["expires_at"] if (row.get("expires_at") is None or isinstance(row.get("expires_at"), datetime)) else datetime.fromisoformat(str(row["expires_at"])),
        ended_at=row.get("ended_at"),
    )


class ActiveEffectTracker:
    """
    Tracks durable ability effects bound to their aura tokens.

    Contract:
      - apply() dispatches aura + records effect row (state='active')
      - Any periodic/tick logic must call is_active() before firing; if False, skip
      - end()/on_dispelled() marks state and must be followed by remove_aura dispatch
      - expire_due() scans for rows past expires_at and ends them

    No aura on target = no effect. This class is the enforcement point.
    """

    def __init__(self, db_client=None) -> None:
        self._db = db_client

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------

    def apply(self, req: EffectApplyRequest) -> EffectApplyResult:
        effect_key = _make_effect_key(req.ability_key, req.target_kind, req.target_guid)
        now = datetime.utcnow()
        expires_at = (now + timedelta(seconds=req.duration_seconds)) if req.duration_seconds is not None else None
        params_json = json.dumps(req.effect_params, ensure_ascii=False) if req.effect_params else None

        if self._db is None:
            effect = ActiveEffect(
                effect_key=effect_key,
                target_kind=req.target_kind,
                target_guid=req.target_guid,
                source_player_guid=req.source_player_guid,
                ability_key=req.ability_key,
                aura_spell_id=req.aura_spell_id,
                effect_kind=req.effect_kind,
                effect_params=req.effect_params,
                state="active",
                applied_at=now,
                expires_at=expires_at,
            )
            return EffectApplyResult(ok=True, effect_key=effect_key, effect=effect)

        try:
            expires_sql = f"'{expires_at.strftime('%Y-%m-%d %H:%M:%S')}'" if expires_at else "NULL"
            params_sql = f"'{params_json.replace(chr(39), chr(39)*2)}'" if params_json else "NULL"
            sql = (
                "INSERT INTO wm_active_effect "
                "(effect_key, target_kind, target_guid, source_player_guid, ability_key, "
                " aura_spell_id, effect_kind, effect_params_json, state, applied_at, expires_at) "
                f"VALUES ('{effect_key}', '{req.target_kind}', {req.target_guid}, "
                f"{req.source_player_guid}, '{req.ability_key}', {req.aura_spell_id}, "
                f"'{req.effect_kind}', {params_sql}, 'active', "
                f"'{now.strftime('%Y-%m-%d %H:%M:%S')}', {expires_sql}) "
                "ON DUPLICATE KEY UPDATE "
                "state='active', applied_at=VALUES(applied_at), expires_at=VALUES(expires_at), "
                "ended_at=NULL, effect_params_json=VALUES(effect_params_json)"
            )
            self._db.execute(sql)
            effect = ActiveEffect(
                effect_key=effect_key,
                target_kind=req.target_kind,
                target_guid=req.target_guid,
                source_player_guid=req.source_player_guid,
                ability_key=req.ability_key,
                aura_spell_id=req.aura_spell_id,
                effect_kind=req.effect_kind,
                effect_params=req.effect_params,
                state="active",
                applied_at=now,
                expires_at=expires_at,
            )
            return EffectApplyResult(ok=True, effect_key=effect_key, effect=effect)
        except Exception as exc:
            return EffectApplyResult(ok=False, effect_key=effect_key, effect=None, error=str(exc))

    # ------------------------------------------------------------------
    # End / dispel
    # ------------------------------------------------------------------

    def end(self, effect_key: str, reason: EndReason = "ended") -> EffectEndResult:
        """Mark effect as ended. Caller must also dispatch remove_aura to native bridge."""
        if self._db is None:
            return EffectEndResult(ok=True, effect_key=effect_key, reason=reason)
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        try:
            self._db.execute(
                f"UPDATE wm_active_effect SET state='{reason}', ended_at='{now}' "
                f"WHERE effect_key='{effect_key}' AND state='active'"
            )
            return EffectEndResult(ok=True, effect_key=effect_key, reason=reason)
        except Exception as exc:
            return EffectEndResult(ok=False, effect_key=effect_key, reason=reason, error=str(exc))

    def on_dispelled(self, *, target_guid: int, target_kind: TargetKind, aura_spell_id: int) -> list[EffectEndResult]:
        """
        Called when C++ reports the aura was removed (dispel, death, manual removal).
        Ends all active effects on this target bound to this aura_spell_id.
        """
        effects = self.get_active_by_aura(target_guid=target_guid, target_kind=target_kind, aura_spell_id=aura_spell_id)
        return [self.end(e.effect_key, reason="dispelled") for e in effects]

    # ------------------------------------------------------------------
    # Query / gate
    # ------------------------------------------------------------------

    def is_active(self, *, target_guid: int, target_kind: TargetKind, aura_spell_id: int) -> bool:
        """
        The tick gate. Call before applying any periodic effect.
        Returns True only if the aura is still tracked as active on the target.
        """
        if self._db is None:
            return False
        try:
            rows = self._db.query(
                f"SELECT id FROM wm_active_effect "
                f"WHERE target_guid={target_guid} AND target_kind='{target_kind}' "
                f"AND aura_spell_id={aura_spell_id} AND state='active' LIMIT 1"
            )
            return bool(rows)
        except Exception:
            return False

    def load(self, effect_key: str) -> ActiveEffect | None:
        if self._db is None:
            return None
        try:
            rows = self._db.query(
                f"SELECT * FROM wm_active_effect WHERE effect_key='{effect_key}' LIMIT 1"
            )
            return _row_to_effect(rows[0]) if rows else None
        except Exception:
            return None

    def get_active(self, *, target_guid: int, target_kind: TargetKind) -> list[ActiveEffect]:
        """All active effects on a target, regardless of aura."""
        if self._db is None:
            return []
        try:
            rows = self._db.query(
                f"SELECT * FROM wm_active_effect "
                f"WHERE target_guid={target_guid} AND target_kind='{target_kind}' AND state='active'"
            )
            return [_row_to_effect(r) for r in rows]
        except Exception:
            return []

    def get_active_by_aura(self, *, target_guid: int, target_kind: TargetKind, aura_spell_id: int) -> list[ActiveEffect]:
        """Active effects on a target bound to a specific aura spell ID."""
        if self._db is None:
            return []
        try:
            rows = self._db.query(
                f"SELECT * FROM wm_active_effect "
                f"WHERE target_guid={target_guid} AND target_kind='{target_kind}' "
                f"AND aura_spell_id={aura_spell_id} AND state='active'"
            )
            return [_row_to_effect(r) for r in rows]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Expiry sweep
    # ------------------------------------------------------------------

    def expire_due(self, now: datetime | None = None) -> list[EffectEndResult]:
        """
        Find all active effects whose expires_at has passed and end them.
        Call periodically from the watch loop or on-demand before a tick fires.
        """
        if self._db is None:
            return []
        cutoff = (now or datetime.utcnow()).strftime("%Y-%m-%d %H:%M:%S")
        try:
            rows = self._db.query(
                f"SELECT effect_key FROM wm_active_effect "
                f"WHERE state='active' AND expires_at IS NOT NULL AND expires_at <= '{cutoff}'"
            )
        except Exception:
            return []
        return [self.end(r["effect_key"], reason="expired") for r in rows]
