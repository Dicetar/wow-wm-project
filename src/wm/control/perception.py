from __future__ import annotations

from typing import Any

from wm.control.registry import ControlRegistry
from wm.events.models import WMEvent
from wm.events.store import EventStore


def build_perception_pack(*, event: WMEvent, registry: ControlRegistry, store: EventStore | None = None) -> dict[str, Any]:
    recipes = registry.eligible_recipes_for_event_type(event.event_type)
    cooldowns: list[dict[str, Any]] = []
    if store is not None and event.player_guid is not None:
        try:
            cooldowns = [record.to_dict() for record in store.list_active_cooldowns(player_guid=event.player_guid, limit=20)]
        except Exception as exc:  # pragma: no cover - defensive for live diagnostics
            cooldowns = [{"error": str(exc)}]
    return {
        "event": event.to_dict(),
        "eligible_recipes": recipes,
        "allowed_actions": {
            recipe["id"]: [registry.actions[action_id] for action_id in recipe.get("allowed_actions", []) if action_id in registry.actions]
            for recipe in recipes
        },
        "active_cooldowns": cooldowns,
        "registry_hash": registry.registry_hash,
        "schema_hash": registry.schema_hash,
    }
