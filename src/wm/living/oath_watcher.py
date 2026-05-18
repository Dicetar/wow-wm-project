"""OathWatcher: evaluates and persists oath state from wm_oath table."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from wm.living.oath import OathDecision, OathTrigger, evaluate_oath


@dataclass(slots=True)
class OathState:
    player_guid: int
    oath_key: str
    constraint_label: str
    target_count: int
    current_count: int
    phase: str
    oath_quest_id: int | None

    def to_trigger(self) -> OathTrigger:
        return OathTrigger(
            player_guid=self.player_guid,
            player_name=str(self.player_guid),
            oath_key=self.oath_key,
            constraint_label=self.constraint_label,
            target_count=self.target_count,
            current_count=self.current_count,
            phase=self.phase,
            oath_quest_id=self.oath_quest_id,
        )


class OathWatcher:
    """Tracks oath progress and evaluates resolve outcomes."""

    def __init__(self, db_client: Any = None):
        self._db = db_client

    def load(self, player_guid: int, oath_key: str) -> OathState | None:
        if self._db is None:
            return None
        rows = self._db.query(
            "SELECT constraint_label, target_count, current_count, phase, oath_quest_id "
            "FROM wm_oath WHERE player_guid = %s AND oath_key = %s",
            (player_guid, oath_key),
        )
        if not rows:
            return None
        r = rows[0]
        return OathState(
            player_guid=player_guid,
            oath_key=oath_key,
            constraint_label=r.get("constraint_label", ""),
            target_count=int(r.get("target_count", 1)),
            current_count=int(r.get("current_count", 0)),
            phase=r.get("phase", "accept"),
            oath_quest_id=r.get("oath_quest_id"),
        )

    def swear(self, player_guid: int, oath_key: str, constraint_label: str,
              target_count: int, oath_quest_id: int | None = None) -> None:
        if self._db is None:
            return
        self._db.execute(
            """
            INSERT INTO wm_oath
                (player_guid, oath_key, constraint_label, target_count, current_count, phase, oath_quest_id)
            VALUES (%s, %s, %s, %s, 0, 'accept', %s)
            ON DUPLICATE KEY UPDATE
                constraint_label = VALUES(constraint_label),
                target_count = VALUES(target_count),
                current_count = 0,
                phase = 'accept',
                oath_quest_id = VALUES(oath_quest_id),
                updated_at = NOW()
            """,
            (player_guid, oath_key, constraint_label, target_count, oath_quest_id),
        )

    def increment(self, player_guid: int, oath_key: str, delta: int = 1) -> None:
        if self._db is None:
            return
        self._db.execute(
            "UPDATE wm_oath SET current_count = current_count + %s, updated_at = NOW() "
            "WHERE player_guid = %s AND oath_key = %s AND phase = 'accept'",
            (delta, player_guid, oath_key),
        )

    def evaluate(self, player_guid: int, oath_key: str,
                 player_name: str = "") -> OathDecision | None:
        state = self.load(player_guid, oath_key)
        if state is None:
            return None
        trigger = OathTrigger(
            player_guid=player_guid,
            player_name=player_name or str(player_guid),
            oath_key=oath_key,
            constraint_label=state.constraint_label,
            target_count=state.target_count,
            current_count=state.current_count,
            phase="resolve",
            oath_quest_id=state.oath_quest_id,
        )
        decision = evaluate_oath(trigger)
        if decision.eligible and decision.plan and decision.plan.outcome is not None:
            if self._db is not None:
                self._db.execute(
                    "UPDATE wm_oath SET phase = 'resolve', updated_at = NOW() "
                    "WHERE player_guid = %s AND oath_key = %s",
                    (player_guid, oath_key),
                )
        return decision
