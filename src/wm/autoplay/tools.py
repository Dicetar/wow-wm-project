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
        "player_output": {
            "preferred_action": "player_chat_message",
            "styles": ["channel", "whisper", "system"],
            "default_payload": {"style": "channel", "channel_name": "WM", "sender_name": "WorldMaster"},
        },
        "native_actions": native_actions,
        "content_lanes": ["quest", "item", "spell", "ability", "scene", "action", "chat"],
        "autoplay_gates": [
            "BridgeLab doctor green",
            "active session character",
            "LM Studio model available",
            "verb enabled in operator manifest",
            "dry-run successful",
            "auto-apply pre-authorized OR operator confirmed",
        ],
    }
