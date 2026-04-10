from __future__ import annotations

from typing import Any

from wm.control.builder import compute_idempotency_key
from wm.control.models import ControlIssue
from wm.control.models import ControlProposal
from wm.control.models import ControlValidationResult
from wm.control.models import RISK_ORDER
from wm.control.registry import ControlRegistry
from wm.events.models import WMEvent
from wm.sources.native_bridge.action_kinds import NATIVE_ACTION_KIND_BY_ID


def validate_control_proposal(
    *,
    proposal: ControlProposal,
    registry: ControlRegistry,
    source_event: WMEvent | None = None,
    require_live_recipe: bool = True,
) -> ControlValidationResult:
    issues: list[ControlIssue] = []
    registry_issues = registry.validate()
    for issue in registry_issues:
        issues.append(ControlIssue(path="registry", message=issue))

    normalized = proposal
    if not normalized.idempotency_key:
        normalized = normalized.model_copy(update={"idempotency_key": compute_idempotency_key(normalized)})

    recipe = registry.recipe(normalized.selected_recipe)
    if recipe is None:
        issues.append(ControlIssue(path="selected_recipe", message=f"Unknown recipe: {normalized.selected_recipe}"))
    elif not recipe.get("enabled", True):
        issues.append(ControlIssue(path="selected_recipe", message=f"Recipe is disabled: {normalized.selected_recipe}"))
    elif require_live_recipe and not recipe.get("live_enabled", False):
        issues.append(ControlIssue(path="selected_recipe", message=f"Recipe is not live-enabled: {normalized.selected_recipe}"))

    action = registry.action(normalized.action.kind)
    if action is None:
        issues.append(ControlIssue(path="action.kind", message=f"Unknown action: {normalized.action.kind}"))
    elif not action.get("enabled", True):
        issues.append(ControlIssue(path="action.kind", message=f"Action is disabled: {normalized.action.kind}"))

    if recipe is not None:
        allowed_actions = [str(value) for value in recipe.get("allowed_actions", [])]
        if normalized.action.kind not in allowed_actions:
            issues.append(
                ControlIssue(
                    path="action.kind",
                    message=f"Action {normalized.action.kind} is not allowed by recipe {normalized.selected_recipe}",
                )
            )
        _validate_risk(
            issues=issues,
            path="risk.level",
            actual=normalized.risk.level,
            maximum=str(recipe.get("max_risk", "low")),
            owner=f"recipe {normalized.selected_recipe}",
        )

    policy = registry.default_policy
    _validate_risk(
        issues=issues,
        path="risk.level",
        actual=normalized.risk.level,
        maximum=str(policy.get("max_live_risk", "low")),
        owner=f"policy {policy.get('id', 'direct_apply')}",
    )

    if action is not None:
        for field_name in action.get("required_payload_fields", []):
            value = normalized.action.payload.get(str(field_name))
            if value in (None, ""):
                issues.append(ControlIssue(path=f"action.payload.{field_name}", message="Required payload field is missing."))

    if normalized.author.kind == "manual_admin" and not (normalized.author.manual_reason or "").strip():
        issues.append(ControlIssue(path="author.manual_reason", message="Manual admin proposals require a reason."))

    if normalized.author.kind != "manual_admin" and normalized.source_event is None:
        issues.append(ControlIssue(path="source_event", message="Non-admin proposals require a source event."))

    if source_event is not None:
        if normalized.source_event is not None:
            if normalized.source_event.event_id is not None and source_event.event_id != normalized.source_event.event_id:
                issues.append(ControlIssue(path="source_event.event_id", message="Proposal event_id does not match loaded source event."))
            if normalized.source_event.source_event_key and source_event.source_event_key != normalized.source_event.source_event_key:
                issues.append(
                    ControlIssue(path="source_event.source_event_key", message="Proposal source_event_key does not match loaded source event.")
                )
        if source_event.player_guid is not None and source_event.player_guid != normalized.player.guid:
            issues.append(ControlIssue(path="player.guid", message="Proposal player_guid does not match source event player_guid."))
        if recipe is not None and source_event.event_type not in recipe.get("trigger_event_types", []):
            issues.append(
                ControlIssue(
                    path="selected_recipe",
                    message=f"Recipe {normalized.selected_recipe} is not eligible for event type {source_event.event_type}.",
                )
            )

    if normalized.action.kind in {"quest_publish", "item_publish", "spell_publish"} and normalized.author.kind == "llm":
        issues.append(
            ControlIssue(
                path="action.kind",
                message="LLM-authored publish actions are blocked in v1; use a manual proposal until richer review gates exist.",
            )
        )

    if normalized.action.kind == "native_bridge_action":
        native_action_kind = str(normalized.action.payload.get("native_action_kind") or "")
        if native_action_kind not in NATIVE_ACTION_KIND_BY_ID:
            issues.append(
                ControlIssue(
                    path="action.payload.native_action_kind",
                    message=f"Unknown native bridge action kind: {native_action_kind}",
                )
            )

    return ControlValidationResult.from_issues(
        issues=issues,
        normalized_proposal=normalized.model_dump(mode="json"),
        registry_hash=registry.registry_hash,
        schema_hash=registry.schema_hash,
        policy=policy,
    )


def _validate_risk(*, issues: list[ControlIssue], path: str, actual: str, maximum: str, owner: str) -> None:
    actual_rank = RISK_ORDER.get(actual, 999)
    maximum_rank = RISK_ORDER.get(maximum, -1)
    if actual_rank > maximum_rank:
        issues.append(ControlIssue(path=path, message=f"Risk {actual} exceeds maximum {maximum} for {owner}."))
