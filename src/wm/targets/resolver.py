from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any

CREATURE_TYPE_MAP: dict[int, str] = {
    0: "NOT_SPECIFIED",
    1: "BEAST",
    2: "DRAGONKIN",
    3: "DEMON",
    4: "ELEMENTAL",
    5: "GIANT",
    6: "UNDEAD",
    7: "HUMANOID",
    8: "CRITTER",
    9: "MECHANICAL",
    10: "NOT_SPECIFIED",
    11: "TOTEM",
    12: "NON_COMBAT_PET",
    13: "GAS_CLOUD",
}

CREATURE_FAMILY_MAP: dict[int, str] = {
    0: "NONE",
    1: "WOLF",
    2: "CAT",
    3: "SPIDER",
    4: "BEAR",
    5: "BOAR",
    6: "CROCOLISK",
    7: "CARRION_BIRD",
    8: "CRAB",
    9: "GORILLA",
    11: "RAPTOR",
    12: "TALLSTRIDER",
    20: "SCORPID",
    21: "TURTLE",
    24: "BAT",
    25: "HYENA",
    26: "BIRD_OF_PREY",
    27: "WIND_SERPENT",
    29: "CORE_HOUND",
    30: "SPIRIT_BEAST",
    31: "MONKEY",
    32: "DOG",
    33: "BEETLE",
    34: "SHALE_SPIDER",
    35: "ZOMBIE_CHICKEN",
    38: "FOX",
    39: "QUILEN",
    40: "CLEFTHOOF",
    41: "WASP",
    42: "BEETLE_2",
    43: "DIREHORN",
    44: "STAG",
    45: "MECHANICAL_AQUATIC",
    46: "ABERRATION",
}

CREATURE_RANK_MAP: dict[int, str] = {
    0: "NORMAL",
    1: "ELITE",
    2: "RARE_ELITE",
    3: "BOSS",
    4: "RARE",
}

UNIT_CLASS_MAP: dict[int, str] = {
    1: "WARRIOR",
    2: "PALADIN",
    4: "MAGE",
    8: "WARLOCK",
    16: "DRUID",
    32: "DEATH_KNIGHT",
}

NPC_FLAG_MAP: dict[int, str] = {
    1: "GOSSIP",
    2: "QUEST_GIVER",
    16: "TRAINER",
    32: "CLASS_TRAINER",
    64: "PROFESSION_TRAINER",
    128: "VENDOR",
    256: "VENDOR_AMMO",
    512: "VENDOR_FOOD",
    1024: "VENDOR_POISON",
    2048: "VENDOR_REAGENT",
    4096: "REPAIR",
    8192: "FLIGHTMASTER",
    16384: "SPIRIT_HEALER",
    32768: "SPIRIT_GUIDE",
    65536: "INNKEEPER",
    131072: "BANKER",
    2097152: "AUCTIONEER",
    4194304: "STABLEMASTER",
    8388608: "GUILD_BANK",
}

FACTION_LABEL_MAP: dict[int, str] = {
    11: "Stormwind",
    12: "Stormwind Civilian",
    17: "Defias Brotherhood",
    18: "Murloc",
    20: "Riverpaw Gnoll",
    21: "Scourge / Hostile Undead",
    22: "Hostile Beast",
    25: "Kobold",
    26: "Kobold / Laborer",
    32: "Neutral Beast",
    35: "Friendly / Passive / Generic",
    54: "Gnomeregan Exiles",
    68: "Undercity / Forsaken",
    76: "Orgrimmar",
    81: "Thunder Bluff",
    84: "Stormwind Guard",
    85: "Silvermoon City",
    90: "Demonic / Hostile",
    104: "Exodar",
}


@dataclass(slots=True)
class CreatureTemplateRow:
    entry: int
    name: str
    subname: str | None
    minlevel: int
    maxlevel: int
    faction: int
    npcflag: int
    type: int
    family: int
    rank: int
    unit_class: int
    gossip_menu_id: int


@dataclass(slots=True)
class TargetProfile:
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LookupStore:
    def __init__(self, creatures_by_entry: dict[int, CreatureTemplateRow]) -> None:
        self.creatures_by_entry = creatures_by_entry

    @classmethod
    def from_json(cls, path: str | Path) -> "LookupStore":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("Lookup JSON must contain a list of creature rows")

        creatures_by_entry: dict[int, CreatureTemplateRow] = {}
        for row in raw:
            creature = CreatureTemplateRow(
                entry=int(row["entry"]),
                name=str(row.get("name") or ""),
                subname=row.get("subname"),
                minlevel=int(row.get("minlevel", 0)),
                maxlevel=int(row.get("maxlevel", 0)),
                faction=int(row.get("faction", 0)),
                npcflag=int(row.get("npcflag", 0)),
                type=int(row.get("type", 0)),
                family=int(row.get("family", 0)),
                rank=int(row.get("rank", 0)),
                unit_class=int(row.get("unit_class", 0)),
                gossip_menu_id=int(row.get("gossip_menu_id", 0)),
            )
            creatures_by_entry[creature.entry] = creature
        return cls(creatures_by_entry=creatures_by_entry)

    def get_creature(self, entry: int) -> CreatureTemplateRow | None:
        return self.creatures_by_entry.get(entry)


def decode_npc_flags(npcflag: int) -> list[str]:
    roles: list[str] = []
    for flag_value, label in sorted(NPC_FLAG_MAP.items()):
        if npcflag & flag_value:
            roles.append(label)
    return roles


def decode_creature_type(type_id: int) -> str:
    return CREATURE_TYPE_MAP.get(type_id, f"UNKNOWN_{type_id}")


def decode_family(family_id: int) -> str | None:
    if family_id == 0:
        return None
    return CREATURE_FAMILY_MAP.get(family_id, f"UNKNOWN_{family_id}")


def decode_rank(rank_id: int) -> str:
    return CREATURE_RANK_MAP.get(rank_id, f"UNKNOWN_{rank_id}")


def decode_unit_class(unit_class: int) -> str:
    return UNIT_CLASS_MAP.get(unit_class, f"UNKNOWN_{unit_class}")


def decode_faction_label(faction_id: int) -> str | None:
    return FACTION_LABEL_MAP.get(faction_id)


class TargetResolver:
    def __init__(self, store: LookupStore) -> None:
        self.store = store

    def resolve_creature_entry(self, entry: int) -> TargetProfile | None:
        row = self.store.get_creature(entry)
        if row is None:
            return None

        return TargetProfile(
            entry=row.entry,
            name=row.name,
            subname=row.subname,
            level_min=row.minlevel,
            level_max=row.maxlevel,
            faction_id=row.faction,
            faction_label=decode_faction_label(row.faction),
            mechanical_type=decode_creature_type(row.type),
            family=decode_family(row.family),
            rank=decode_rank(row.rank),
            unit_class=decode_unit_class(row.unit_class),
            service_roles=decode_npc_flags(row.npcflag),
            has_gossip_menu=row.gossip_menu_id > 0,
        )
