from __future__ import annotations

from typing import Any, Protocol

from wm.refs import CreatureRef
from wm.subjects.models import SubjectCard


class CreatureProfileResolver(Protocol):
    def resolve_creature_entry(self, entry: int) -> Any | None:
        ...


class SubjectResolver:
    def __init__(self, target_resolver: CreatureProfileResolver) -> None:
        self.target_resolver = target_resolver

    def resolve_creature_entry(self, entry: int) -> SubjectCard | None:
        profile = self.target_resolver.resolve_creature_entry(int(entry))
        if profile is None:
            return None
        return build_subject_card_from_profile(profile)


def build_subject_card_from_profile(profile: Any) -> SubjectCard:
    entry = int(profile.entry)
    display_name = str(profile.name or f"Creature {entry}")
    derived_tags = [str(tag) for tag in getattr(profile, "derived_tags", [])]
    service_roles = [str(role) for role in getattr(profile, "service_roles", [])]
    creature_type = _str_or_none(getattr(profile, "mechanical_type", None))
    family = _str_or_none(getattr(profile, "family", None))
    faction_label = _str_or_none(getattr(profile, "faction_label", None))
    area_tags = [tag for tag in derived_tags if tag in {"elwynn", "westfall"}]
    role_tags = _dedupe([*_role_tags_from_profile(profile), *service_roles, *derived_tags])
    group_keys = _dedupe(_group_keys_from_profile(profile, display_name=display_name))
    archetype = _first_non_empty(
        _humanized(family),
        _humanized(faction_label),
        _humanized(creature_type),
    )

    return SubjectCard(
        canonical_id=f"creature:{entry}",
        kind="creature",
        entry=entry,
        display_name=display_name,
        title=_str_or_none(getattr(profile, "subname", None)),
        archetype=archetype,
        faction_id=int(getattr(profile, "faction_id", 0) or 0),
        faction_label=faction_label,
        creature_type=creature_type,
        family=family,
        rank=_str_or_none(getattr(profile, "rank", None)),
        unit_class=_str_or_none(getattr(profile, "unit_class", None)),
        role_tags=role_tags,
        group_keys=group_keys,
        area_tags=area_tags,
        source_ref=CreatureRef(entry=entry, name=display_name),
        source=type(profile).__name__,
        evidence={
            "level_min": int(getattr(profile, "level_min", 0) or 0),
            "level_max": int(getattr(profile, "level_max", 0) or 0),
            "service_roles": service_roles,
            "derived_tags": derived_tags,
            "has_gossip_menu": bool(getattr(profile, "has_gossip_menu", False)),
            "spawn_count": int(getattr(profile, "spawn_count", 0) or 0),
        },
    )


def _role_tags_from_profile(profile: Any) -> list[str]:
    tags: list[str] = []
    service_roles = set(str(role) for role in getattr(profile, "service_roles", []))
    if "QUEST_GIVER" in service_roles or getattr(profile, "quest_starter_ids", []):
        tags.append("quest_actor")
    if "TRAINER" in service_roles or "CLASS_TRAINER" in service_roles or "PROFESSION_TRAINER" in service_roles:
        tags.append("trainer")
    if "VENDOR" in service_roles or int(getattr(profile, "vendor_item_count", 0) or 0) > 0:
        tags.append("merchant")
    if bool(getattr(profile, "has_gossip_menu", False)) or "GOSSIP" in service_roles:
        tags.append("interactive")
    if not tags:
        tags.append("world_subject")
    return tags


def _group_keys_from_profile(profile: Any, *, display_name: str) -> list[str]:
    keys = [f"creature:{int(profile.entry)}"]
    family = _str_or_none(getattr(profile, "family", None))
    if family is not None:
        keys.append(f"family:{family.lower()}")
    creature_type = _str_or_none(getattr(profile, "mechanical_type", None))
    if creature_type is not None:
        keys.append(f"type:{creature_type.lower()}")
    faction_label = _str_or_none(getattr(profile, "faction_label", None))
    if faction_label is not None:
        keys.append(f"faction:{_slug(faction_label)}")
    name = display_name.strip().lower()
    if name:
        keys.append(f"name:{_slug(name)}")
    return keys


def _str_or_none(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _first_non_empty(*values: str | None) -> str | None:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _humanized(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    return str(value).replace("_", " ").title()


def _slug(value: str) -> str:
    return "_".join(part for part in value.lower().replace("/", " ").replace("-", " ").split() if part)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
