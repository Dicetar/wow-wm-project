"""Autonomy governor (Phase 6.1).

The single chokepoint every *autonomous* (unprompted, no per-action human
confirm) action must pass. It enforces a budget over time and a risk ceiling on
top of the existing per-action policy gate -- it can only ever be *more*
restrictive, never a bypass.

Outcomes (encoded by two booleans on GovernorDecision):
  * allow=True,  requires_review=False -> may auto-apply now
  * allow=False, requires_review=True  -> queue for operator review (do not apply)
  * allow=False, requires_review=False -> reject outright (see reason)

Default posture is deliberately cautious: low risk ceiling, modest rate, a
cooldown between actions, so turning autonomy on cannot run away with a live world.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable

# off < low < medium < high
_RISK_ORDER: dict[str, int] = {"off": 0, "low": 1, "medium": 2, "high": 3}


def _risk_rank(risk: str | None) -> int:
    return _RISK_ORDER.get(str(risk or "").strip().lower(), _RISK_ORDER["high"])


@dataclass(slots=True)
class AutonomyBudget:
    max_actions_per_window: int = 6
    window_seconds: int = 600
    max_risk: str = "low"
    cooldown_seconds: int = 120
    per_kind_caps: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> "AutonomyBudget":
        cfg = config or {}
        caps = cfg.get("autonomy_per_kind_caps")
        return cls(
            max_actions_per_window=int(cfg.get("autonomy_per_window") or 6),
            window_seconds=int(cfg.get("autonomy_window_seconds") or 600),
            max_risk=str(cfg.get("autonomy_max_risk") or "low").strip().lower(),
            cooldown_seconds=int(cfg.get("autonomy_cooldown_seconds") or 120),
            per_kind_caps=dict(caps) if isinstance(caps, dict) else {},
        )


@dataclass(slots=True)
class GovernorDecision:
    allow: bool
    reason: str = ""
    requires_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"allow": self.allow, "requires_review": self.requires_review, "reason": self.reason}


def _coerce_at(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        text = value.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
    return None


class AutonomyGovernor:
    def __init__(self, budget: AutonomyBudget | None = None) -> None:
        self.budget = budget or AutonomyBudget()

    def evaluate(
        self,
        *,
        action_kind: str,
        risk: str,
        recent_actions: Iterable[dict[str, Any]] | None = None,
        now: datetime,
        mutating: bool = True,
    ) -> GovernorDecision:
        """Decide whether an autonomous action may auto-apply, queue, or be rejected.

        ``recent_actions`` are prior autonomous actions, each a dict with at least
        ``at`` (datetime or ISO string) and ``action_kind``.
        """
        budget = self.budget
        max_rank = _risk_rank(budget.max_risk)
        risk_rank = _risk_rank(risk)

        # 1. Hard risk ceiling.
        if max_rank == _RISK_ORDER["off"]:
            return GovernorDecision(allow=False, reason="autonomy risk ceiling is off")
        if risk_rank > max_rank:
            return GovernorDecision(allow=False, reason=f"risk {risk!r} exceeds max {budget.max_risk!r}")

        # Bucket recent actions inside the rolling window.
        window_start = now - timedelta(seconds=max(1, budget.window_seconds))
        in_window: list[tuple[datetime, str]] = []
        for item in recent_actions or []:
            at = _coerce_at(item.get("at"))
            if at is None or at < window_start:
                continue
            in_window.append((at, str(item.get("action_kind") or "")))

        # 2. Global rate cap.
        if len(in_window) >= max(0, budget.max_actions_per_window):
            return GovernorDecision(allow=False, reason="autonomy action budget exhausted for window")

        # 3. Per-kind cap.
        kind_cap = budget.per_kind_caps.get(action_kind)
        if kind_cap is not None:
            kind_count = sum(1 for _at, kind in in_window if kind == action_kind)
            if kind_count >= max(0, int(kind_cap)):
                return GovernorDecision(allow=False, reason=f"per-kind cap reached for {action_kind!r}")

        # 4. Cooldown since the most recent action.
        if budget.cooldown_seconds > 0 and in_window:
            latest = max(at for at, _kind in in_window)
            if (now - latest).total_seconds() < budget.cooldown_seconds:
                return GovernorDecision(allow=False, reason="autonomy cooldown active")

        # 5. At-ceiling mutating actions are queued for operator review, never auto-applied.
        if mutating and risk_rank == max_rank and risk_rank > _RISK_ORDER["low"]:
            return GovernorDecision(allow=False, requires_review=True,
                                    reason=f"{risk!r} is at the ceiling; queued for review")

        return GovernorDecision(allow=True, reason="within budget")
