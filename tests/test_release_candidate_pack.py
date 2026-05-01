from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import unittest

from wm.candidates.release_pack import RELEASE_CANDIDATE_PACK_SCHEMA
from wm.candidates.release_pack import build_release_candidate_pack
from wm.candidates.release_pack import build_release_test_manifest
from wm.candidates.release_pack import main
from wm.candidates.release_pack import render_release_candidate_pack_summary
from wm.candidates.release_pack import render_release_candidate_pack_write_summary
from wm.content.release import validate_content_release_spec
from wm.candidates.release_pack import write_release_candidate_pack


class ReleaseCandidatePackTests(unittest.TestCase):
    def test_builds_ready_release_specs_from_context_pack(self) -> None:
        pack = build_release_candidate_pack(_context_pack())
        candidates = {candidate["lane"]: candidate for candidate in pack["candidates"]}

        self.assertEqual(pack["schema_version"], RELEASE_CANDIDATE_PACK_SCHEMA)
        self.assertEqual(pack["status"], "READY")
        self.assertEqual(pack["player_guid"], 5406)
        self.assertEqual(pack["target"]["slug"], "murloc_forager")
        for lane in ("repeatable_bounty", "story_arc", "shell_ability", "native_scene"):
            self.assertEqual(candidates[lane]["status"], "ready")
            self.assertEqual(candidates[lane]["packet_status"], "PACKET_READY")
            result = validate_content_release_spec(candidates[lane]["release_spec"])
            self.assertTrue(result.ok, f"{lane}: {result.to_dict()}")
        self.assertEqual(candidates["managed_item_power"]["status"], "blocked_needs_id_reservation")
        self.assertIn("fresh_item_entry_required", candidates["managed_item_power"]["blockers"])

    def test_item_power_becomes_ready_when_fresh_ids_are_supplied(self) -> None:
        pack = build_release_candidate_pack(_context_pack(), reserved_item_entry=910999, base_item_entry=2586)
        candidate = next(item for item in pack["candidates"] if item["lane"] == "managed_item_power")
        spec = candidate["release_spec"]

        self.assertEqual(candidate["status"], "ready")
        self.assertEqual(candidate["packet_status"], "PACKET_READY")
        self.assertTrue(validate_content_release_spec(spec).ok)
        self.assertEqual(spec["schema_version"], "wm.item.release.managed_power.v1")
        self.assertEqual(spec["item_entry"], 910999)
        self.assertEqual(spec["base_item_entry"], 2586)
        self.assertEqual(spec["slot_policy"], "fresh_item_slot_required")

    def test_blocks_story_arc_when_journey_is_not_ready(self) -> None:
        context = _context_pack()
        context["generation_input"]["journey"]["eligibility"] = {
            "ready_for_arc_factory": False,
            "blocked_reasons": ["profile_missing"],
            "active_arc_keys": [],
        }

        pack = build_release_candidate_pack(context)
        story = next(candidate for candidate in pack["candidates"] if candidate["lane"] == "story_arc")

        self.assertEqual(story["status"], "blocked_by_journey")
        self.assertIn("profile_missing", story["blockers"])
        self.assertTrue(validate_content_release_spec(story["release_spec"]).ok)

    def test_summary_and_cli_render_candidates(self) -> None:
        temp_path = Path(".pytest-tmp") / "release-candidate-context.json"
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(json.dumps(_context_pack()), encoding="utf-8")

        summary = render_release_candidate_pack_summary(build_release_candidate_pack(_context_pack()))
        self.assertIn("murloc_forager_choice_arc", summary)

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = main(["--context-pack-json", str(temp_path), "--summary"])

        self.assertEqual(exit_code, 0)
        self.assertIn("schema_version: wm.release_candidate_pack.v1", stdout.getvalue())
        self.assertIn("managed_item_power", stdout.getvalue())

    def test_writer_exports_pack_and_ready_release_specs(self) -> None:
        output_dir = Path(".pytest-tmp") / "release-candidate-pack-writer"
        result = write_release_candidate_pack(_context_pack(), output_dir, allow_overwrite=True)
        summary = render_release_candidate_pack_write_summary(result)

        self.assertEqual(result["schema_version"], "wm.release_candidate_pack_write.v1")
        self.assertEqual(result["status"], "WRITTEN")
        self.assertEqual(result["packet_write_count"], 0)
        self.assertTrue((output_dir / "release_candidate_pack.json").exists())
        self.assertTrue((output_dir / "murloc_forager_choice_arc.release.json").exists())
        self.assertFalse((output_dir / "murloc_forager_managed_item_power.release.json").exists())
        self.assertIn("release_candidate_pack", summary)

        with self.assertRaises(ValueError):
            write_release_candidate_pack(_context_pack(), output_dir)

    def test_writer_can_emit_release_packets_for_ready_candidates(self) -> None:
        output_dir = Path(".pytest-tmp") / "release-candidate-pack-packets"
        result = write_release_candidate_pack(
            _context_pack(),
            output_dir,
            allow_overwrite=True,
            reserved_item_entry=910999,
            base_item_entry=2586,
            write_packets=True,
            write_test_manifest=True,
        )
        summary = render_release_candidate_pack_write_summary(result)

        self.assertEqual(result["packet_write_count"], 5)
        self.assertTrue(result["test_manifest_written"])
        self.assertTrue((output_dir / "murloc_forager_managed_item_power.release.json").exists())
        self.assertTrue((output_dir / "murloc_forager_managed_item_power.packet" / "release_packet.json").exists())
        self.assertTrue((output_dir / "murloc_forager_managed_item_power.packet" / "managed-item-power-contract.json").exists())
        self.assertTrue((output_dir / "release_test_manifest.json").exists())
        self.assertIn("release_packet:managed_item_power_contract", summary)
        self.assertIn("release_test_manifest", summary)

        manifest = json.loads((output_dir / "release_test_manifest.json").read_text(encoding="utf-8"))
        all_commands = "\n".join(
            command
            for candidate in manifest["candidates"]
            for command in candidate["dry_run_commands"]
        )
        self.assertEqual(manifest["schema_version"], "wm.release_candidate_test_manifest.v1")
        self.assertEqual(manifest["status"], "TEST_READY")
        self.assertEqual(manifest["candidate_count"], 5)
        self.assertIn("python -m wm.control.scene_play", all_commands)
        self.assertIn("python -m wm.character.journey apply", all_commands)

    def test_build_release_test_manifest_without_written_artifacts(self) -> None:
        pack = build_release_candidate_pack(_context_pack(), reserved_item_entry=910999, base_item_entry=2586)

        manifest = build_release_test_manifest(pack)
        commands = "\n".join(
            command
            for candidate in manifest["candidates"]
            for command in candidate["dry_run_commands"]
        )

        self.assertEqual(manifest["status"], "TEST_READY")
        self.assertIn("python -m pytest -q tests/test_content_release.py tests/test_release_candidate_pack.py", manifest["preflight_commands"])
        self.assertIn("--emit-control-scene", commands)
        self.assertIn("--emit-journey-plan", commands)

    def test_cli_writes_candidates(self) -> None:
        temp_path = Path(".pytest-tmp") / "release-candidate-context.json"
        output_dir = Path(".pytest-tmp") / "release-candidate-pack-cli"
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(json.dumps(_context_pack()), encoding="utf-8")
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = main(
                [
                    "--context-pack-json",
                    str(temp_path),
                    "--write-candidates-dir",
                    str(output_dir),
                    "--force",
                    "--summary",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("wm.release_candidate_pack_write.v1", stdout.getvalue())
        self.assertTrue((output_dir / "murloc_forager_targeted_projectile_power.release.json").exists())

    def test_cli_writes_managed_item_candidate_when_ids_are_supplied(self) -> None:
        temp_path = Path(".pytest-tmp") / "release-candidate-context.json"
        output_dir = Path(".pytest-tmp") / "release-candidate-pack-cli-item"
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(json.dumps(_context_pack()), encoding="utf-8")
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = main(
                [
                    "--context-pack-json",
                    str(temp_path),
                    "--reserved-item-entry",
                    "910999",
                    "--base-item-entry",
                    "2586",
                    "--write-candidates-dir",
                    str(output_dir),
                    "--write-packets",
                    "--write-test-manifest",
                    "--force",
                    "--summary",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("wm.release_candidate_pack_write.v1", stdout.getvalue())
        self.assertTrue((output_dir / "murloc_forager_managed_item_power.release.json").exists())
        self.assertTrue((output_dir / "murloc_forager_managed_item_power.packet" / "release_packet.json").exists())
        self.assertTrue((output_dir / "release_test_manifest.json").exists())

    def test_repository_release_candidate_example_builds(self) -> None:
        path = Path("control/examples/release_candidates/murloc_forager_context_pack.json")
        context = json.loads(path.read_text(encoding="utf-8"))

        pack = build_release_candidate_pack(context)

        self.assertEqual(pack["status"], "READY")
        self.assertEqual(pack["target"]["slug"], "murloc_forager")
        self.assertTrue(any(candidate["packet_status"] == "PACKET_READY" for candidate in pack["candidates"]))


def _context_pack() -> dict:
    return {
        "schema_version": "wm.context_pack.v1",
        "player_guid": 5406,
        "target_profile": {
            "entry": 46,
            "name": "Murloc Forager",
            "level_min": 9,
            "level_max": 10,
            "mechanical_type": "HUMANOID",
            "faction_label": "Murloc",
        },
        "generation_input": {
            "player": {
                "guid": 5406,
                "name": "Jecia",
            },
            "trigger": {
                "event_type": "kill",
                "source": "native_bridge",
                "source_event_key": "bridge:12",
            },
            "target": {
                "entry": 46,
                "name": "Murloc Forager",
                "mechanical_type": "HUMANOID",
                "faction_label": "Murloc",
            },
            "history": {
                "kill_count": 3,
                "summary_lines": ["Jecia has been thinning the shoreline murlocs."],
            },
            "journey": {
                "eligibility": {
                    "ready_for_arc_factory": True,
                    "blocked_reasons": [],
                    "active_arc_keys": ["jecia_world_master_awakened"],
                    "unlock_refs": ["shell_spell:940001"],
                    "reward_refs": ["item:910006"],
                },
                "steering": [
                    {
                        "key": "visible_first",
                        "body": "Prioritize visible wild powers.",
                    }
                ],
            },
            "eligible_recipe_ids": ["reactive_bounty"],
        },
    }


if __name__ == "__main__":
    unittest.main()
