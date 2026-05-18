"""Content-layer letter/mail template models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class WMLetter:
    letter_key: str
    subject_line: str
    body_template: str              # Supports {player}, {zone}, {deed_count}, etc.
    sender_npc_entry: int | None = None
    item_attachments: list[int] = field(default_factory=list)   # item entry IDs
    money_copper: int = 0

    def render_body(self, **kwargs: Any) -> str:
        try:
            return self.body_template.format(**kwargs)
        except KeyError:
            return self.body_template


@dataclass(slots=True)
class LetterDelivery:
    player_guid: int
    letter: WMLetter
    context_vars: dict = field(default_factory=dict)
    delivered_at: str | None = None

    def rendered_body(self) -> str:
        return self.letter.render_body(**self.context_vars)
