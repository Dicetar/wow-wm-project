from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient

_CLASS_MASK_BY_CLASS_ID = {
    1: 1,      # Warrior
    2: 2,      # Paladin
    3: 4,      # Hunter
    4: 8,      # Rogue
    5: 16,     # Priest
    6: 32,     # Death Knight
    7: 64,     # Shaman
    8: 128,    # Mage
    9: 256,    # Warlock
    11: 1024,  # Druid
}

_ARMOR_SKILL_TO_SUBCLASS = {
    414: 2,  # Leather
    413: 3,  # Mail
    293: 4,  # Plate
    433: 6,  # Shield
}

_EQUIPMENT_INVENTORY_TYPES = (1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 14, 16, 20)
_NAME_EXCLUSION_SQL = (
    "name NOT LIKE 'Test %'",
    "name NOT LIKE 'Deprecated%'",
    "name NOT LIKE 'OLD%'",
    "name NOT LIKE 'Monster - %'",
    "name NOT LIKE '%Placeholder%'",
)


@dataclass(frozen=True, slots=True)
class BountyRewardSelection:
    item_entry: int
    item_name: str
    player_level: int
    required_level_min: int
    required_level_max: int
    candidate_count: int
    policy_key: str = "random_suitable_equipment_v1"

    def to_dict(self) -> dict[str, object]:
        return {
            "item_entry": int(self.item_entry),
            "item_name": self.item_name,
            "player_level": int(self.player_level),
            "required_level_min": int(self.required_level_min),
            "required_level_max": int(self.required_level_max),
            "candidate_count": int(self.candidate_count),
            "policy_key": self.policy_key,
        }


@dataclass(frozen=True, slots=True)
class PlayerRewardProfile:
    player_guid: int
    class_id: int
    level: int
    class_mask: int
    armor_subclasses: tuple[int, ...]


class BountyEquipmentRewardPicker:
    def __init__(
        self,
        *,
        client: MysqlCliClient,
        settings: Settings,
        chooser: Callable[[list[dict[str, object]]], dict[str, object]] | None = None,
    ) -> None:
        self.client = client
        self.settings = settings
        self.chooser = chooser or random.choice

    def select_for_player(self, *, player_guid: int) -> BountyRewardSelection | None:
        profile = self._load_player_profile(player_guid=int(player_guid))
        if profile is None:
            return None

        low_level = max(1, int(profile.level) - 4)
        high_level = int(profile.level) + 1
        candidates = self._load_item_candidates(
            profile=profile,
            low_level=low_level,
            high_level=high_level,
            min_quality=2,
        )
        if not candidates:
            candidates = self._load_item_candidates(
                profile=profile,
                low_level=low_level,
                high_level=high_level,
                min_quality=1,
            )
        if not candidates:
            return None

        selected = self.chooser(candidates)
        return BountyRewardSelection(
            item_entry=int(selected["entry"]),
            item_name=str(selected["name"]),
            player_level=int(profile.level),
            required_level_min=low_level,
            required_level_max=high_level,
            candidate_count=len(candidates),
        )

    def _load_player_profile(self, *, player_guid: int) -> PlayerRewardProfile | None:
        rows = self.client.query(
            host=self.settings.char_db_host,
            port=self.settings.char_db_port,
            user=self.settings.char_db_user,
            password=self.settings.char_db_password,
            database=self.settings.char_db_name,
            sql=(
                "SELECT class, level FROM characters "
                f"WHERE guid = {int(player_guid)} LIMIT 1"
            ),
        )
        if not rows:
            return None
        row = rows[0]
        class_id = int(row.get("class") or 0)
        level = int(row.get("level") or 1)
        class_mask = int(_CLASS_MASK_BY_CLASS_ID.get(class_id, 0))
        armor_subclasses = tuple(sorted(self._resolve_armor_subclasses(player_guid=int(player_guid), class_id=class_id, level=level)))
        return PlayerRewardProfile(
            player_guid=int(player_guid),
            class_id=class_id,
            level=level,
            class_mask=class_mask,
            armor_subclasses=armor_subclasses,
        )

    def _resolve_armor_subclasses(self, *, player_guid: int, class_id: int, level: int) -> set[int]:
        subclasses = {0, _baseline_armor_subclass(class_id=class_id, level=level)}
        rows = self.client.query(
            host=self.settings.char_db_host,
            port=self.settings.char_db_port,
            user=self.settings.char_db_user,
            password=self.settings.char_db_password,
            database=self.settings.char_db_name,
            sql=(
                "SELECT skill FROM character_skills "
                f"WHERE guid = {int(player_guid)} "
                "AND skill IN (293, 413, 414, 433)"
            ),
        )
        for row in rows:
            skill_id = int(row.get("skill") or 0)
            subclass = _ARMOR_SKILL_TO_SUBCLASS.get(skill_id)
            if subclass is not None:
                subclasses.add(int(subclass))
        return subclasses

    def _load_item_candidates(
        self,
        *,
        profile: PlayerRewardProfile,
        low_level: int,
        high_level: int,
        min_quality: int,
    ) -> list[dict[str, object]]:
        subclass_list = ", ".join(str(int(subclass)) for subclass in profile.armor_subclasses)
        inventory_type_list = ", ".join(str(int(value)) for value in _EQUIPMENT_INVENTORY_TYPES)
        class_mask = int(profile.class_mask)
        allowable_class_filter = "1 = 1"
        if class_mask > 0:
            allowable_class_filter = (
                f"(AllowableClass IS NULL OR AllowableClass IN (0, -1, 4294967295) OR (AllowableClass & {class_mask}) <> 0)"
            )
        return self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=(
                "SELECT entry, name, Quality, ItemLevel, RequiredLevel, class, subclass, InventoryType, AllowableClass "
                "FROM item_template "
                "WHERE class = 4 "
                "AND entry < 900000 "
                "AND COALESCE(name, '') <> '' "
                f"AND {' AND '.join(_NAME_EXCLUSION_SQL)} "
                f"AND subclass IN ({subclass_list}) "
                f"AND InventoryType IN ({inventory_type_list}) "
                f"AND RequiredLevel BETWEEN {int(low_level)} AND {int(high_level)} "
                f"AND Quality BETWEEN {int(min_quality)} AND 4 "
                f"AND {allowable_class_filter} "
                "AND ("
                "EXISTS (SELECT 1 FROM creature_loot_template WHERE creature_loot_template.item = item_template.entry) "
                "OR EXISTS (SELECT 1 FROM reference_loot_template WHERE reference_loot_template.item = item_template.entry)"
                ") "
                "ORDER BY RequiredLevel DESC, Quality DESC, entry ASC "
                "LIMIT 200"
            ),
        )


def _baseline_armor_subclass(*, class_id: int, level: int) -> int:
    resolved_level = max(1, int(level))
    if class_id in {1, 2, 6}:  # Warrior, Paladin, Death Knight
        return 4 if resolved_level >= 40 else 3
    if class_id in {3, 7}:  # Hunter, Shaman
        return 3 if resolved_level >= 40 else 2
    if class_id in {4, 11}:  # Rogue, Druid
        return 2
    return 1  # Mage, Priest, Warlock and unknown -> Cloth
