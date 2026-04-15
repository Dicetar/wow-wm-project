import tempfile
import unittest
from pathlib import Path

from wm.spells.configure import parse_wm_spells_runtime_config
from wm.spells.configure import update_wm_spells_runtime_config
from wm.spells.platform import create_shell_draft
from wm.spells.platform import load_shell_draft
from wm.spells.platform import write_shell_draft_file


class WmSpellsConfigureTests(unittest.TestCase):
    def test_update_runtime_config_plans_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp).joinpath("mod_wm_spells.conf")
            config_path.write_text(
                "\n".join(
                    [
                        "[worldserver]",
                        "WmSpells.Enable = 0",
                        'WmSpells.PlayerGuidAllowList = "1234"',
                        "WmSpells.LabOnlyDebugInvokeEnable = 0",
                        "WmSpells.DebugPollIntervalMs = 1000",
                        "WmSpells.BoneboundServant.Enable = 0",
                        'WmSpells.BoneboundServant.ShellSpellIds = "940000"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            result = update_wm_spells_runtime_config(
                config_path=config_path,
                player_guids=[5406],
                shell_spell_ids=[940001],
                append_players=True,
                write=False,
                enable_debug_invoke=True,
                debug_poll_interval_ms=50,
            )

            self.assertTrue(result.changed)
            self.assertEqual(result.previous_allowlist, [1234])
            self.assertEqual(result.new_allowlist, [1234, 5406])
            self.assertEqual(result.previous_shell_spell_ids, [940000])
            self.assertEqual(result.new_shell_spell_ids, [940000, 940001])
            self.assertEqual(result.debug_poll_interval_ms, 50)
            snapshot = parse_wm_spells_runtime_config(config_path.read_text(encoding="utf-8"))
            self.assertFalse(snapshot.enabled)
            self.assertEqual(snapshot.debug_poll_interval_ms, 1000)
            self.assertEqual(snapshot.player_guid_allowlist, [1234])


class SpellPlatformDraftTests(unittest.TestCase):
    def test_create_shell_draft_uses_bank_metadata(self) -> None:
        draft = create_shell_draft(shell_key="bonebound_servant_v1", player_guid=5406)

        self.assertEqual(draft.spell_id, 940000)
        self.assertEqual(draft.family_id, "summon_pet")
        self.assertEqual(draft.behavior_kind, "summon_bonebound_servant_v1")
        self.assertTrue(draft.behavior_config["require_corpse"])
        self.assertEqual(draft.behavior_config["creature_entry"], 1860)

    def test_shell_draft_round_trips_via_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            draft = create_shell_draft(shell_key="bonebound_servant_v1", player_guid=5406)
            path = write_shell_draft_file(draft=draft, out_path=Path(tmp).joinpath("bonebound.json"))
            loaded = load_shell_draft(path)

            self.assertEqual(loaded.shell_key, draft.shell_key)
            self.assertEqual(loaded.spell_id, draft.spell_id)
            self.assertEqual(loaded.behavior_kind, draft.behavior_kind)

    def test_twin_shell_draft_uses_dual_summon_defaults(self) -> None:
        draft = create_shell_draft(shell_key="bonebound_twins_v1", player_guid=5406)

        self.assertEqual(draft.spell_id, 940001)
        self.assertEqual(draft.behavior_kind, "summon_bonebound_twin_v2")
        self.assertFalse(draft.behavior_config["require_corpse"])
        self.assertTrue(draft.behavior_config["spawn_omega"])
        self.assertTrue(draft.behavior_config["owner_intellect_to_all_stats"])
        self.assertEqual(draft.behavior_config["owner_intellect_to_all_stats_scale"], 1.0)
        self.assertTrue(draft.behavior_config["owner_shadow_power_to_attack_power"])
        self.assertEqual(draft.behavior_config["owner_shadow_power_to_attack_power_scale"], 1.0)
        self.assertEqual(draft.behavior_config["omega_name"], "Bonebound Omega")


if __name__ == "__main__":
    unittest.main()
