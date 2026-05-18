"""Quest narrative text models and LLM-driven narrative generator."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class QuestNarrativeText:
    quest_id: int
    log_title: str
    log_description: str
    objective_text: str
    offer_reward_text: str
    request_items_text: str
    quest_completion_log: str
    schema_version: str = "wm.quest_narrative.v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "quest_id": self.quest_id,
            "log_title": self.log_title,
            "log_description": self.log_description,
            "objective_text": self.objective_text,
            "offer_reward_text": self.offer_reward_text,
            "request_items_text": self.request_items_text,
            "quest_completion_log": self.quest_completion_log,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "QuestNarrativeText":
        return cls(
            quest_id=int(d.get("quest_id", 0)),
            log_title=str(d.get("log_title", "")),
            log_description=str(d.get("log_description", "")),
            objective_text=str(d.get("objective_text", "")),
            offer_reward_text=str(d.get("offer_reward_text", "")),
            request_items_text=str(d.get("request_items_text", "")),
            quest_completion_log=str(d.get("quest_completion_log", "")),
            schema_version=str(d.get("schema_version", "wm.quest_narrative.v1")),
        )


_NARRATIVE_SYSTEM = (
    "You write WoW 3.3.5a quest narrative text. "
    "Output only one JSON object with schema_version 'wm.quest_narrative.v1' and the six text fields. "
    "Keep lore-appropriate tone. Do not include SQL, commands, or mutation instructions."
)


class NarrativeGenerator:
    """Builds LLM messages for quest narrative generation and parses the response."""

    def build_messages(
        self,
        *,
        quest_id: int,
        context: dict | None = None,
        instruction: str = "",
    ) -> list[dict[str, str]]:
        user_payload: dict[str, Any] = {
            "schema_version": "wm.quest_narrative.v1",
            "quest_id": quest_id,
            "instruction": instruction or "Write narrative text for this quest.",
        }
        if context:
            user_payload["context"] = context
        return [
            {"role": "system", "content": _NARRATIVE_SYSTEM},
            {"role": "user", "content": json.dumps(user_payload, indent=2, ensure_ascii=False)},
        ]

    def parse_response(self, raw: str) -> QuestNarrativeText:
        from wm.llm.results import parse_json_object
        parsed = parse_json_object(raw)
        return QuestNarrativeText.from_dict(parsed)
