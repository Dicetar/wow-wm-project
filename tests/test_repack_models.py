import unittest

from wm.repack.models import BuildTooling
from wm.repack.models import CoreTarget
from wm.repack.models import LiveRepackManifest
from wm.repack.models import RepackSourceGap
from wm.repack.models import RuntimeLayout


class RepackModelTests(unittest.TestCase):
    def test_gap_report_lists_unresolved_entries(self) -> None:
        manifest = LiveRepackManifest(
            generated_at_utc="2026-04-08T19:00:00+00:00",
            core=CoreTarget(
                repo_url="https://github.com/mod-playerbots/azerothcore-wotlk.git",
                branch="Playerbot",
                commit="946f88d981c5",
                version_string="AzerothCore rev. 946f88d981c5+",
            ),
            runtime_layout=RuntimeLayout(
                repack_root="D:/WOW/Azerothcore_WoTLK_Repack",
                config_root="D:/WOW/Azerothcore_WoTLK_Repack/configs",
                module_config_root="D:/WOW/Azerothcore_WoTLK_Repack/configs/modules",
                source_hint_root="D:/WOW/Azerothcore_WoTLK_Repack/source/azerothcore/modules",
                data_dir="D:/WOW/Azerothcore_WoTLK_Repack/data",
                logs_dir="D:/WOW/Azerothcore_WoTLK_Repack/logs",
                mysql_root="D:/WOW/Azerothcore_WoTLK_Repack/mysql",
                optional_sql_dir="D:/WOW/Azerothcore_WoTLK_Repack/optional",
                worldserver_conf_source_directory="source/azerothCore",
            ),
            build_tooling=BuildTooling(git_path="git", cmake_path="cmake", msbuild_path="msbuild"),
            source_gaps=[
                RepackSourceGap(
                    category="module",
                    name="mod-dungeon-master",
                    impact="build",
                    reason="No fully verified source mapping is pinned yet.",
                )
            ],
        )

        report = manifest.render_gap_report()

        self.assertIn("mod-dungeon-master", report)
        self.assertIn("946f88d981c5", report)


if __name__ == "__main__":
    unittest.main()
