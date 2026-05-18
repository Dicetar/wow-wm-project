"""Scene outcome and result models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

SceneResultKind = Literal["success", "partial", "failed", "skipped"]


@dataclass(slots=True)
class SceneStepResult:
    step_index: int
    native_action_kind: str
    executed: bool
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "native_action_kind": self.native_action_kind,
            "executed": self.executed,
            "error": self.error,
        }


@dataclass(slots=True)
class SceneOutcome:
    scene_key: str
    result: SceneResultKind
    steps_total: int
    steps_executed: int
    step_results: list[SceneStepResult] = field(default_factory=list)
    dry_run: bool = True
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.result in ("success", "partial")

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_key": self.scene_key,
            "result": self.result,
            "steps_total": self.steps_total,
            "steps_executed": self.steps_executed,
            "dry_run": self.dry_run,
            "ok": self.ok,
            "error": self.error,
            "step_results": [s.to_dict() for s in self.step_results],
        }
