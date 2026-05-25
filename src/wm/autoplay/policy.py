from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


RISK_ORDER = {"low": 1, "medium": 2, "high": 3}

SCHEMA_LANE: dict[str, str] = {
    "wm.quest.release.repeatable_bounty.v1": "quest",
    "wm.quest.release.one_shot.v1": "quest",
    "wm.item.release.managed_power.v1": "item",
    "wm.ability.release.shell_power.v1": "ability",
    "wm.scene.release.native_sequence.v1": "scene",
    "control.proposal.v1": "action",
}

DBC_BACKED_SCHEMAS = {
    "wm.ability.release.shell_power.v1",
    "wm.spell.release.managed_spell.v1",
}

LANES_REQUIRING_ROLLBACK = {"quest", "item", "spell"}


@dataclass(slots=True)
class SafeWindow:
    client_running: bool = False
    scoped_player_online: bool = False

    @property
    def ok_for_dbc_apply(self) -> bool:
        return not self.client_running and not self.scoped_player_online

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AutoplayPolicy:
    max_auto_risk: str = "low"
    enabled_lanes: set[str] = field(default_factory=lambda: {"quest", "item", "spell", "ability", "scene", "action"})
    lane_budgets: dict[str, int] = field(default_factory=lambda: {
        "quest": 2,
        "item": 1,
        "spell": 1,
        "ability": 1,
        "scene": 3,
        "action": 5,
    })
    max_source_event_age_seconds: int = 3600
    require_rollback_for_lanes: set[str] = field(default_factory=lambda: set(LANES_REQUIRING_ROLLBACK))

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_auto_risk": self.max_auto_risk,
            "enabled_lanes": sorted(self.enabled_lanes),
            "lane_budgets": dict(self.lane_budgets),
            "max_source_event_age_seconds": self.max_source_event_age_seconds,
            "require_rollback_for_lanes": sorted(self.require_rollback_for_lanes),
        }

    def decide(
        self,
        *,
        schema_version: str,
        payload: dict[str, Any] | None = None,
        lane: str | None = None,
        risk: str = "low",
        readiness_ok: bool = False,
        lm_ok: bool = False,
        session_ok: bool = False,
        source_event_at: str | None = None,
        dry_run_ok: bool = False,
        rollback_available: bool = False,
        idempotency_seen: bool = False,
        lane_applied_count: int = 0,
        safe_window: SafeWindow | None = None,
        now: datetime | None = None,
    ) -> "PolicyDecision":
        resolved_lane = lane or SCHEMA_LANE.get(schema_version, "unknown")
        blockers: list[str] = []
        maintenance: list[str] = []
        safe_window = safe_window or SafeWindow()

        if resolved_lane not in self.enabled_lanes:
            blockers.append(f"lane_disabled:{resolved_lane}")
        if _risk_rank(risk) > _risk_rank(self.max_auto_risk):
            blockers.append(f"risk_exceeds_policy:{risk}>{self.max_auto_risk}")
        if not readiness_ok:
            blockers.append("readiness_not_green")
        if not lm_ok:
            blockers.append("llm_unavailable")
        if not session_ok:
            blockers.append("no_active_session")
        if source_event_at and self._source_event_stale(source_event_at, now=now):
            blockers.append("source_event_stale")
        if not dry_run_ok:
            blockers.append("dry_run_not_successful")
        if idempotency_seen:
            blockers.append("idempotency_already_seen")
        if int(lane_applied_count) >= int(self.lane_budgets.get(resolved_lane, 0)):
            blockers.append(f"lane_budget_exhausted:{resolved_lane}")
        if resolved_lane in self.require_rollback_for_lanes and not rollback_available:
            blockers.append(f"rollback_missing:{resolved_lane}")

        if _requires_dbc_staging(schema_version=schema_version, lane=resolved_lane, payload=payload or {}):
            if not safe_window.ok_for_dbc_apply:
                maintenance.append("dbc_safe_window_required")

        status = "allow"
        if blockers:
            status = "blocked"
        elif maintenance:
            status = "maintenance_pending"
        return PolicyDecision(
            ok=status == "allow",
            status=status,
            lane=resolved_lane,
            schema_version=schema_version,
            blockers=blockers,
            maintenance_reasons=maintenance,
            safe_window=safe_window.to_dict(),
        )

    def _source_event_stale(self, source_event_at: str, *, now: datetime | None = None) -> bool:
        try:
            parsed = datetime.fromisoformat(source_event_at.replace("Z", "+00:00"))
        except ValueError:
            return True
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        return (current - parsed).total_seconds() > int(self.max_source_event_age_seconds)


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    ok: bool
    status: str
    lane: str
    schema_version: str
    blockers: list[str]
    maintenance_reasons: list[str]
    safe_window: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _risk_rank(risk: str) -> int:
    return RISK_ORDER.get(str(risk or "high").lower(), 999)


def _requires_dbc_staging(*, schema_version: str, lane: str, payload: dict[str, Any]) -> bool:
    if schema_version in DBC_BACKED_SCHEMAS:
        return True
    if lane in {"spell", "ability"}:
        return True
    client_truth = payload.get("client_truth") if isinstance(payload.get("client_truth"), dict) else {}
    return bool(client_truth.get("client_patch_required") or client_truth.get("server_dbc_required"))
