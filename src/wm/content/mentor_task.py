"""Content-layer mentor task template models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

StepStatus = Literal["pending", "complete", "failed"]


@dataclass(slots=True)
class MentorStep:
    step_key: str
    objective_text: str
    required_event_type: str    # e.g. "kill", "talk", "skinning"
    target_entry: int | None = None
    count: int = 1


@dataclass(slots=True)
class MentorTask:
    task_key: str
    mentor_npc_entry: int
    steps: list[MentorStep]
    reward_ref: str | None = None
    min_player_level: int = 1
    description: str = ""

    def total_steps(self) -> int:
        return len(self.steps)

    def step_by_key(self, step_key: str) -> MentorStep | None:
        for s in self.steps:
            if s.step_key == step_key:
                return s
        return None
