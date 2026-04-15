import tempfile
import unittest
from pathlib import Path

from wm.prototypes.configure import parse_prototype_runtime_config
from wm.prototypes.configure import update_twin_skeleton_config


class PrototypeConfigureTests(unittest.TestCase):
    def test_update_twin_skeleton_config_plans_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp).joinpath("mod_wm_prototypes.conf")
            config_path.write_text(
                "\n".join(
                    [
                        "[worldserver]",
                        "WmPrototypes.Enable = 0",
                        'WmPrototypes.PlayerGuidAllowList = "1234"',
                        "WmPrototypes.TwinSkeleton.Enable = 0",
                        'WmPrototypes.TwinSkeleton.ShellSpellIds = "940001"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            result = update_twin_skeleton_config(
                config_path=config_path,
                player_guids=[5406],
                shell_spell_ids=[940002],
                append_players=True,
                write=False,
            )

            self.assertTrue(result.changed)
            self.assertEqual(result.previous_allowlist, [1234])
            self.assertEqual(result.new_allowlist, [1234, 5406])
            self.assertEqual(result.new_shell_spell_ids, [940001, 940002])
            snapshot = parse_prototype_runtime_config(config_path.read_text(encoding="utf-8"))
            self.assertFalse(snapshot.enabled)
            self.assertEqual(snapshot.player_guid_allowlist, [1234])

    def test_update_twin_skeleton_config_writes_enabled_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp).joinpath("mod_wm_prototypes.conf")
            config_path.write_text("[worldserver]\n", encoding="utf-8")

            result = update_twin_skeleton_config(
                config_path=config_path,
                player_guids=[5406],
                shell_spell_ids=[940001],
                append_players=False,
                write=True,
            )

            self.assertTrue(result.changed)
            snapshot = parse_prototype_runtime_config(config_path.read_text(encoding="utf-8"))
            self.assertTrue(snapshot.enabled)
            self.assertTrue(snapshot.twin_skeleton_enabled)
            self.assertEqual(snapshot.player_guid_allowlist, [5406])
            self.assertEqual(snapshot.twin_skeleton_shell_spell_ids, [940001])


if __name__ == "__main__":
    unittest.main()
