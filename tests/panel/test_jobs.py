from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from wm.panel.catalog import CommandCatalog
from wm.panel.catalog import CommandEntry
from wm.panel.jobs import JobRunner
from wm.panel.state import PanelState


class PanelJobRunnerTests(unittest.TestCase):
    def test_mutating_job_requires_dry_run_and_matching_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runner = _runner(Path(temp))

            job = runner.run_dry_run(command_id="test.mutate", payload={"schema_version": "x"})
            self.assertEqual(job["state"], "AWAITING_CONFIRM")

            rejected = runner.run_apply(job_id=job["job_id"], confirmation="wrong")
            self.assertEqual(rejected["state"], "AWAITING_CONFIRM")
            self.assertFalse(rejected["apply_attempts"][0]["ok"])

            applied = runner.run_apply(job_id=job["job_id"], confirmation=job["job_id"])
            self.assertEqual(applied["state"], "APPLIED")
            self.assertIn("apply", applied)

    def test_read_only_command_cannot_apply(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runner = _runner(Path(temp))

            job = runner.run_dry_run(command_id="test.read", payload={"schema_version": "x"})
            result = runner.run_apply(job_id=job["job_id"], confirmation=job["job_id"])

            self.assertEqual(result["state"], "INVALID")
            self.assertIn("Read-only", result["issues"][0]["message"])

    def test_subprocess_uses_shell_false(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runner = _runner(Path(temp))
            completed = subprocess.CompletedProcess(args=["x"], returncode=0, stdout="ok", stderr="")
            with patch("wm.panel.jobs.subprocess.run", return_value=completed) as mocked_run:
                runner.run_dry_run(command_id="test.read")

            self.assertFalse(mocked_run.call_args.kwargs["shell"])

    def test_unknown_command_returns_invalid_job(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = _runner(Path(temp)).run_dry_run(command_id="missing.command")

            self.assertEqual(result["state"], "INVALID")
            self.assertEqual(result["issues"][0]["path"], "command_id")


class PanelCatalogTests(unittest.TestCase):
    def test_marker_scan_is_read_only_and_uses_native_marker_cli(self) -> None:
        entry = CommandCatalog().get("marker.scan")

        self.assertFalse(entry.mutating)
        self.assertIn("wm.sources.native_bridge.player_marker", entry.dry_run_argv)
        self.assertIn("scan", entry.dry_run_argv)
        self.assertFalse(entry.apply_argv)

    def test_marker_scope_latest_is_gated_mutation(self) -> None:
        entry = CommandCatalog().get("marker.scope_latest")

        self.assertTrue(entry.mutating)
        self.assertTrue(entry.dry_run_required)
        self.assertEqual(entry.confirmation, "type_job_id")
        self.assertIn("scan", entry.dry_run_argv)
        self.assertIn("scope-latest", entry.apply_argv)

    def test_observe_all_commands_are_gated_through_existing_configure_cli(self) -> None:
        catalog = CommandCatalog()

        for command_id in ("marker.observe_all.start", "marker.observe_all.stop"):
            entry = catalog.get(command_id)
            self.assertTrue(entry.mutating)
            self.assertTrue(entry.dry_run_required)
            self.assertEqual(entry.confirmation, "type_job_id")
            self.assertIn("wm.sources.native_bridge.configure", entry.apply_argv)


def _runner(root: Path) -> JobRunner:
    catalog = CommandCatalog(
        [
            CommandEntry(
                id="test.mutate",
                label="Mutate",
                category="test",
                kind="mutation",
                dry_run_argv=(sys.executable, "-c", "print('dry')"),
                apply_argv=(sys.executable, "-c", "print('apply')"),
                mutating=True,
                dry_run_required=True,
                confirmation="type_job_id",
            ),
            CommandEntry(
                id="test.read",
                label="Read",
                category="test",
                kind="read_only",
                dry_run_argv=(sys.executable, "-c", "print('read')"),
            ),
        ]
    )
    return JobRunner(state=PanelState(root), catalog=catalog, cwd=Path.cwd())


if __name__ == "__main__":
    unittest.main()
