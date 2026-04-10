import os
import unittest

from wm.control.builder import build_manual_proposal
from wm.control.coordinator import ControlCoordinator
from wm.control.registry import ControlRegistry
from wm.events.models import ExecutionResult
from wm.events.models import ExecutionStepResult
from wm.events.models import WMEvent


class FakeEventStore:
    def __init__(self, event: WMEvent) -> None:
        self.event = event

    def get_event(self, *, event_id: int):
        if self.event.event_id == event_id:
            return self.event
        return None

    def get_event_by_source_key(self, *, source: str, source_event_key: str):
        if self.event.source == source and self.event.source_event_key == source_event_key:
            return self.event
        return None


class FakeExecutor:
    def __init__(self) -> None:
        self.preview_calls = []
        self.apply_calls = []

    def preview(self, *, plan):
        self.preview_calls.append(plan)
        return ExecutionResult(
            mode="preview",
            plan=plan,
            status="preview",
            steps=[ExecutionStepResult(kind=plan.actions[0].kind, status="dry-run", details={})],
        )

    def execute(self, *, plan, mode: str):
        self.apply_calls.append((plan, mode))
        return ExecutionResult(
            mode=mode,
            plan=plan,
            status="applied",
            steps=[ExecutionStepResult(kind=plan.actions[0].kind, status="applied", details={})],
        )


class FakeAuditStore:
    def __init__(self) -> None:
        self.statuses = {}
        self.records = []
        self.dry_runs = []
        self.applies = []

    def get_status(self, *, idempotency_key: str):
        return self.statuses.get(idempotency_key)

    def record_proposal(self, *, proposal, validation, status: str) -> None:
        self.records.append((proposal, validation, status))
        self.statuses[proposal.idempotency_key] = status

    def update_dry_run(self, *, idempotency_key: str, status: str, result: dict) -> None:
        self.dry_runs.append((idempotency_key, status, result))
        self.statuses[idempotency_key] = status

    def update_apply(self, *, idempotency_key: str, status: str, result: dict) -> None:
        self.applies.append((idempotency_key, status, result))
        self.statuses[idempotency_key] = status


def _event() -> WMEvent:
    return WMEvent(
        event_id=77,
        event_class="observed",
        event_type="kill",
        source="native_bridge",
        source_event_key="native_bridge:77",
        occurred_at="2026-04-10 12:00:00",
        player_guid=5406,
        subject_type="creature",
        subject_entry=6,
    )


class ControlCoordinatorTests(unittest.TestCase):
    def _coordinator(self):
        event = _event()
        registry = ControlRegistry.load("control")
        executor = FakeExecutor()
        audit = FakeAuditStore()
        coordinator = ControlCoordinator(
            registry=registry,
            event_store=FakeEventStore(event),  # type: ignore[arg-type]
            executor=executor,  # type: ignore[arg-type]
            audit_store=audit,  # type: ignore[arg-type]
        )
        proposal = build_manual_proposal(
            event=event,
            registry=registry,
            recipe_id="kill_burst_bounty",
            action_kind="quest_grant",
        )
        return coordinator, proposal, executor, audit

    def test_dry_run_uses_preview_and_audit_store(self) -> None:
        coordinator, proposal, executor, audit = self._coordinator()

        result = coordinator.execute(proposal=proposal, mode="dry-run")

        self.assertEqual(result.status, "dry-run")
        self.assertEqual(len(executor.preview_calls), 1)
        self.assertEqual(executor.apply_calls, [])
        self.assertEqual(audit.dry_runs[0][1], "dry-run")

    def test_apply_requires_confirmation(self) -> None:
        coordinator, proposal, executor, _audit = self._coordinator()

        result = coordinator.execute(proposal=proposal, mode="apply", confirm_live_apply=False)

        self.assertEqual(result.status, "rejected")
        self.assertEqual(executor.preview_calls, [])
        self.assertTrue(any(issue.path == "confirm_live_apply" for issue in (result.issues or [])))

    def test_apply_runs_preview_before_apply(self) -> None:
        coordinator, proposal, executor, audit = self._coordinator()

        result = coordinator.execute(proposal=proposal, mode="apply", confirm_live_apply=True)

        self.assertEqual(result.status, "applied")
        self.assertEqual(len(executor.preview_calls), 1)
        self.assertEqual(len(executor.apply_calls), 1)
        self.assertEqual(audit.applies[0][1], "applied")

    def test_llm_apply_requires_environment_gate(self) -> None:
        coordinator, proposal, executor, _audit = self._coordinator()
        proposal = proposal.model_copy(update={"author": proposal.author.model_copy(update={"kind": "llm"})})
        os.environ.pop("WM_LLM_DIRECT_APPLY", None)

        result = coordinator.execute(proposal=proposal, mode="apply", confirm_live_apply=True)

        self.assertEqual(result.status, "rejected")
        self.assertEqual(executor.preview_calls, [])
        self.assertTrue(any(issue.path == "WM_LLM_DIRECT_APPLY" for issue in (result.issues or [])))

    def test_duplicate_applied_idempotency_is_rejected(self) -> None:
        coordinator, proposal, executor, audit = self._coordinator()
        audit.statuses[proposal.idempotency_key] = "applied"

        result = coordinator.execute(proposal=proposal, mode="apply", confirm_live_apply=True)

        self.assertEqual(result.status, "rejected")
        self.assertEqual(executor.preview_calls, [])
        self.assertTrue(any(issue.path == "idempotency_key" for issue in (result.issues or [])))


if __name__ == "__main__":
    unittest.main()
