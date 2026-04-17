from __future__ import annotations

import io
import json
import shutil
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from wm.control import scene_play
from wm.control.coordinator import ControlExecutionResult
from wm.control.scene_play import build_scene_proposal
from wm.control.scene_play import load_scene
from wm.control.models import ControlValidationResult
from wm.events.models import ExecutionResult
from wm.events.models import ExecutionStepResult
from wm.events.models import ReactionPlan
from wm.events.models import SubjectRef


class FakeSceneCoordinator:
    def execute(self, *, proposal, mode, confirm_live_apply=False):
        del confirm_live_apply
        plan = ReactionPlan(
            plan_key=proposal.idempotency_key,
            opportunity_type="control:manual_admin_action",
            rule_type="manual_admin_action",
            player_guid=proposal.player.guid,
            subject=SubjectRef(subject_type="control", subject_entry=0),
        )
        execution = ExecutionResult(
            mode="apply" if mode == "apply" else "preview",
            plan=plan,
            status="applied" if mode == "apply" else "preview",
            steps=[
                ExecutionStepResult(
                    kind="native_bridge_action",
                    status="applied" if mode == "apply" else "preview",
                    details={
                        "request": {
                            "request_id": 52,
                            "idempotency_key": f"{proposal.idempotency_key}:native",
                            "player_guid": proposal.player.guid,
                            "action_kind": proposal.action.payload["native_action_kind"],
                            "status": "done",
                        }
                    },
                )
            ],
        )
        return ControlExecutionResult(
            status="applied" if mode == "apply" else "dry-run",
            proposal=proposal,
            validation=ControlValidationResult(ok=True, issues=[]),
            dry_run=execution if mode == "dry-run" else None,
            applied=execution if mode == "apply" else None,
            issues=[],
        )


class ControlScenePlayTests(unittest.TestCase):
    def test_loads_bundled_scene_and_materializes_payload(self) -> None:
        scene = load_scene(scene_ref="summon_marker", control_root=Path("control"))

        self.assertEqual(scene.scene_id, "summon_marker")
        self.assertEqual(scene.steps[0].native_action_kind, "creature_spawn")

        proposal = build_scene_proposal(
            scene=scene,
            step=scene.steps[0],
            index=0,
            player_guid=5406,
            player_name="Jecia",
            run_key="test-run",
            manual_reason="unit test",
        )

        self.assertEqual(proposal.selected_recipe, "manual_admin_action")
        self.assertEqual(proposal.action.kind, "native_bridge_action")
        self.assertEqual(proposal.action.payload["native_action_kind"], "creature_spawn")
        native_payload = proposal.action.payload["payload"]
        self.assertEqual(native_payload["arc_key"], "scene:summon_marker:5406:test-run")
        self.assertEqual(proposal.idempotency_key, "control:scene:summon_marker:5406:test-run:0:spawn")

    def test_bundled_scenes_use_only_registered_native_payload_shape(self) -> None:
        for scene_id in ("field_medic_pulse", "bonebound_battle_cry", "summon_marker", "arcane_marker_demo"):
            with self.subTest(scene_id=scene_id):
                scene = load_scene(scene_ref=scene_id, control_root=Path("control"))
                for index, step in enumerate(scene.steps):
                    proposal = build_scene_proposal(
                        scene=scene,
                        step=step,
                        index=index,
                        player_guid=5406,
                        player_name=None,
                        run_key="shape",
                        manual_reason="unit test",
                    )
                    self.assertIn("native_action_kind", proposal.action.payload)
                    self.assertIn("payload", proposal.action.payload)
                    self.assertIsInstance(proposal.action.payload["payload"], dict)
                    self.assertIn(proposal.risk.level, {"low", "medium", "high"})

    def test_load_scene_rejects_unknown_native_action_kind(self) -> None:
        temp_dir = Path(".tmp/test_control_scene_play_unknown")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        try:
            temp_dir.mkdir(parents=True)
            scene_path = temp_dir / "bad_scene.json"
            scene_path.write_text(
                json.dumps(
                    {
                        "id": "bad_scene",
                        "schema_version": "control.scene.v1",
                        "steps": [
                            {
                                "native_action_kind": "not_a_real_action",
                                "payload": {},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unknown native action kind"):
                load_scene(scene_ref=str(scene_path), control_root=Path("control"))
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def test_load_scene_rejects_unimplemented_native_action_kind(self) -> None:
        temp_dir = Path(".tmp/test_control_scene_play_unimplemented")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        try:
            temp_dir.mkdir(parents=True)
            scene_path = temp_dir / "bad_scene.json"
            scene_path.write_text(
                json.dumps(
                    {
                        "id": "bad_scene",
                        "schema_version": "control.scene.v1",
                        "steps": [
                            {
                                "native_action_kind": "player_teleport",
                                "payload": {"map_id": 0},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unimplemented native action kind"):
                load_scene(scene_ref=str(scene_path), control_root=Path("control"))
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def test_scene_play_summary_exposes_native_requests(self) -> None:
        output = io.StringIO()
        with patch.object(scene_play, "build_live_coordinator", return_value=FakeSceneCoordinator()), redirect_stdout(output):
            exit_code = scene_play.main(
                [
                    "--scene",
                    "field_medic_pulse",
                    "--player-guid",
                    "5406",
                    "--mode",
                    "dry-run",
                    "--run-key",
                    "unit-test",
                    "--summary",
                ]
            )

        self.assertEqual(exit_code, 0)
        rendered = output.getvalue()
        self.assertIn("scene_id=field_medic_pulse", rendered)
        self.assertIn("run_key=unit-test", rendered)
        self.assertIn("step=0 native_action_kind=player_restore_health_power", rendered)
        self.assertIn("request_id=52", rendered)
        self.assertIn("action_kind=player_apply_aura", rendered)


if __name__ == "__main__":
    unittest.main()
