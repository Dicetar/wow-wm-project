import json
import shutil
import unittest
from pathlib import Path

from wm.control.models import ControlProposal
from wm.control.registry import ControlRegistry


class ControlRegistryTests(unittest.TestCase):
    def test_repo_registry_loads_and_validates(self) -> None:
        registry = ControlRegistry.load("control")

        self.assertEqual(registry.validate(), [])
        self.assertIn("quest_grant", registry.actions)
        self.assertIn("native_bridge_action", registry.actions)
        self.assertIn("kill_burst_bounty", [recipe["id"] for recipe in registry.eligible_recipes_for_event_type("kill")])
        self.assertEqual(len(registry.registry_hash), 64)
        self.assertEqual(len(registry.schema_hash), 64)

    def test_example_proposal_matches_pydantic_schema(self) -> None:
        proposal = ControlProposal.model_validate_json(
            Path("control/examples/proposals/manual_kill_burst_bounty.json").read_text(encoding="utf-8")
        )

        self.assertEqual(proposal.schema_version, "control.proposal.v1")
        self.assertEqual(proposal.action.kind, "quest_grant")

        native_proposal = ControlProposal.model_validate_json(
            Path("control/examples/proposals/manual_native_debug_ping.json").read_text(encoding="utf-8")
        )

        self.assertEqual(native_proposal.selected_recipe, "manual_admin_action")
        self.assertEqual(native_proposal.action.kind, "native_bridge_action")

    def test_duplicate_control_ids_are_rejected(self) -> None:
        root = Path(".tmp/control_registry_duplicate")
        if root.exists():
            shutil.rmtree(root)
        try:
            root.mkdir(parents=True)
            (root / "events").mkdir()
            (root / "actions").mkdir()
            (root / "recipes").mkdir()
            (root / "policies").mkdir()
            (root / "runtime").mkdir()
            (root / "registry.json").write_text(
                json.dumps(
                    {
                        "events_dir": "events",
                        "actions_dir": "actions",
                        "recipes_dir": "recipes",
                        "policies_dir": "policies",
                        "runtime_dir": "runtime",
                    }
                ),
                encoding="utf-8",
            )
            duplicate = {"id": "kill", "schema_version": "control.event.v1", "event_type": "kill"}
            (root / "events" / "a.json").write_text(json.dumps(duplicate), encoding="utf-8")
            (root / "events" / "b.json").write_text(json.dumps(duplicate), encoding="utf-8")

            with self.assertRaises(ValueError):
                ControlRegistry.load(root)
        finally:
            if root.exists():
                shutil.rmtree(root)


if __name__ == "__main__":
    unittest.main()
