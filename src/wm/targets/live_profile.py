from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from wm.targets.resolver import (
    decode_creature_type,
    decode_family,
    decode_faction_label,
    decode_npc_flags,
    decode_rank,
    decode_unit_class,
)


@dataclass(slots=True)
class SpawnContext:
    map_id: int
    zone_id: int
    count: int


@dataclass(slots=True)
class LiveTargetProfile:
    entry: int
    name: str
    subname: str | None
    level_min: int
    level_max: int
    faction_id: int
    faction_label: str | None
    mechanical_type: str
    family: str | None
    rank: str
    unit_class: str
    service_roles: list[str] = field(default_factory=list)
    has_gossip_menu: bool = False
    gossip_option_count: int = 0
    quest_starter_ids: list[int] = field(default_factory=list)
    quest_ender_ids: list[int] = field(default_factory=list)
    vendor_item_count: int = 0
    trainer_spell_count: int = 0
    spawn_count: int = 0
    spawn_contexts: list[SpawnContext] = field(default_factory=list)
    derived_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["spawn_contexts"] = [asdict(x) for x in self.spawn_contexts]
        return payload


def build_live_target_profile(raw: dict[str, Any]) -> LiveTargetProfile:
    entry = int(raw["entry"])
    faction_id = int(raw.get("faction", 0))
    npcflag = int(raw.get("npcflag", 0))
    gossip_menu_id = int(raw.get("gossip_menu_id", 0))
    gossip_option_count = int(raw.get("gossip_option_count", 0))
    quest_starter_ids = _parse_csv_ints(raw.get("quest_starter_ids"))
    quest_ender_ids = _parse_csv_ints(raw.get("quest_ender_ids"))
    vendor_item_count = int(raw.get("vendor_item_count", 0))
    trainer_spell_count = int(raw.get("trainer_spell_count", 0))
    spawn_count = int(raw.get("spawn_count", 0))
    spawn_contexts = _parse_spawn_contexts(raw.get("spawn_contexts"))
    roles = decode_npc_flags(npcflag)

    profile = LiveTargetProfile(
        entry=entry,
        name=str(raw.get("name") or ""),
        subname=_normalize_text_or_none(raw.get("subname")),
        level_min=int(raw.get("minlevel", 0)),
        level_max=int(raw.get("maxlevel", 0)),
        faction_id=faction_id,
        faction_label=_normalize_text_or_none(raw.get("faction_name")) or decode_faction_label(faction_id),
        mechanical_type=decode_creature_type(int(raw.get("type", 0))),
        family=decode_family(int(raw.get("family", 0))),
        rank=decode_rank(int(raw.get("rank", 0))),
        unit_class=decode_unit_class(int(raw.get("unit_class", 0))),
        service_roles=roles,
        has_gossip_menu=gossip_menu_id > 0,
        gossip_option_count=gossip_option_count,
        quest_starter_ids=quest_starter_ids,
        quest_ender_ids=quest_ender_ids,
        vendor_item_count=vendor_item_count,
        trainer_spell_count=trainer_spell_count,
        spawn_count=spawn_count,
        spawn_contexts=spawn_contexts,
        derived_tags=derive_tags(
            name=str(raw.get("name") or ""),
            subname=_normalize_text_or_none(raw.get("subname")),
            mechanical_type=decode_creature_type(int(raw.get("type", 0))),
            service_roles=roles,
            quest_starter_ids=quest_starter_ids,
            quest_ender_ids=quest_ender_ids,
            vendor_item_count=vendor_item_count,
            trainer_spell_count=trainer_spell_count,
            spawn_contexts=spawn_contexts,
        ),
    )
    return profile


def derive_tags(
    *,
    name: str,
    subname: str | None,
    mechanical_type: str,
    service_roles: list[str],
    quest_starter_ids: list[int],
    quest_ender_ids: list[int],
    vendor_item_count: int,
    trainer_spell_count: int,
    spawn_contexts: list[SpawnContext],
) -> list[str]:
    tags: list[str] = []

    normalized_name = name.lower()
    if "murloc" in normalized_name:
        tags.append("murloc")
    if subname:
        tags.append("named_service_npc")
    if mechanical_type == "BEAST":
        tags.append("wild_beast")
    elif mechanical_type == "HUMANOID":
        tags.append("humanoid")
    elif mechanical_type == "UNDEAD":
        tags.append("undead")

    if quest_starter_ids or quest_ender_ids:
        tags.append("quest_actor")
    if vendor_item_count > 0 or "VENDOR" in service_roles:
        tags.append("merchant")
    if trainer_spell_count > 0 or "TRAINER" in service_roles or "CLASS_TRAINER" in service_roles or "PROFESSION_TRAINER" in service_roles:
        tags.append("trainer")
    if "GOSSIP" in service_roles:
        tags.append("interactive")
    if not service_roles and not quest_starter_ids and not quest_ender_ids:
        tags.append("wild_encounter")

    if any(context.zone_id == 40 for context in spawn_contexts):
        tags.append("westfall")
    if any(context.zone_id == 12 for context in spawn_contexts):
        tags.append("elwynn")

    return _dedupe_preserve_order(tags)


def _parse_csv_ints(value: Any) -> list[int]:
    if value in (None, ""):
        return []
    parsed: list[int] = []
    for part in str(value).split(","):
        text = part.strip()
        if not text:
            continue
        try:
            parsed.append(int(text))
        except ValueError:
            continue
    return parsed


def _parse_spawn_contexts(value: Any) -> list[SpawnContext]:
    contexts: list[SpawnContext] = []
    if value in (None, ""):
        return contexts
    for blob in str(value).split(";"):
        text = blob.strip()
        if not text:
            continue
        try:
            map_text, zone_text, count_text = text.split(":", 2)
            contexts.append(SpawnContext(map_id=int(map_text), zone_id=int(zone_text), count=int(count_text)))
        except ValueError:
            continue
    return contexts


def _normalize_text_or_none(value: Any) -> str | None:
    if value in (None, "", "NULL"):
        return None
    return str(value)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered
