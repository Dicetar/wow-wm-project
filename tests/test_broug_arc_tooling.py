import json
import tempfile
import unittest
from pathlib import Path

from wm.arcs.scaffold import build_scaffold_plan
from wm.bridge_lab.release_gate import build_release_gate_plan
from wm.content.preflight import _empty_court_custom_creature_entries
from wm.content.preflight import preflight_arc
from wm.live.proof_packet import build_proof_packet
from wm.spells.broug_empty_court import BROUG_EMPTY_COURT_ARC_KEY
from wm.spells.broug_lightness import BROUG_LIGHTNESS_ARC_KEY
from wm.spells.shell_audit import audit_spell_shells
from wm.spells.shell_bank import default_shell_bank_path


class BrougArcToolingTests(unittest.TestCase):
    def test_preflight_accepts_current_broug_arcs(self) -> None:
        lightness = preflight_arc(arc_key=BROUG_LIGHTNESS_ARC_KEY)
        empty_court = preflight_arc(arc_key=BROUG_EMPTY_COURT_ARC_KEY)

        self.assertEqual(lightness.status, "WORKING")
        self.assertEqual(empty_court.status, "WORKING")
        self.assertIn("quest_target_static", lightness.checked)
        self.assertIn("custom_actor_static", empty_court.checked)
        self.assertEqual(lightness.issues, [])
        self.assertEqual(empty_court.issues, [])

    def test_empty_court_preflight_tracks_every_custom_trial_actor(self) -> None:
        entries = _empty_court_custom_creature_entries()

        self.assertIn(915500, entries)
        self.assertIn(915510, entries)
        self.assertIn(915511, entries)
        self.assertIn(915512, entries)
        self.assertIn(915520, entries)
        self.assertIn(915530, entries)
        self.assertIn(915539, entries)
        self.assertIn(915540, entries)
        self.assertEqual(len(entries), 16)

    def test_preflight_rejects_unknown_arc(self) -> None:
        report = preflight_arc(arc_key="unknown_arc")

        self.assertEqual(report.status, "UNKNOWN")
        self.assertEqual(report.issues[0].code, "unknown_arc")

    def test_shell_audit_accepts_fixed_broug_self_cast_and_manual(self) -> None:
        report = audit_spell_shells(spell_ids=[946621, 946803])

        self.assertEqual(report.status, "WORKING")
        self.assertEqual([result.spell_id for result in report.spell_results], [946621, 946803])
        self.assertTrue(all(result.status == "WORKING" for result in report.spell_results))

    def test_shell_audit_catches_self_cast_range_leak(self) -> None:
        raw = json.loads(default_shell_bank_path().read_text(encoding="utf-8"))
        for shell in raw["shells"]:
            if shell["spell_id"] == 946621:
                shell["client_presentation"]["range_index"] = 4
                break
        with tempfile.TemporaryDirectory() as temp_dir:
            bank_path = Path(temp_dir) / "spell_shell_bank.json"
            bank_path.write_text(json.dumps(raw), encoding="utf-8")

            report = audit_spell_shells(spell_ids=[946621], shell_bank_path=bank_path)

        self.assertEqual(report.status, "BROKEN")
        issues = [issue.code for issue in report.spell_results[0].issues]
        self.assertIn("self_cast_range_not_self", issues)

    def test_release_gate_plans_all_current_broug_checks_before_mutations(self) -> None:
        plan = build_release_gate_plan(arc_key="broug_all_current", include_native_build=False)

        self.assertEqual(plan.status, "WORKING")
        keys = [step.key for step in plan.steps]
        self.assertEqual(keys[0], "focused_tests")
        self.assertIn(f"content_preflight:{BROUG_LIGHTNESS_ARC_KEY}", keys)
        self.assertIn(f"content_preflight:{BROUG_EMPTY_COURT_ARC_KEY}", keys)
        self.assertLess(keys.index(f"content_preflight:{BROUG_EMPTY_COURT_ARC_KEY}"), keys.index("world_sql_apply"))
        self.assertIn(r"D:\WOW\WM_BridgeLab\deps\mysql\bin\mysql.exe", plan.steps[keys.index("world_sql_apply")].command[0])

    def test_live_proof_packets_name_player_actions_and_counters(self) -> None:
        lightness = build_proof_packet(arc_key=BROUG_LIGHTNESS_ARC_KEY)
        empty_court = build_proof_packet(arc_key=BROUG_EMPTY_COURT_ARC_KEY)

        self.assertEqual(lightness.status, "WORKING")
        self.assertEqual(empty_court.status, "WORKING")
        self.assertTrue(any("Cloud Step" in step.instruction for step in lightness.steps))
        self.assertTrue(any("Qi Reversal" in step.instruction for step in empty_court.steps))
        self.assertIn("wm_broug_lightness_counter:cloud_step_strike", lightness.counters)
        self.assertIn("wm_broug_empty_court_counter:domain_pulse", empty_court.counters)

    def test_arc_scaffold_lists_standard_files_and_gates(self) -> None:
        plan = build_scaffold_plan(arc_key="broug_future_arc_v3")

        self.assertEqual(plan.status, "WORKING")
        paths = [file.path for file in plan.files]
        self.assertIn("src/wm/spells/broug_future_arc_v3.py", paths)
        self.assertTrue(any("wm.content.preflight" in gate for gate in plan.required_gates))
        self.assertTrue(any("wm.bridge_lab.release_gate" in gate for gate in plan.required_gates))


if __name__ == "__main__":
    unittest.main()
