import io
import json
import shutil
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from wm.control import apply as control_apply
from wm.control._cli import load_proposal
from wm.control.coordinator import ControlExecutionResult
from wm.control.models import ControlValidationResult
from wm.events.models import ExecutionResult
from wm.events.models import ExecutionStepResult
from wm.events.models import ReactionPlan
from wm.events.models import SubjectRef


class FakeCoordinator:
    def execute(self, *, proposal, mode, confirm_live_apply=False):
        del mode, confirm_live_apply
        plan = ReactionPlan(
            plan_key=proposal.idempotency_key,
            opportunity_type="control:manual_admin_action",
            rule_type="manual_admin_action",
            player_guid=proposal.player.guid,
            subject=SubjectRef(subject_type="control", subject_entry=0),
        )
        applied = ExecutionResult(
            mode="apply",
            plan=plan,
            status="applied",
            steps=[
                ExecutionStepResult(
                    kind="native_bridge_action",
                    status="applied",
                    details={
                        "request": {
                            "request_id": 44,
                            "idempotency_key": "control:test:native:debug_ping",
                            "player_guid": 5406,
                            "action_kind": "debug_ping",
                            "status": "done",
                        }
                    },
                )
            ],
        )
        return ControlExecutionResult(
            status="applied",
            proposal=proposal,
            validation=ControlValidationResult(ok=True, issues=[]),
            dry_run=ExecutionResult(mode="preview", plan=plan, status="preview", steps=[]),
            applied=applied,
            issues=[],
        )


def _proposal_path(root: Path) -> Path:
    payload = {
        "schema_version": "control.proposal.v1",
        "player": {"guid": 5406, "name": "Jecia"},
        "selected_recipe": "manual_admin_action",
        "action": {"kind": "native_bridge_action", "payload": {"native_action_kind": "debug_ping", "payload": {}}},
        "rationale": "Test debug ping.",
        "risk": {"level": "low", "irreversible": False, "notes": []},
        "idempotency_key": "control:test",
        "expected_effect": "Native debug ping reaches done.",
        "author": {"kind": "manual_admin", "name": "test", "manual_reason": "summary test"},
        "metadata": {},
    }
    path = root / "proposal.json"
    path.write_text(json.dumps(payload), encoding="utf-8-sig")
    load_proposal(path)
    return path


class ControlApplyCliTests(unittest.TestCase):
    def test_apply_summary_exposes_native_request(self) -> None:
        temp_dir = Path(".tmp/test_control_apply_cli")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        try:
            temp_dir.mkdir(parents=True)
            proposal_path = _proposal_path(temp_dir)
            output = io.StringIO()
            with patch.object(control_apply, "build_live_coordinator", return_value=FakeCoordinator()), redirect_stdout(output):
                exit_code = control_apply.main(["--proposal", str(proposal_path), "--mode", "apply", "--confirm-live-apply", "--summary"])
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

        self.assertEqual(exit_code, 0)
        rendered = output.getvalue()
        self.assertIn("idempotency_key=control:test", rendered)
        self.assertIn("audit_status=applied", rendered)
        self.assertIn("request_id=44", rendered)
        self.assertIn("action_kind=debug_ping", rendered)


if __name__ == "__main__":
    unittest.main()
