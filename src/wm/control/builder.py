from __future__ import annotations

import getpass
from typing import Any

from wm.control.models import ControlAction
from wm.control.models import ControlAuthor
from wm.control.models import ControlPlayer
from wm.control.models import ControlProposal
from wm.control.models import ControlRisk
from wm.control.models import ControlSourceEvent
from wm.control.registry import ControlRegistry
from wm.events.models import WMEvent


def build_manual_proposal(
    *,
    event: WMEvent | None,
    registry: ControlRegistry,
    recipe_id: str,
    action_kind: str,
    author_kind: str = "manual",
    author_name: str | None = None,
    manual_reason: str | None = None,
    payload_overrides: dict[str, Any] | None = None,
) -> ControlProposal:
    recipe = registry.recipe(recipe_id)
    if recipe is None:
        raise ValueError(f"Unknown recipe: {recipe_id}")
    action_contract = registry.action(action_kind)
    if action_contract is None:
        raise ValueError(f"Unknown action: {action_kind}")

    payload: dict[str, Any] = {}
    default_action = recipe.get("default_action")
    if isinstance(default_action, dict) and default_action.get("kind") == action_kind:
        default_payload = default_action.get("payload")
        if isinstance(default_payload, dict):
            payload.update(default_payload)
    action_default_payload = action_contract.get("default_payload")
    if isinstance(action_default_payload, dict):
        payload = {**action_default_payload, **payload}
    if event is not None and event.player_guid is not None:
        payload.setdefault("player_guid", event.player_guid)
    if event is not None and event.subject_type is not None and event.subject_entry is not None:
        payload.setdefault("subject", {"type": event.subject_type, "entry": event.subject_entry})
    if payload_overrides:
        payload.update(payload_overrides)

    player_guid = int(payload.get("player_guid") or (event.player_guid if event is not None and event.player_guid is not None else 0))
    if player_guid <= 0:
        raise ValueError("Manual proposal needs a player_guid from the event or payload.")

    source_event = None
    if event is not None:
        source_event = ControlSourceEvent(
            event_id=event.event_id,
            source=event.source,
            source_event_key=event.source_event_key,
            event_type=event.event_type,
        )

    proposal = ControlProposal(
        source_event=source_event,
        player=ControlPlayer(guid=player_guid),
        selected_recipe=recipe_id,
        action=ControlAction(kind=action_kind, payload=payload),
        rationale=f"Manual proposal for recipe {recipe_id}.",
        risk=ControlRisk(
            level=str(action_contract.get("risk", "low")),
            irreversible=False,
            notes=[str(action_contract.get("description", "Registered WM action."))],
        ),
        expected_effect=str(action_contract.get("description", "")) or None,
        author=ControlAuthor(
            kind=author_kind,  # type: ignore[arg-type]
            name=author_name or getpass.getuser(),
            manual_reason=manual_reason,
        ),
        metadata={
            "recipe_live_enabled": bool(recipe.get("live_enabled", False)),
            "registry_hash": registry.registry_hash,
        },
    )
    return proposal.model_copy(update={"idempotency_key": compute_idempotency_key(proposal)})


def compute_idempotency_key(proposal: ControlProposal) -> str:
    event_part = "admin"
    if proposal.source_event is not None:
        event_part = str(proposal.source_event.event_id or proposal.source_event.source_event_key)
    return ":".join(
        [
            "control",
            proposal.schema_version,
            proposal.author.kind,
            str(proposal.player.guid),
            event_part,
            proposal.selected_recipe,
            proposal.action.kind,
        ]
    )
