from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from typing import Any

from wm.control.builder import compute_idempotency_key
from wm.control.models import ControlIssue
from wm.control.models import ControlProposal
from wm.control.models import ControlValidationResult
from wm.control.registry import ControlRegistry
from wm.control.store import ControlAuditStore
from wm.control.validator import validate_control_proposal
from wm.events.executor import ReactionExecutor
from wm.events.models import ExecutionResult
from wm.events.models import PlannedAction
from wm.events.models import ReactionPlan
from wm.events.models import SubjectRef
from wm.events.models import WMEvent
from wm.events.store import EventStore


@dataclass(slots=True)
class ControlExecutionResult:
    status: str
    proposal: ControlProposal
    validation: ControlValidationResult
    dry_run: ExecutionResult | None = None
    applied: ExecutionResult | None = None
    issues: list[ControlIssue] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "proposal": self.proposal.model_dump(mode="json"),
            "validation": self.validation.model_dump(mode="json"),
            "dry_run": self.dry_run.to_dict() if self.dry_run is not None else None,
            "applied": self.applied.to_dict() if self.applied is not None else None,
            "issues": [issue.model_dump(mode="json") for issue in (self.issues or [])],
        }


class ControlCoordinator:
    def __init__(
        self,
        *,
        registry: ControlRegistry,
        event_store: EventStore,
        executor: ReactionExecutor,
        audit_store: ControlAuditStore | None = None,
        now: datetime | None = None,
    ) -> None:
        self.registry = registry
        self.event_store = event_store
        self.executor = executor
        self.audit_store = audit_store
        self.now = now

    def validate(self, proposal: ControlProposal) -> ControlValidationResult:
        proposal = _ensure_idempotency(proposal)
        source_event = self._resolve_source_event(proposal)
        result = validate_control_proposal(proposal=proposal, registry=self.registry, source_event=source_event, now=self.now)
        if source_event is None and proposal.author.kind != "manual_admin":
            result.issues.append(ControlIssue(path="source_event", message="Source event does not exist."))
            result.ok = False
        return result

    def execute(self, *, proposal: ControlProposal, mode: str, confirm_live_apply: bool = False) -> ControlExecutionResult:
        if mode not in {"dry-run", "apply"}:
            raise ValueError(f"Unsupported control mode: {mode}")
        proposal = _ensure_idempotency(proposal)
        validation = self.validate(proposal)
        duplicate_status = self.audit_store.get_status(idempotency_key=proposal.idempotency_key or "") if self.audit_store else None
        if mode == "apply" and duplicate_status == "applied":
            issue = ControlIssue(path="idempotency_key", message="Proposal was already applied.")
            validation.issues.append(issue)
            validation.ok = False
            return ControlExecutionResult(status="rejected", proposal=proposal, validation=validation, issues=[issue])
        if self.audit_store is not None:
            self.audit_store.record_proposal(
                proposal=proposal,
                validation=validation,
                status="validated" if validation.ok else "rejected",
            )
        if not validation.ok:
            return ControlExecutionResult(status="rejected", proposal=proposal, validation=validation, issues=validation.issues)

        if mode == "apply":
            gate_issue = self._apply_gate_issue(proposal=proposal, confirm_live_apply=confirm_live_apply)
            if gate_issue is not None:
                validation.issues.append(gate_issue)
                validation.ok = False
                if self.audit_store is not None:
                    self.audit_store.record_proposal(proposal=proposal, validation=validation, status="rejected")
                return ControlExecutionResult(status="rejected", proposal=proposal, validation=validation, issues=[gate_issue])

        source_event = self._resolve_source_event(proposal)
        plan = self._proposal_to_plan(proposal=proposal, source_event=source_event)
        dry_run = self.executor.preview(plan=plan)
        dry_run_status = "dry-run" if dry_run.status in {"preview", "dry-run"} and not _execution_failed(dry_run) else "failed"
        if self.audit_store is not None:
            self.audit_store.update_dry_run(
                idempotency_key=proposal.idempotency_key or "",
                status=dry_run_status,
                result=dry_run.to_dict(),
            )
        if dry_run_status == "failed" or mode == "dry-run":
            return ControlExecutionResult(status=dry_run_status, proposal=proposal, validation=validation, dry_run=dry_run)

        applied = self.executor.execute(plan=plan, mode="apply")
        apply_status = "applied" if applied.status == "applied" and not _execution_failed(applied) else "failed"
        if self.audit_store is not None:
            self.audit_store.update_apply(
                idempotency_key=proposal.idempotency_key or "",
                status=apply_status,
                result=applied.to_dict(),
            )
        return ControlExecutionResult(status=apply_status, proposal=proposal, validation=validation, dry_run=dry_run, applied=applied)

    def _apply_gate_issue(self, *, proposal: ControlProposal, confirm_live_apply: bool) -> ControlIssue | None:
        if not confirm_live_apply:
            return ControlIssue(path="confirm_live_apply", message="Apply mode requires --confirm-live-apply.")
        if proposal.author.kind == "llm":
            env_name = str(self.registry.default_policy.get("llm_requires_env", "WM_LLM_DIRECT_APPLY"))
            if os.getenv(env_name, "").strip().lower() not in {"1", "true", "yes", "on"}:
                return ControlIssue(path=env_name, message=f"LLM apply requires {env_name}=1.")
        return None

    def _resolve_source_event(self, proposal: ControlProposal) -> WMEvent | None:
        if proposal.source_event is None:
            return None
        if proposal.source_event.event_id is not None:
            return self.event_store.get_event(event_id=proposal.source_event.event_id)
        if proposal.source_event.source and proposal.source_event.source_event_key:
            return self.event_store.get_event_by_source_key(
                source=proposal.source_event.source,
                source_event_key=proposal.source_event.source_event_key,
            )
        return None

    def _proposal_to_plan(self, *, proposal: ControlProposal, source_event: WMEvent | None) -> ReactionPlan:
        subject_type = source_event.subject_type if source_event is not None else None
        subject_entry = source_event.subject_entry if source_event is not None else None
        payload_subject = proposal.action.payload.get("subject")
        if isinstance(payload_subject, dict):
            subject_type = subject_type or str(payload_subject.get("type") or "control")
            if subject_entry is None and payload_subject.get("entry") not in (None, ""):
                subject_entry = int(payload_subject["entry"])
        subject = SubjectRef(subject_type=subject_type or "control", subject_entry=int(subject_entry or 0))
        return ReactionPlan(
            plan_key=proposal.idempotency_key or compute_idempotency_key(proposal),
            opportunity_type=f"control:{proposal.selected_recipe}",
            rule_type=proposal.selected_recipe,
            player_guid=proposal.player.guid,
            subject=subject,
            actions=[
                PlannedAction(
                    kind=proposal.action.kind,
                    payload=proposal.action.payload,
                    description=f"Control proposal action for {proposal.selected_recipe}.",
                )
            ],
            metadata={
                "control_proposal": proposal.model_dump(mode="json"),
                "source_event": source_event.to_dict() if source_event is not None else None,
            },
        )


def _ensure_idempotency(proposal: ControlProposal) -> ControlProposal:
    if proposal.idempotency_key:
        return proposal
    return proposal.model_copy(update={"idempotency_key": compute_idempotency_key(proposal)})


def _execution_failed(result: ExecutionResult) -> bool:
    return any(step.status == "failed" for step in result.steps)
