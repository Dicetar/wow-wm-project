"""Scene sequencer: executes typed native action steps in order."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from wm.scenes.models import SceneOutcome, SceneResultKind, SceneStepResult


@dataclass(slots=True)
class SceneStep:
    native_action_kind: str
    payload: dict
    expected_effect: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "native_action_kind": self.native_action_kind,
            "payload": self.payload,
            "expected_effect": self.expected_effect,
        }


@dataclass(slots=True)
class SceneContext:
    scene_key: str
    player_guid: int
    arc_key: str | None = None
    zone_id: int | None = None
    metadata: dict = field(default_factory=dict)


class SceneSequencer:
    """Runs SceneSteps via an injected native bridge; dry_run=True never calls execute."""

    def __init__(self, native_client: Any = None, dry_run: bool = True):
        self._native = native_client
        self.dry_run = dry_run

    def execute(
        self,
        context: SceneContext,
        steps: list[SceneStep],
    ) -> SceneOutcome:
        step_results: list[SceneStepResult] = []
        executed = 0

        for i, step in enumerate(steps):
            if self.dry_run or self._native is None:
                step_results.append(SceneStepResult(
                    step_index=i,
                    native_action_kind=step.native_action_kind,
                    executed=False,
                ))
                continue

            try:
                self._native.send_action(
                    action_kind=step.native_action_kind,
                    payload=step.payload,
                    player_guid=context.player_guid,
                )
                step_results.append(SceneStepResult(
                    step_index=i,
                    native_action_kind=step.native_action_kind,
                    executed=True,
                ))
                executed += 1
            except Exception as exc:
                step_results.append(SceneStepResult(
                    step_index=i,
                    native_action_kind=step.native_action_kind,
                    executed=False,
                    error=str(exc),
                ))
                return SceneOutcome(
                    scene_key=context.scene_key,
                    result="failed",
                    steps_total=len(steps),
                    steps_executed=executed,
                    step_results=step_results,
                    dry_run=self.dry_run,
                    error=str(exc),
                )

        result: SceneResultKind
        if self.dry_run:
            result = "skipped"
        elif executed == len(steps):
            result = "success"
        elif executed > 0:
            result = "partial"
        else:
            result = "failed"

        return SceneOutcome(
            scene_key=context.scene_key,
            result=result,
            steps_total=len(steps),
            steps_executed=executed,
            step_results=step_results,
            dry_run=self.dry_run,
        )
