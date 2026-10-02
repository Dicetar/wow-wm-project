from __future__ import annotations

from typing import Any

from wm.autoplay.intent import resolve_verb_modes
from wm.sources.native_bridge.action_kinds import NATIVE_ACTION_KINDS
from wm.sources.native_bridge.payload_contract import load_payload_contracts


def autoplay_tool_manifest(*, modes: dict[str, str] | None = None) -> dict[str, Any]:
    resolved = resolve_verb_modes(modes)
    try:
        contracts = load_payload_contracts()
    except Exception:
        contracts = {}
    native_actions = []
    for item in NATIVE_ACTION_KINDS:
        if not (item.implemented and resolved.get(item.kind, "off") != "off"):
            continue
        entry = {
            "kind": item.kind,
            "category": item.category,
            "risk": item.default_risk,
            "mode": resolved[item.kind],
            "description": item.description,
            "proof_status": item.proof_status,
            "verification_strategy": item.verification_strategy,
            "auto_apply_allowed": item.auto_apply_allowed,
            "client_visible": item.client_visible,
            "cleanup_required": item.cleanup_required,
        }
        contract = contracts.get(item.kind) or {}
        for field in ("required", "required_any", "optional", "notes"):
            value = contract.get(field)
            if value:
                entry[field] = value
        native_actions.append(entry)
    return {
        "schema_version": "wm.autoplay.tools.v2",
        "model_contract": (
            "Reply in plain words. You MAY include one `intent` choosing exactly one verb from "
            "native_actions with its args; WM validates, dry-runs, and applies it. Never write SQL, "
            "GM commands, shell commands, config edits, or raw mutations."
        ),
        "player_input": {
            "preferred": "custom chat channel named WM",
            "also_supported": ["chat prefix: towm <message>", "addon mirror events"],
        },
        "author_notes": {
            "status": "PARTIAL",
            "input": ["towm /note <direction>", "towm /note! <firm constraint>", "towm /notes <page>",
                      "towm /note edit <id> <direction>", "towm /note remove <id>"],
            "panel_api": "/api/wm/author-notes",
            "scope": "In-game commands affect the speaking character; the panel also supports World notes.",
            "authority": "Explicit user input only, not an LLM-write tool or live-mutation authorization.",
        },
        "player_output": {
            "preferred_action": "player_chat_message",
            "styles": ["channel", "whisper", "system"],
            "default_payload": {"style": "channel", "channel_name": "WM", "sender_name": "WorldMaster"},
        },
        "native_actions": native_actions,
        "content_lanes": ["quest", "item", "spell", "ability", "scene", "action", "chat"],
        "director_read_tools": [
            {"capability": "world_scout", "outcome": "inspect_world", "arguments": ["radius", "limit", "search"],
             "effect": "Read nearby ingredients around fresh selected-character position."},
            {"capability": "world_lookup", "outcome": "inspect_world", "arguments": ["kind", "entry", "search", "limit"],
             "effect": "Inspect/search existing creature, gameobject, item, quest or shell identities."},
            {"capability": "loot_sources", "outcome": "inspect_world", "arguments": ["entry", "search", "map_id", "limit"],
             "effect": "Trace item sources; ambiguous names require clarification, never a guessed ID."},
        ],
        "operator_authoring_tools": [
            {"command_id": "world.ingredients.scout", "effect": "Read nearby NPC roles, enemy populations and material sources using fresh native position."},
            {"command_id": "world.templates.search", "effect": "Search existing creature/object/item/quest/shell identities by literal name."},
            {"command_id": "world.templates.inspect", "effect": "Inspect an existing template, regional spawn population and quest relations."},
            {"command_id": "world.loot.sources", "effect": "Trace an item through direct/reference loot to persistent source regions; no mutation."},
            {"command_id": "quests.draft_delivery", "effect": "Draft a material-delivery quest using existing item/NPC identities; does not publish or grant."},
            {"command_id": "world.spawns.inspect", "effect": "Inspect persistent spawn IDs, coordinates, phase and respawn delay."},
            {"command_id": "world.spawn.execute", "effect": "Place/move/edit/remove world spawns using a typed action JSON."},
            {"command_id": "world.event.run", "effect": "Publish and trigger an ordered content/native event bundle."},
            {"command_id": "workbench.publish_quest", "effect": "Publish a managed kill or material-delivery quest draft."},
            {"command_id": "workbench.publish_item", "effect": "Publish a managed item draft."},
            {"command_id": "workbench.publish_spell", "effect": "Publish a managed spell or passive draft."},
            {"command_id": "workbench.publish_shell", "effect": "Publish shell/native behavior metadata; client patch remains separate."},
        ],
        "autoplay_gates": [
            "BridgeLab doctor green",
            "active session character",
            "LM Studio model available",
            "verb enabled in operator manifest",
            "dry-run successful",
            "auto-apply pre-authorized OR operator confirmed",
        ],
    }
