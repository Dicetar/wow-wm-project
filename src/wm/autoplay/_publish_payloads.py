from __future__ import annotations

from typing import Any

from wm.autoplay._compact import _int_or_none


def _quest_publish_payload_from_release(payload: dict[str, Any], *, record: dict[str, Any], allocator: Any) -> dict[str, Any]:
    quest = payload.get("quest") if isinstance(payload.get("quest"), dict) else {}
    objective = payload.get("objective") if isinstance(payload.get("objective"), dict) else {}
    reward = payload.get("reward") if isinstance(payload.get("reward"), dict) else {}
    player_guid = int(payload.get("player_guid") or record.get("player_guid") or 0)
    quest_id = _int_or_none(quest.get("quest_id"))
    if quest_id is None:
        slot = allocator.peek_next_free_slot(entity_type="quest")
        if slot is None:
            raise ValueError("No free managed quest slot is available.")
        quest_id = int(slot.reserved_id)
    questgiver_entry = int(quest.get("questgiver_entry") or quest.get("start_npc_entry") or quest.get("end_npc_entry") or 240)
    questgiver_name = str(quest.get("questgiver_name") or "World Master")
    target_entry = int(objective.get("target_entry") or 1)
    target_name = str(objective.get("target_name") or f"Target {target_entry}")
    title = str(quest.get("title") or f"WM Bounty: {target_name}")[:80]
    return {
        "quest_id": quest_id,
        "quest_level": int(quest.get("quest_level") or 70),
        "min_level": min(int(quest.get("min_level") or 1), int(quest.get("quest_level") or 70)),
        "questgiver_entry": questgiver_entry,
        "questgiver_name": questgiver_name,
        "start_npc_entry": _int_or_none(quest.get("start_npc_entry")) or questgiver_entry,
        "end_npc_entry": _int_or_none(quest.get("end_npc_entry")) or questgiver_entry,
        "grant_mode": str(quest.get("grant_mode") or "direct_grant"),
        "title": title,
        "quest_description": str(quest.get("quest_description") or f"The world has marked {target_name}. Cull them."),
        "objective_text": str(quest.get("objective_text") or f"Slay {int(objective.get('kill_count') or 3)} {target_name}."),
        "offer_reward_text": str(quest.get("offer_reward_text") or "The world acknowledges your answer."),
        "request_items_text": str(quest.get("request_items_text") or "Return when the work is done."),
        "objective": {
            "target_entry": target_entry,
            "target_name": target_name,
            "kill_count": int(objective.get("kill_count") or 3),
        },
        "reward": _quest_reward_payload(reward),
        "tags": ["wm_autoplay", "llm_draft"],
        "template_defaults": dict(quest.get("template_defaults") or {"SpecialFlags": 1}),
        "_wm_reserved_slot": {
            "entity_type": "quest",
            "reserved_id": quest_id,
            "arc_key": "wm_autoplay",
            "character_guid": player_guid,
            "notes": [f"draft:{record.get('draft_id')}"],
        },
    }


def _quest_reward_payload(reward: dict[str, Any]) -> dict[str, Any]:
    kind = str(reward.get("kind") or "none")
    result = {"money_copper": 0, "reward_item_count": int(reward.get("item_count") or 1)}
    if kind == "money":
        result["money_copper"] = int(reward.get("money_copper") or 0)
    elif kind == "item" and reward.get("item_entry") not in (None, ""):
        result["reward_item_entry"] = int(reward["item_entry"])
        result["reward_item_name"] = str(reward.get("item_name") or f"Item {reward['item_entry']}")
    elif kind == "spell" and reward.get("spell_id") not in (None, ""):
        result["reward_spell_id"] = int(reward["spell_id"])
        if reward.get("spell_display_id") not in (None, ""):
            result["reward_spell_display_id"] = int(reward["spell_display_id"])
    return result


def _item_publish_payload_from_release(payload: dict[str, Any], *, record: dict[str, Any], allocator: Any) -> dict[str, Any]:
    item_entry = _int_or_none(payload.get("item_entry"))
    if item_entry is None:
        slot = allocator.peek_next_free_slot(entity_type="item")
        if slot is None:
            raise ValueError("No free managed item slot is available.")
        item_entry = int(slot.reserved_id)
    shape = payload.get("item_shape") if isinstance(payload.get("item_shape"), dict) else {}
    effects = payload.get("effects") if isinstance(payload.get("effects"), list) else []
    spells = [
        {"spell_id": int(effect["spell_id"]), "trigger": 1}
        for effect in effects
        if isinstance(effect, dict) and effect.get("spell_id") not in (None, "")
    ]
    return {
        "item_entry": item_entry,
        "base_item_entry": int(payload.get("base_item_entry") or 6948),
        "name": str(payload.get("item_key") or f"WM Autoplay Item {item_entry}")[:120],
        "description": "; ".join(str(note) for note in payload.get("notes", [])[:2]) if isinstance(payload.get("notes"), list) else None,
        "quality": _int_or_none(shape.get("quality")) or 2,
        "required_level": _int_or_none(shape.get("required_level")),
        "clear_stats": True,
        "clear_spells": bool(spells),
        "spells": spells,
        "tags": ["wm_autoplay", "llm_draft"],
        "_wm_reserved_slot": {
            "entity_type": "item",
            "reserved_id": item_entry,
            "arc_key": "wm_autoplay",
            "character_guid": int(payload.get("player_guid") or record.get("player_guid") or 0),
            "notes": [f"draft:{record.get('draft_id')}"],
        },
    }


def _spell_publish_payload_from_release(payload: dict[str, Any], *, record: dict[str, Any], allocator: Any) -> dict[str, Any]:
    spell_entry = _int_or_none(payload.get("spell_entry"))
    if spell_entry is None:
        slot = allocator.peek_next_free_slot(entity_type="spell")
        if slot is None:
            raise ValueError("No free managed spell slot is available.")
        spell_entry = int(slot.reserved_id)
    return {
        "spell_entry": spell_entry,
        "slot_kind": str(payload.get("slot_kind") or "visible_spell_slot"),
        "name": str(payload.get("name") or payload.get("spell_key") or f"WM Autoplay Spell {spell_entry}")[:120],
        "base_visible_spell_id": _int_or_none(payload.get("base_visible_spell_id")) or 133,
        "aura_description": str(payload.get("aura_description") or ""),
        "proc_rules": list(payload.get("proc_rules") or []),
        "linked_spells": list(payload.get("linked_spells") or []),
        "tags": ["wm_autoplay", "llm_draft"],
        "_wm_reserved_slot": {
            "entity_type": "spell",
            "reserved_id": spell_entry,
            "arc_key": "wm_autoplay",
            "character_guid": int(payload.get("player_guid") or record.get("player_guid") or 0),
            "notes": [f"draft:{record.get('draft_id')}"],
        },
    }


def _entry_from_payload(payload: dict[str, Any], lane: str) -> int | None:
    if lane == "quest":
        objective = payload.get("objective") if isinstance(payload.get("objective"), dict) else {}
        return _int_or_none(objective.get("target_entry"))
    if lane == "item":
        return _int_or_none(payload.get("item_entry"))
    if lane == "spell":
        return _int_or_none(payload.get("spell_entry"))
    return None
