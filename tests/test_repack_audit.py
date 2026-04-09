from pathlib import Path
import json
import shutil
import unittest

from wm.repack.audit_upgrade import _compare_config_dists


class RepackAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path.cwd() / "data" / "test_tmp" / "repack_audit_case"
        if self.root.exists():
            shutil.rmtree(self.root)
        (self.root / "env" / "dist" / "etc" / "modules").mkdir(parents=True)
        (self.root / "env" / "dist" / "etc" / "worldserver.conf.dist").write_text("", encoding="utf-8")
        (self.root / "env" / "dist" / "etc" / "modules" / "playerbots.conf.dist").write_text("", encoding="utf-8")

    def tearDown(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)

    def test_compare_config_dists_uses_env_dist_etc_layout(self) -> None:
        manifest = {
            "config_overlays": [
                {"dist_relative_path": "worldserver.conf.dist"},
                {"dist_relative_path": "modules/playerbots.conf.dist"},
                {"dist_relative_path": "modules/mod_dungeon_master.conf.dist"},
            ]
        }

        findings = _compare_config_dists(manifest, self.root)

        self.assertEqual(findings, ["Missing upstream dist for modules/mod_dungeon_master.conf.dist"])


if __name__ == "__main__":
    unittest.main()
