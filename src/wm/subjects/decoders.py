"""Decode AzerothCore integer codes into human-readable labels."""
from __future__ import annotations

CREATURE_TYPE: dict[int, str] = {
    0: "None", 1: "Beast", 2: "Dragonkin", 3: "Demon",
    4: "Elemental", 5: "Giant", 6: "Undead", 7: "Humanoid",
    8: "Critter", 9: "Mechanical", 10: "Not_specified",
    11: "Totem", 12: "Non-combat_pet", 13: "Gas_cloud",
}

NPC_FLAGS: dict[int, str] = {
    0x1: "gossip", 0x2: "questgiver", 0x10: "trainer",
    0x20: "trainer_class", 0x40: "trainer_profession",
    0x80: "vendor", 0x100: "vendor_ammo", 0x200: "vendor_food",
    0x400: "vendor_poison", 0x800: "vendor_reagent",
    0x1000: "repair", 0x4000: "flightmaster", 0x8000: "spiritguide",
    0x10000: "innkeeper", 0x20000: "banker", 0x40000: "petitioner",
    0x80000: "tabarddesigner", 0x100000: "battlemaster",
    0x200000: "auctioneer", 0x400000: "stablemaster",
    0x1000000: "guard",
}

RANK: dict[int, str] = {
    0: "normal", 1: "elite", 2: "rareelite", 3: "worldboss", 4: "rare",
}

CREATURE_FAMILY: dict[int, str] = {
    1: "Wolf", 2: "Cat", 3: "Spider", 4: "Bear", 5: "Boar",
    6: "Crocolisk", 7: "Carrion Bird", 8: "Crab", 9: "Gorilla",
    11: "Raptor", 12: "Tallstrider", 20: "Scorpid", 21: "Turtle",
    24: "Bat", 25: "Hyena", 26: "Bird_of_Prey", 27: "Wind_Serpent",
    30: "Dragonhawk", 31: "Ravager", 32: "Warp_Stalker",
    33: "Sporebat", 34: "Nether_Ray", 35: "Serpent",
    37: "Moth", 38: "Chimaera", 39: "Devilsaur", 41: "Silithid",
    42: "Worm", 43: "Rhino", 44: "Wasp", 45: "Core_Hound",
    46: "Spirit_Beast",
}

# Broad faction alignment by faction template ID (AzerothCore 3.3.5a).
# Conservative — only well-known IDs mapped precisely.
FACTION_ALIGNMENT: dict[int, str] = {
    1: "alliance_friendly",   # Stormwind
    2: "alliance_friendly",   # Player — Alliance
    3: "horde_friendly",      # Orgrimmar
    4: "horde_friendly",      # Player — Horde
    35: "neutral",            # Friendly to all
    14: "hostile_all",        # Monster
    16: "hostile_all",        # Creature — aggressive
}


def decode_creature_type(type_id: int) -> str:
    return CREATURE_TYPE.get(type_id, f"Unknown({type_id})")


def decode_npc_flags(flags: int) -> list[str]:
    return [label for bit, label in NPC_FLAGS.items() if flags & bit]


def decode_rank(rank_id: int) -> str:
    return RANK.get(rank_id, f"unknown({rank_id})")


def decode_creature_family(family_id: int) -> str | None:
    return CREATURE_FAMILY.get(family_id)


def decode_faction_alignment(faction_id: int) -> str:
    return FACTION_ALIGNMENT.get(faction_id, "unknown")
