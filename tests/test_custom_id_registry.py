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


def _validate_payload(payload: dict[str, object]):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp).joinpath("registry.json")
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return validate_custom_id_registry(path)


if __name__ == "__main__":
    unittest.main()
