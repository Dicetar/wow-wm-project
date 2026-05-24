from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


TargetKind = Literal["player", "creature"]
EffectState = Literal["active", "ended", "expired", "dispelled"]
EndReason = Literal["ended", "expired", "dispelled"]


@dataclass(slots=True)
class ActiveEffect:
    """A durable ability effect that is alive only while its aura is on the target."""
    effect_key: str
    target_kind: TargetKind
    target_guid: int
    source_player_guid: int
    ability_key: str
    aura_spell_id: int
    effect_kind: str
    effect_params: dict[str, Any]
    state: EffectState
    applied_at: datetime
    expires_at: datetime | None
    ended_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.state == "active"

    @property
    def is_permanent(self) -> bool:
        return self.expires_at is None

    def seconds_remaining(self, now: datetime) -> float | None:
        if self.expires_at is None:
            return None
        delta = (self.expires_at - now).total_seconds()
        return max(0.0, delta)


@dataclass(slots=True)
class EffectApplyRequest:
    target_kind: TargetKind
    target_guid: int
    source_player_guid: int
    ability_key: str
    aura_spell_id: int
    effect_kind: str
    effect_params: dict[str, Any] = field(default_factory=dict)
    duration_seconds: float | None = None


@dataclass(slots=True)
class EffectApplyResult:
    ok: bool
    effect_key: str | None
    effect: ActiveEffect | None
    error: str | None = None


@dataclass(slots=True)
class EffectEndResult:
    ok: bool
    effect_key: str
    reason: EndReason
    error: str | None = None
