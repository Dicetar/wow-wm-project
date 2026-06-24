from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from wm.panel.catalog import CommandCatalog
from wm.panel.catalog import CommandEntry
from wm.panel.catalog import ParameterSpec
from wm.panel.jobs import JobRunner
from wm.panel.state import PanelState
from wm.panel.state import utc_now_iso


class PanelJobRunnerTests(unittest.TestCase):
    def test_marker_target_job_injects_session_guid_and_rejects_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = PanelState(root)
            state.save_session(_marker_session(3838))
            entry = CommandEntry(
                id="test.marker",
                label="Marker",
                category="test",
                kind="read_only",
                dry_run_argv=(sys.executable, "-c", "print('{player_guid}')"),
                parameters=(ParameterSpec("player_guid", type="integer"),),
                marker_target_required=True,
            )
            runner = JobRunner(state=state, catalog=CommandCatalog([entry]), cwd=Path.cwd())
            injected = runner.run_dry_run(command_id="test.marker")
            self.assertEqual(injected["params"]["player_guid"], 3838)
            self.assertEqual(injected["state"], "DRY_RUN_PASSED")
            conflict = runner.run_dry_run(command_id="test.marker", params={"player_guid": 5406})
            self.assertEqual(conflict["state"], "INVALID")
            self.assertIn("conflicts", conflict["issues"][0]["message"])

    def test_marker_target_job_rejects_stale_offline_or_incomplete_session(self) -> None:
        entry = CommandEntry(
            id="test.marker",
            label="Marker",
            category="test",
            kind="read_only",
            dry_run_argv=(sys.executable, "-c", "print('{player_guid}')"),
            parameters=(ParameterSpec("player_guid", type="integer"),),
            marker_target_required=True,
        )

        cases = [
            (_marker_session(3838, online=False), "not confirmed online"),
            (_marker_session(3838, bridge_event_id=None), "bridge event id"),
            (_marker_session(3838, selected_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()), "stale"),
        ]
        for session, message in cases:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as temp:
                state = PanelState(Path(temp))
                state.save_session(session)
                runner = JobRunner(state=state, catalog=CommandCatalog([entry]), cwd=Path.cwd())
                result = runner.run_dry_run(command_id="test.marker")

                self.assertEqual(result["state"], "INVALID")
                self.assertIn(message, result["issues"][0]["message"])

    def test_marker_target_apply_revalidates_active_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = PanelState(root)
            state.save_session(_marker_session(3838))
            entry = CommandEntry(
                id="test.marker.mutate",
                label="Marker Mutate",
                category="test",
                kind="mutation",
                dry_run_argv=(sys.executable, "-c", "print('{player_guid}')"),
                apply_argv=(sys.executable, "-c", "print('{player_guid}')"),
                mutating=True,
                dry_run_required=True,
                confirmation="type_job_id",
                parameters=(ParameterSpec("player_guid", type="integer"),),
                marker_target_required=True,
            )
            runner = JobRunner(state=state, catalog=CommandCatalog([entry]), cwd=Path.cwd())
            job = runner.run_dry_run(command_id="test.marker.mutate")
            self.assertEqual(job["state"], "AWAITING_CONFIRM")

            state.save_session(_marker_session(3838, online=False))
            rejected = runner.run_apply(job_id=job["job_id"], confirmation=job["job_id"])

            self.assertEqual(rejected["state"], "INVALID")
            self.assertIn("not confirmed online", rejected["issues"][0]["message"])

    def test_marker_target_job_requires_canonical_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            entry = CommandEntry(
                id="test.marker",
                label="Marker",
                category="test",
                kind="read_only",
                dry_run_argv=(sys.executable, "-c", "print('x')"),
                marker_target_required=True,
            )
            runner = JobRunner(state=PanelState(Path(temp)), catalog=CommandCatalog([entry]), cwd=Path.cwd())
            result = runner.run_dry_run(command_id="test.marker")
            self.assertEqual(result["state"], "INVALID")
            self.assertIn("canonical marker-selected", result["issues"][0]["message"])

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

    def test_marker_arc_scenario_generation_requires_marker_target(self) -> None:
        entry = CommandCatalog().get("arc.marker_scenario.generate")

        self.assertFalse(entry.mutating)
        self.assertTrue(entry.marker_target_required)
        self.assertIn("wm.arcs.marker_scenario", entry.dry_run_argv)
        self.assertIn("--player-guid", entry.dry_run_argv)
        self.assertIn("--db-profile", entry.dry_run_argv)
        self.assertIn("bridgelab", entry.dry_run_argv)

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


def _marker_session(
    guid: int,
    *,
    online: bool = True,
    bridge_event_id: int | None = 77,
    selected_at: str | None = None,
) -> dict:
    return {
        "source": "marker",
        "marker_spell_id": 946602,
        "character_guid": int(guid),
        "bridge_event_id": bridge_event_id,
        "selected_at": selected_at or utc_now_iso(),
        "marker": {"character_online": bool(online)},
    }


if __name__ == "__main__":
    unittest.main()
