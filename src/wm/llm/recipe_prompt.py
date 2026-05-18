"""LLM recipe prompts: structured prompt builder for WM recipe schemas."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

RECIPE_SCHEMA = {
    "schema_version": "wm.recipe.v1",
    "type": "object",
    "required": ["schema_version", "recipe_key", "title", "steps"],
    "properties": {
        "schema_version": {"type": "string"},
        "recipe_key": {"type": "string"},
        "title": {"type": "string"},
        "description": {"type": "string"},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["step_key", "action"],
                "properties": {
                    "step_key": {"type": "string"},
                    "action": {"type": "string"},
                    "params": {"type": "object"},
                },
            },
        },
        "metadata": {"type": "object"},
    },
}

_RECIPE_SYSTEM = (
    "You generate WM recipe drafts. Output only one JSON object matching the recipe schema. "
    "Do not include SQL, shell commands, config edits, or any direct mutation instructions. "
    "Each step must specify a named WM action with typed parameters. "
    "If required context is missing, return a conservative draft with empty steps."
)


@dataclass(slots=True)
class LLMPrompt:
    schema_version: str
    system: str
    user_payload: dict

    def to_messages(self) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": self.system},
            {"role": "user", "content": json.dumps(self.user_payload, indent=2,
                                                     ensure_ascii=False, sort_keys=True)},
        ]


class RecipePromptBuilder:
    """Builds LLMPrompt objects for WM recipe generation."""

    def build(
        self,
        *,
        instruction: str,
        recipe_key: str | None = None,
        context_pack: Any = None,
        extra: dict | None = None,
    ) -> LLMPrompt:
        user_payload: dict[str, Any] = {
            "schema_version": "wm.recipe.v1",
            "instruction": instruction,
        }
        if recipe_key:
            user_payload["recipe_key"] = recipe_key
        if context_pack is not None:
            user_payload["context_pack"] = context_pack
        if extra:
            user_payload.update(extra)
        return LLMPrompt(
            schema_version="wm.recipe.v1",
            system=_RECIPE_SYSTEM,
            user_payload=user_payload,
        )
