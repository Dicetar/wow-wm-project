"""Living World mentor: tracks player progress through MentorTask steps."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from wm.content.mentor_task import MentorStep, MentorTask

MentorStatus = Literal["active", "complete", "abandoned"]


@dataclass(slots=True)
class MentorProgress:
    player_guid: int
    task_key: str
    mentor_npc_entry: int
    current_step_key: str | None
    completed_steps: list[str]
    status: MentorStatus

    def is_step_done(self, step_key: str) -> bool:
        return step_key in self.completed_steps

    def to_dict(self) -> dict[str, Any]:
        return {
            "player_guid": self.player_guid,
            "task_key": self.task_key,
            "mentor_npc_entry": self.mentor_npc_entry,
            "current_step_key": self.current_step_key,
            "completed_steps": self.completed_steps,
            "status": self.status,
        }


class MentorManager:
    def __init__(self, db_client: Any = None):
        self._db = db_client

    def get_progress(self, player_guid: int, task_key: str) -> MentorProgress | None:
        if self._db is None:
            return None
        rows = self._db.query(
            "SELECT mentor_npc_entry, current_step_key, completed_steps, status "
            "FROM wm_mentor_relationship WHERE player_guid = %s AND task_key = %s",
            (player_guid, task_key),
        )
        if not rows:
            return None
        r = rows[0]
        raw = r.get("completed_steps")
        completed = json.loads(raw) if raw else []
        return MentorProgress(
            player_guid=player_guid,
            task_key=task_key,
            mentor_npc_entry=int(r["mentor_npc_entry"]),
            current_step_key=r.get("current_step_key"),
            completed_steps=completed,
            status=r.get("status", "active"),
        )

    def start_task(self, player_guid: int, task: MentorTask) -> None:
        if self._db is None:
            return
        first_step = task.steps[0].step_key if task.steps else None
        self._db.execute(
            """
            INSERT INTO wm_mentor_relationship
                (player_guid, mentor_npc_entry, task_key, current_step_key, completed_steps, status)
            VALUES (%s, %s, %s, %s, '[]', 'active')
            ON DUPLICATE KEY UPDATE
                current_step_key = VALUES(current_step_key),
                status = 'active',
                updated_at = NOW()
            """,
            (player_guid, task.mentor_npc_entry, task.task_key, first_step),
        )

    def advance_step(
        self,
        player_guid: int,
        task: MentorTask,
        completed_step_key: str,
    ) -> MentorProgress | None:
        if self._db is None:
            return None
        progress = self.get_progress(player_guid, task.task_key)
        if progress is None:
            return None

        completed = list(progress.completed_steps)
        if completed_step_key not in completed:
            completed.append(completed_step_key)

        step_keys = [s.step_key for s in task.steps]
        remaining = [k for k in step_keys if k not in completed]
        next_step = remaining[0] if remaining else None
        status: MentorStatus = "complete" if not remaining else "active"

        self._db.execute(
            """
            UPDATE wm_mentor_relationship
            SET current_step_key = %s, completed_steps = %s, status = %s, updated_at = NOW()
            WHERE player_guid = %s AND task_key = %s
            """,
            (next_step, json.dumps(completed), status, player_guid, task.task_key),
        )
        return MentorProgress(
            player_guid=player_guid,
            task_key=task.task_key,
            mentor_npc_entry=task.mentor_npc_entry,
            current_step_key=next_step,
            completed_steps=completed,
            status=status,
        )
