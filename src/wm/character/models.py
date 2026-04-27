from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CharacterProfile:
    character_guid: int
    character_name: str
    wm_persona: str = "default"
    tone: str = "adaptive"
    preferred_themes: list[str] = field(default_factory=list)
    avoided_themes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ArcState:
    character_guid: int
    arc_key: str
    stage_key: str
    status: str = "active"
    branch_key: str | None = None
    summary: str | None = None


@dataclass(slots=True)
class CharacterUnlock:
    character_guid: int
    unlock_kind: str
    unlock_id: int
    source_arc_key: str | None = None
    source_quest_id: int | None = None
    grant_method: str = "control"
    bot_eligible: bool = False


@dataclass(slots=True)
class RewardInstance:
    character_guid: int
    reward_kind: str
    template_id: int
    source_arc_key: str | None = None
    source_quest_id: int | None = None
    is_equipped_gate: bool = False


@dataclass(slots=True)
class PromptQueueEntry:
    character_guid: int
    prompt_kind: str
    body: str
    queue_id: int | None = None
    is_consumed: bool = False
    created_at: str | None = None


@dataclass(slots=True)
class ConversationSteeringNote:
    character_guid: int
    steering_key: str
    body: str
    steering_kind: str = "player_preference"
    priority: int = 0
    source: str = "operator"
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
