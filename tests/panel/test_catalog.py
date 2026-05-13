from __future__ import annotations

from pathlib import Path
import sys
import unittest

from wm.panel.catalog import CommandCatalog


class PanelCommandCatalogTests(unittest.TestCase):
    def test_catalog_has_allowlisted_commands(self) -> None:
        catalog = CommandCatalog()
        command_ids = {entry.id for entry in catalog.entries}

        self.assertIn("watcher.status", command_ids)
        self.assertIn("content.release.plan", command_ids)
        self.assertIn("control.apply", command_ids)
        self.assertIn("workbench.publish_item", command_ids)

    def test_mutating_commands_require_dry_run_and_confirmation(self) -> None:
        for entry in CommandCatalog().entries:
            if entry.mutating:
                self.assertTrue(entry.dry_run_required, entry.id)
                self.assertEqual(entry.confirmation, "type_job_id", entry.id)
                self.assertTrue(entry.apply_argv, entry.id)

    def test_python_templates_resolve_without_shell_strings(self) -> None:
        entry = CommandCatalog().get("content.release.plan")
        argv = entry.argv_for(
            mode="dry-run",
            params={},
            paths={
                "input_json": Path("spec.json"),
                "proposal_json": Path("proposal.json"),
                "context_pack_json": Path("context.json"),
                "candidate_dir": Path("candidates"),
                "packet_dir": Path("packet"),
                "result_json": Path("result.json"),
                "job_dir": Path("."),
            },
        )

        self.assertEqual(argv[0], sys.executable)
        self.assertIn("wm.content.release", argv)
        self.assertNotIn("shell=True", " ".join(argv))


if __name__ == "__main__":
    unittest.main()
