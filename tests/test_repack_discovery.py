from pathlib import Path
import shutil
import unittest

from wm.repack.discovery import export_live_repack_manifest


class _FakeMysqlClient:
    def query(self, *, host: str, port: int, user: str, password: str, database: str, sql: str):
        del host, port, user, password
        if database == "acore_world" and "FROM version" in sql:
            return [
                {
                    "core_version": "AzerothCore rev. 946f88d981c5+ test",
                    "core_revision": "946f88d981c5+",
                }
            ]
        if "FROM updates WHERE state='MODULE'" in sql:
            if database == "acore_world":
                return [{"name": "cs_individualProgression.sql"}, {"name": "dm_setup.sql"}]
            return []
        if "FROM updates WHERE state='CUSTOM'" in sql:
            if database == "acore_characters":
                return [{"name": "dm_characters_setup.sql"}]
            return []
        raise AssertionError(f"Unexpected SQL for {database}: {sql}")


class RepackDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        base_tmp = Path.cwd() / "data" / "test_tmp"
        base_tmp.mkdir(parents=True, exist_ok=True)
        self.root = base_tmp / "repack_discovery_case"
        if self.root.exists():
            shutil.rmtree(self.root)
        self.root.mkdir(parents=True)
        (self.root / "configs" / "modules").mkdir(parents=True)
        (self.root / "logs").mkdir(parents=True)
        (self.root / "optional").mkdir(parents=True)
        (self.root / "source" / "azerothcore" / "modules" / "mod-playerbots").mkdir(parents=True)

        (self.root / "configs" / "worldserver.conf").write_text(
            "\n".join(
                [
                    'LoginDatabaseInfo = "127.0.0.1;3306;acore;secret;acore_auth"',
                    'WorldDatabaseInfo = "127.0.0.1;3306;acore;secret;acore_world"',
                    'CharacterDatabaseInfo = "127.0.0.1;3306;acore;secret;acore_characters"',
                    'DataDir = "data"',
                    'LogsDir = "logs"',
                    'SourceDirectory = "source/azerothCore"',
                ]
            ),
            encoding="utf-8",
        )
        (self.root / "configs" / "authserver.conf").write_text(
            'LoginDatabaseInfo = "127.0.0.1;3306;acore;secret;acore_auth"',
            encoding="utf-8",
        )
        (self.root / "configs" / "modules" / "playerbots.conf").write_text(
            "AiPlayerbot.Enable = 1\n",
            encoding="utf-8",
        )
        (self.root / "configs" / "modules" / "playerbots.conf.dist").write_text(
            "AiPlayerbot.Enable = 0\n",
            encoding="utf-8",
        )
        (self.root / "configs" / "modules" / "mod_dungeon_master.conf").write_text(
            "DungeonMaster.Enable = 1\n",
            encoding="utf-8",
        )
        (self.root / "configs" / "modules" / "mod_dungeon_master.conf.dist").write_text(
            "DungeonMaster.Enable = 0\n",
            encoding="utf-8",
        )
        (self.root / "logs" / "Server_2026-04-08_20_19_52.log").write_text(
            "\n".join(
                [
                    "Using modules configuration:",
                    "> playerbots.conf",
                    "> mod_dungeon_master.conf",
                    "Dungeon Master Module — Ready",
                    '> Config: Missing property DungeonMaster.Roguelike.Buff.1 in config file configs/worldserver.conf',
                ]
            ),
            encoding="utf-8",
        )
        (self.root / "optional" / "zz_optional_attunements.sql").write_text("-- optional", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.root)

    def test_export_live_manifest_uses_live_truth_inputs(self) -> None:
        manifest = export_live_repack_manifest(
            repack_root=self.root,
            mysql_client=_FakeMysqlClient(),  # type: ignore[arg-type]
        )

        self.assertEqual(manifest.core.commit, "946f88d981c5")
        self.assertEqual(manifest.databases[1].database, "acore_world")
        self.assertTrue(any(item.relative_path == "modules/playerbots.conf" for item in manifest.config_overlays))
        self.assertTrue(any(item.filename == "zz_optional_attunements.sql" for item in manifest.optional_sql))
        self.assertTrue(any(module.key == "mod-playerbots" and module.status == "verified" for module in manifest.modules))
        self.assertTrue(any(gap.name == "mod-dungeon-master" for gap in manifest.source_gaps))
        self.assertTrue(any("Missing property" in warning for warning in manifest.runtime_markers.missing_property_warnings))


if __name__ == "__main__":
    unittest.main()
