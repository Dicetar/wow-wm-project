from __future__ import annotations

import json
from pathlib import Path
import unittest

from wm.panel.schemas import SchemaCatalog


class PanelSchemaCatalogTests(unittest.TestCase):
    def test_catalog_loads_initial_schema_versions(self) -> None:
        catalog = SchemaCatalog.load()
        schema_ids = {entry.id for entry in catalog.entries}

        self.assertIn("control.proposal.v1", schema_ids)
        self.assertIn("wm.quest.release.repeatable_bounty.v1", schema_ids)
        self.assertIn("wm.quest.release.one_shot.v1", schema_ids)
        self.assertIn("wm.quest.release.story_arc.v1", schema_ids)
        self.assertIn("wm.item.release.managed_power.v1", schema_ids)
        self.assertIn("wm.spell.release.managed_spell.v1", schema_ids)
        self.assertIn("wm.ability.release.shell_power.v1", schema_ids)
        self.assertIn("wm.scene.release.native_sequence.v1", schema_ids)
        self.assertIn("properties", catalog.get("control.proposal.v1").schema)

    def test_examples_validate_through_domain_validators(self) -> None:
        catalog = SchemaCatalog.load()
        examples = [
            "control/examples/content_releases/repeatable_bounty_template.json",
            "control/examples/content_releases/one_shot_template.json",
            "control/examples/content_releases/story_arc_choice_template.json",
            "control/examples/content_releases/items/fresh_item_power_template.json",
            "control/examples/content_releases/abilities/targeted_instant_template.json",
            "control/examples/content_releases/scenes/creature_marker_scene_template.json",
        ]

        for example in examples:
            with self.subTest(example=example):
                payload = json.loads(Path(example).read_text(encoding="utf-8"))
                result = catalog.validate(str(payload["schema_version"]), payload)
                self.assertTrue(result["ok"], result)

    def test_unknown_schema_is_invalid(self) -> None:
        result = SchemaCatalog.load().validate("unknown.schema", {})

        self.assertFalse(result["ok"])
        self.assertEqual(result["issues"][0]["path"], "schema_version")

    def test_obviously_bogus_large_ids_are_invalid(self) -> None:
        payload = json.loads(Path("control/examples/content_releases/repeatable_bounty_template.json").read_text(encoding="utf-8"))
        payload["quest"]["end_npc_entry"] = 6478923553423543

        result = SchemaCatalog.load().validate(str(payload["schema_version"]), payload)

        self.assertFalse(result["ok"])
        self.assertIn("quest.end_npc_entry", {issue["path"] for issue in result["issues"]})

    def test_managed_item_shape_dropdown_values_validate(self) -> None:
        payload = json.loads(Path("control/examples/content_releases/items/fresh_item_power_template.json").read_text(encoding="utf-8"))
        payload["item_shape"] = {
            "item_class": "armor",
            "inventory_type": "shield",
            "armor_subclass": "shield",
            "weapon_subclass": None,
            "quality": "uncommon",
            "binding": "on_equip",
            "required_level": 12,
            "stackable": 1,
        }

        result = SchemaCatalog.load().validate(str(payload["schema_version"]), payload)

        self.assertTrue(result["ok"], result)


if __name__ == "__main__":
    unittest.main()
