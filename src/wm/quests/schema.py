from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QuestTemplateSchema:
    columns: list[str]
    required_for_visibility: set[str]
    safe_to_zero: set[str]

    def validate_draft(self, draft: dict) -> list[str]:
        errors = []
        for col in self.required_for_visibility:
            if col not in draft or draft[col] is None:
                errors.append(f"missing required field: {col}")
        return errors

    @classmethod
    def from_live_db(cls, db_client: Any) -> "QuestTemplateSchema":
        """Query the live quest_template to derive the actual column set."""
        rows = db_client.query("SHOW COLUMNS FROM quest_template")
        columns = [r["Field"] for r in rows]
        required_for_visibility = {
            "ID", "LogTitle", "LogDescription", "QuestDescription",
            "QuestLevel", "MinLevel", "QuestSortID",
        }
        safe_to_zero = {
            "RewardMoney", "RewardBonusMoney", "RewardDisplaySpell",
            "RewardSpell", "RewardHonor", "RewardKillHonor",
            "StartItem", "RequiredPlayerKills",
        }
        return cls(columns=columns, required_for_visibility=required_for_visibility,
                   safe_to_zero=safe_to_zero)
