import unittest

from wm.repack.catalog import ModuleCatalog


class RepackCatalogTests(unittest.TestCase):
    def test_playerbots_is_verified(self) -> None:
        catalog = ModuleCatalog()

        mapping = catalog.match_config_file("playerbots.conf")

        self.assertEqual(mapping.key, "mod-playerbots")
        self.assertEqual(mapping.status, "verified")
        self.assertIn("mod-playerbots", mapping.repo_url)

    def test_user_provided_repo_is_marked_verified(self) -> None:
        catalog = ModuleCatalog()

        mapping = catalog.match_config_file("mod_weather_vibe.conf")

        self.assertEqual(mapping.status, "verified")
        self.assertEqual(mapping.repo_url, "https://github.com/hermensbas/mod_weather_vibe.git")

    def test_runtime_noise_can_be_ignored(self) -> None:
        catalog = ModuleCatalog()

        mapping = catalog.match_config_file("Using configuration file       configs/worldserver.conf")

        self.assertEqual(mapping.status, "ignored")

    def test_dungeon_master_mapping_uses_recovered_repo(self) -> None:
        catalog = ModuleCatalog()

        mapping = catalog.match_config_file("mod_dungeon_master.conf")

        self.assertEqual(mapping.key, "mod-dungeon-master")
        self.assertEqual(mapping.status, "candidate")
        self.assertEqual(mapping.repo_url, "https://github.com/InstanceForge/mod-dungeon-master.git")

    def test_mythic_plus_mapping_uses_recovered_repo(self) -> None:
        catalog = ModuleCatalog()

        mapping = catalog.match_config_file("mod_mythic_plus.conf")

        self.assertEqual(mapping.key, "mod-mythic-plus")
        self.assertEqual(mapping.status, "candidate")
        self.assertEqual(mapping.repo_url, "https://github.com/silviu20092/mod-mythic-plus.git")

    def test_player_bot_reset_mapping_uses_recovered_repo(self) -> None:
        catalog = ModuleCatalog()

        mapping = catalog.match_config_file("mod_player_bot_reset.conf")

        self.assertEqual(mapping.key, "mod-player-bot-reset")
        self.assertEqual(mapping.status, "candidate")
        self.assertEqual(mapping.repo_url, "https://github.com/DustinHendrickson/mod-player-bot-reset.git")


if __name__ == "__main__":
    unittest.main()
