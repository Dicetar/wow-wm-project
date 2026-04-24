import unittest

from wm.config import Settings
from wm.quests.reward_picker import BountyEquipmentRewardPicker


class _RewardPickerClient:
    def __init__(self, *, class_id: int, level: int, skills: list[int], item_rows: list[dict[str, object]]) -> None:
        self.class_id = int(class_id)
        self.level = int(level)
        self.skills = list(skills)
        self.item_rows = list(item_rows)
        self.world_item_sql: list[str] = []

    def query(self, *, host: str, port: int, user: str, password: str, database: str, sql: str):
        del host, port, user, password
        if database == "acore_characters" and "SELECT class, level FROM characters" in sql:
            return [{"class": str(self.class_id), "level": str(self.level)}]
        if database == "acore_characters" and "FROM character_skills" in sql:
            return [{"skill": str(skill_id)} for skill_id in self.skills]
        if database == "acore_world" and "FROM item_template" in sql:
            self.world_item_sql.append(sql)
            return list(self.item_rows)
        raise AssertionError(f"Unexpected SQL for {database}: {sql}")


class BountyRewardPickerTests(unittest.TestCase):
    def test_warlock_with_explicit_shield_and_leather_grants_can_roll_exception_items(self) -> None:
        client = _RewardPickerClient(
            class_id=9,
            level=26,
            skills=[414, 433],
            item_rows=[
                {"entry": "910006", "name": "Night Watcher's Lens"},
                {"entry": "910005", "name": "Ice-Layered Barrier"},
            ],
        )
        picker = BountyEquipmentRewardPicker(
            client=client,  # type: ignore[arg-type]
            settings=Settings(),
            chooser=lambda rows: rows[-1],
        )

        selection = picker.select_for_player(player_guid=5406)

        self.assertIsNotNone(selection)
        assert selection is not None
        self.assertEqual(selection.item_entry, 910005)
        self.assertEqual(selection.item_name, "Ice-Layered Barrier")
        self.assertEqual(selection.required_level_min, 22)
        self.assertEqual(selection.required_level_max, 27)
        self.assertIn("subclass IN (0, 1, 2, 6)", client.world_item_sql[0])
        self.assertIn("name NOT LIKE 'Test %'", client.world_item_sql[0])
        self.assertIn("EXISTS (SELECT 1 FROM creature_loot_template", client.world_item_sql[0])

    def test_warrior_below_40_stays_in_mail_pool(self) -> None:
        client = _RewardPickerClient(
            class_id=1,
            level=26,
            skills=[],
            item_rows=[{"entry": "3001", "name": "Razorfen Mail Hauberk"}],
        )
        picker = BountyEquipmentRewardPicker(
            client=client,  # type: ignore[arg-type]
            settings=Settings(),
            chooser=lambda rows: rows[0],
        )

        selection = picker.select_for_player(player_guid=77)

        self.assertIsNotNone(selection)
        assert selection is not None
        self.assertEqual(selection.item_entry, 3001)
        self.assertIn("subclass IN (0, 3)", client.world_item_sql[0])

    def test_returns_none_when_no_suitable_equipment_candidates_exist(self) -> None:
        client = _RewardPickerClient(
            class_id=8,
            level=20,
            skills=[],
            item_rows=[],
        )
        picker = BountyEquipmentRewardPicker(
            client=client,  # type: ignore[arg-type]
            settings=Settings(),
        )

        selection = picker.select_for_player(player_guid=42)

        self.assertIsNone(selection)
        self.assertEqual(len(client.world_item_sql), 2)


if __name__ == "__main__":
    unittest.main()
