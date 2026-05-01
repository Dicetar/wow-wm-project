from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from wm.reserved.custom_id_registry import load_custom_id_registry
from wm.reserved.custom_id_registry import validate_custom_id_registry


class CustomIdRegistryTests(unittest.TestCase):
    def test_default_registry_loads_and_validates(self) -> None:
        registry = load_custom_id_registry()
        validation = validate_custom_id_registry()

        self.assertTrue(validation.ok)
        self.assertEqual(registry.schema_version, "wm.custom_id_registry.v1")
        self.assertIsNotNone(registry.range_by_key(namespace="spell", range_key="managed_spell_slots"))
        self.assertIsNotNone(registry.claim_by_id(namespace="spell", id=940001))

    def test_retired_visible_ids_are_marked_broken_and_replaced(self) -> None:
        registry = load_custom_id_registry()

        retired_item = registry.claim_by_id(namespace="item", id=910010)
        retired_item_v2 = registry.claim_by_id(namespace="item", id=910011)
        retired_item_v3 = registry.claim_by_id(namespace="item", id=919001)
        retired_item_v4 = registry.claim_by_id(namespace="item", id=919002)
        retired_item_v5 = registry.claim_by_id(namespace="item", id=919003)
        retired_item_v6 = registry.claim_by_id(namespace="item", id=919004)
        retired_item_v7 = registry.claim_by_id(namespace="item", id=919005)
        retired_item_v8 = registry.claim_by_id(namespace="item", id=910012)
        fresh_item = registry.claim_by_id(namespace="item", id=910013)
        retired_quest = registry.claim_by_id(namespace="quest", id=910152)
        retired_quest_v2 = registry.claim_by_id(namespace="quest", id=910154)
        retired_quest_v3 = registry.claim_by_id(namespace="quest", id=910155)
        retired_quest_v4 = registry.claim_by_id(namespace="quest", id=910160)
        retired_quest_v5 = registry.claim_by_id(namespace="quest", id=910167)
        retired_quest_v6 = registry.claim_by_id(namespace="quest", id=910168)
        retired_quest_v7 = registry.claim_by_id(namespace="quest", id=910169)
        retired_quest_v8 = registry.claim_by_id(namespace="quest", id=910170)
        fresh_quest = registry.claim_by_id(namespace="quest", id=910171)

        self.assertIsNotNone(retired_item)
        self.assertIsNotNone(retired_item_v2)
        self.assertIsNotNone(retired_item_v3)
        self.assertIsNotNone(retired_item_v4)
        self.assertIsNotNone(retired_item_v5)
        self.assertIsNotNone(retired_item_v6)
        self.assertIsNotNone(retired_item_v7)
        self.assertIsNotNone(retired_item_v8)
        self.assertIsNotNone(fresh_item)
        self.assertIsNotNone(retired_quest)
        self.assertIsNotNone(retired_quest_v2)
        self.assertIsNotNone(retired_quest_v3)
        self.assertIsNotNone(retired_quest_v4)
        self.assertIsNotNone(retired_quest_v5)
        self.assertIsNotNone(retired_quest_v6)
        self.assertIsNotNone(retired_quest_v7)
        self.assertIsNotNone(retired_quest_v8)
        self.assertIsNotNone(fresh_quest)
        assert retired_item is not None
        assert retired_item_v2 is not None
        assert retired_item_v3 is not None
        assert retired_item_v4 is not None
        assert retired_item_v5 is not None
        assert retired_item_v6 is not None
        assert retired_item_v7 is not None
        assert retired_item_v8 is not None
        assert fresh_item is not None
        assert retired_quest is not None
        assert retired_quest_v2 is not None
        assert retired_quest_v3 is not None
        assert retired_quest_v4 is not None
        assert retired_quest_v5 is not None
        assert retired_quest_v6 is not None
        assert retired_quest_v7 is not None
        assert retired_quest_v8 is not None
        assert fresh_quest is not None
        self.assertEqual(retired_item.status, "BROKEN")
        self.assertEqual(retired_item.replaced_by, "item:910013")
        self.assertEqual(retired_item_v2.status, "BROKEN")
        self.assertEqual(retired_item_v2.replaced_by, "item:910013")
        self.assertEqual(retired_item_v3.status, "BROKEN")
        self.assertEqual(retired_item_v3.replaced_by, "item:910013")
        self.assertEqual(retired_item_v4.status, "BROKEN")
        self.assertEqual(retired_item_v4.replaced_by, "item:910013")
        self.assertEqual(retired_item_v5.status, "BROKEN")
        self.assertEqual(retired_item_v5.replaced_by, "item:910013")
        self.assertEqual(retired_item_v6.status, "BROKEN")
        self.assertEqual(retired_item_v6.replaced_by, "item:910013")
        self.assertEqual(retired_item_v7.status, "BROKEN")
        self.assertEqual(retired_item_v7.replaced_by, "item:910013")
        self.assertEqual(retired_item_v8.status, "BROKEN")
        self.assertEqual(retired_item_v8.replaced_by, "item:910013")
        self.assertEqual(fresh_item.status, "PARTIAL")
        self.assertEqual(retired_quest.status, "BROKEN")
        self.assertEqual(retired_quest.replaced_by, "quest:910171")
        self.assertEqual(retired_quest_v2.status, "BROKEN")
        self.assertEqual(retired_quest_v2.replaced_by, "quest:910171")
        self.assertEqual(retired_quest_v3.status, "BROKEN")
        self.assertEqual(retired_quest_v3.replaced_by, "quest:910171")
        self.assertEqual(retired_quest_v4.status, "BROKEN")
        self.assertEqual(retired_quest_v4.replaced_by, "quest:910171")
        self.assertEqual(retired_quest_v5.status, "BROKEN")
        self.assertEqual(retired_quest_v5.replaced_by, "quest:910171")
        self.assertEqual(retired_quest_v6.status, "BROKEN")
        self.assertEqual(retired_quest_v6.replaced_by, "quest:910171")
        self.assertEqual(retired_quest_v7.status, "BROKEN")
        self.assertEqual(retired_quest_v7.replaced_by, "quest:910171")
        self.assertEqual(retired_quest_v8.status, "BROKEN")
        self.assertEqual(retired_quest_v8.replaced_by, "quest:910171")
        self.assertEqual(fresh_quest.status, "PARTIAL")

    def test_duplicate_exact_claim_in_same_namespace_is_rejected(self) -> None:
        payload = {
            "schema_version": "wm.custom_id_registry.v1",
            "description": "test",
            "ranges": [],
            "claims": [
                {
                    "namespace": "spell",
                    "id": 940001,
                    "key": "alpha",
                    "kind": "shell_spell",
                    "purpose": "alpha",
                    "status": "WORKING",
                    "owner_system": "wm",
                    "source_paths": ["control/runtime/spell_shell_bank.json"],
                },
                {
                    "namespace": "spell",
                    "id": 940001,
                    "key": "duplicate",
                    "kind": "managed_spell_slot",
                    "purpose": "duplicate",
                    "status": "PARTIAL",
                    "owner_system": "wm",
                    "source_paths": ["control/examples/spells/test.json"],
                },
            ],
        }
        validation = _validate_payload(payload)

        self.assertFalse(validation.ok)
        self.assertTrue(any("Duplicate exact claim" in issue["message"] for issue in validation.to_dict()["issues"]))

    def test_same_numeric_id_across_namespaces_is_allowed(self) -> None:
        payload = {
            "schema_version": "wm.custom_id_registry.v1",
            "description": "test",
            "ranges": [],
            "claims": [
                {
                    "namespace": "spell",
                    "id": 940001,
                    "key": "alpha",
                    "kind": "shell_spell",
                    "purpose": "alpha",
                    "status": "WORKING",
                    "owner_system": "wm",
                    "source_paths": ["control/runtime/spell_shell_bank.json"],
                },
                {
                    "namespace": "quest",
                    "id": 940001,
                    "key": "quest_alpha",
                    "kind": "quest_template",
                    "purpose": "quest alpha",
                    "status": "PARTIAL",
                    "owner_system": "wm",
                    "source_paths": ["control/examples/reactive_bounties/example.json"],
                },
            ],
        }
        validation = _validate_payload(payload)

        self.assertTrue(validation.ok)

    def test_overlapping_ranges_are_rejected(self) -> None:
        payload = {
            "schema_version": "wm.custom_id_registry.v1",
            "description": "test",
            "ranges": [
                {
                    "namespace": "spell",
                    "range_key": "first",
                    "start_id": 947000,
                    "end_id": 947100,
                    "purpose": "first",
                    "status": "WORKING",
                    "allocation_rule": "first",
                },
                {
                    "namespace": "spell",
                    "range_key": "second",
                    "start_id": 947050,
                    "end_id": 947200,
                    "purpose": "second",
                    "status": "WORKING",
                    "allocation_rule": "second",
                },
            ],
            "claims": [],
        }
        validation = _validate_payload(payload)

        self.assertFalse(validation.ok)
        self.assertTrue(any("overlaps" in issue["message"] for issue in validation.to_dict()["issues"]))

    def test_unknown_status_is_rejected(self) -> None:
        payload = {
            "schema_version": "wm.custom_id_registry.v1",
            "description": "test",
            "ranges": [],
            "claims": [
                {
                    "namespace": "spell",
                    "id": 947000,
                    "key": "bad_status",
                    "kind": "managed_spell_slot",
                    "purpose": "bad status",
                    "status": "DONE",
                    "owner_system": "wm",
                    "source_paths": ["control/examples/spells/test.json"],
                },
            ],
        }
        validation = _validate_payload(payload)

        self.assertFalse(validation.ok)
        self.assertTrue(any(issue["path"].endswith(".status") for issue in validation.to_dict()["issues"]))

    def test_broken_visible_claim_requires_replacement(self) -> None:
        payload = {
            "schema_version": "wm.custom_id_registry.v1",
            "description": "test",
            "ranges": [],
            "claims": [
                {
                    "namespace": "item",
                    "id": 910010,
                    "key": "bad_item",
                    "kind": "managed_item_slot",
                    "purpose": "bad live proof",
                    "status": "BROKEN",
                    "owner_system": "wm",
                    "source_paths": ["docs/CUSTOM_ID_LEDGER.md"],
                },
            ],
        }
        validation = _validate_payload(payload)

        self.assertFalse(validation.ok)
        self.assertTrue(any(issue["path"].endswith(".replaced_by") for issue in validation.to_dict()["issues"]))


def _validate_payload(payload: dict[str, object]):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp).joinpath("registry.json")
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return validate_custom_id_registry(path)


if __name__ == "__main__":
    unittest.main()
