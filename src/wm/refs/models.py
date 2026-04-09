from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class PlayerRef:
    guid: int
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"guid": int(self.guid), "name": self.name}


@dataclass(slots=True)
class CreatureRef:
    entry: int
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"entry": int(self.entry), "name": self.name}


@dataclass(slots=True)
class NpcRef:
    entry: int
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"entry": int(self.entry), "name": self.name}


@dataclass(slots=True)
class QuestRef:
    id: int
    title: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"id": int(self.id), "title": self.title}


@dataclass(slots=True)
class ItemRef:
    entry: int
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"entry": int(self.entry), "name": self.name}


@dataclass(slots=True)
class SpellRef:
    id: int
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"id": int(self.id), "name": self.name}


def player_ref_from_value(value: object) -> PlayerRef | None:
    if isinstance(value, PlayerRef):
        return value
    if not isinstance(value, dict):
        return None
    guid = value.get("guid")
    if guid in (None, ""):
        return None
    return PlayerRef(guid=int(guid), name=_str_or_none(value.get("name")))


def creature_ref_from_value(value: object) -> CreatureRef | None:
    if isinstance(value, CreatureRef):
        return value
    if not isinstance(value, dict):
        return None
    entry = value.get("entry")
    if entry in (None, ""):
        return None
    return CreatureRef(entry=int(entry), name=_str_or_none(value.get("name")))


def npc_ref_from_value(value: object) -> NpcRef | None:
    if isinstance(value, NpcRef):
        return value
    if not isinstance(value, dict):
        return None
    entry = value.get("entry")
    if entry in (None, ""):
        return None
    return NpcRef(entry=int(entry), name=_str_or_none(value.get("name")))


def quest_ref_from_value(value: object) -> QuestRef | None:
    if isinstance(value, QuestRef):
        return value
    if not isinstance(value, dict):
        return None
    quest_id = value.get("id")
    if quest_id in (None, ""):
        return None
    return QuestRef(id=int(quest_id), title=_str_or_none(value.get("title")))


def item_ref_from_value(value: object) -> ItemRef | None:
    if isinstance(value, ItemRef):
        return value
    if not isinstance(value, dict):
        return None
    entry = value.get("entry")
    if entry in (None, ""):
        return None
    return ItemRef(entry=int(entry), name=_str_or_none(value.get("name")))


def spell_ref_from_value(value: object) -> SpellRef | None:
    if isinstance(value, SpellRef):
        return value
    if not isinstance(value, dict):
        return None
    spell_id = value.get("id")
    if spell_id in (None, ""):
        return None
    return SpellRef(id=int(spell_id), name=_str_or_none(value.get("name")))


def _str_or_none(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
