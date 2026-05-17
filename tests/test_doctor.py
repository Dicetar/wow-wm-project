from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliError
from wm.doctor import FAIL, UNKNOWN, WORKING, run_doctor


class _FakeDb:
    """Stands in for MysqlCliClient with no real mysql process."""

    def __init__(self, *, reachable: bool = True, world_tables=None, char_tables=None):
        self.reachable = reachable
        self.world_tables = world_tables
        self.char_tables = char_tables
        self.mysql_bin_path = "fake-mysql"

    def query(self, *, host, port, user, password, database, sql):
        if not self.reachable:
            raise MysqlCliError("connection refused")
        if sql.startswith("SELECT 1"):
            return [{"ok": "1"}]
        if sql.startswith("SHOW TABLES"):
            tables = self.world_tables if "world" in database else self.char_tables
            return [{"t": name} for name in (tables or [])]
        return []


def _settings(tmp: Path, *, soap_enabled: bool = False) -> Settings:
    s = Settings()
    s.soap_enabled = soap_enabled
    s.world_db_name = "acore_world"
    s.char_db_name = "acore_characters"
    s.wm_bridge_config_path = str(tmp / "missing_bridge.conf")
    s.control_root = str(tmp / "control")
    (tmp / "control").mkdir(parents=True, exist_ok=True)
    (tmp / "control" / "registry.json").write_text("{}", encoding="utf-8")
    return s


def _by_name(results):
    return {r.name: r for r in results}


class DoctorTests(unittest.TestCase):
    def test_all_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            db = _FakeDb(
                world_tables=["wm_event_log", "wm_control_proposal", "wm_reserved_slot", "wm_publish_log"],
                char_tables=["wm_character_arc_state", "wm_character_reward_instance"],
            )
            results = run_doctor(_settings(tmp), db_client=db)
            by = _by_name(results)
            self.assertEqual(by["world_db"].status, WORKING)
            self.assertEqual(by["world_db.wm_tables"].status, WORKING)
            self.assertEqual(by["char_db.wm_tables"].status, WORKING)
            self.assertEqual(by["control_registry"].status, WORKING)
            # SOAP off and bridge config absent are UNKNOWN, never FAIL.
            self.assertEqual(by["soap"].status, UNKNOWN)
            self.assertEqual(by["native_bridge"].status, UNKNOWN)
            self.assertFalse(any(r.status == FAIL for r in results))

    def test_db_unreachable_is_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            results = run_doctor(_settings(Path(d)), db_client=_FakeDb(reachable=False))
            by = _by_name(results)
            self.assertEqual(by["world_db"].status, FAIL)
            self.assertEqual(by["char_db"].status, FAIL)

    def test_missing_bootstrap_tables_is_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            db = _FakeDb(world_tables=["wm_event_log"], char_tables=[])
            results = run_doctor(_settings(Path(d)), db_client=db)
            by = _by_name(results)
            self.assertEqual(by["world_db.wm_tables"].status, FAIL)
            self.assertIn("wm_control_proposal", by["world_db.wm_tables"].detail)

    def test_missing_control_registry_is_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            s = _settings(tmp)
            (tmp / "control" / "registry.json").unlink()
            results = run_doctor(s, db_client=_FakeDb(world_tables=[], char_tables=[]))
            self.assertEqual(_by_name(results)["control_registry"].status, FAIL)

    def test_no_mysql_client_degrades_to_unknown_not_crash(self) -> None:
        # db_client=None with no mysql binary: mysql_bin FAILs, db checks UNKNOWN.
        with tempfile.TemporaryDirectory() as d:
            s = _settings(Path(d))
            results = run_doctor(s)  # real discovery; CI has no acore mysql
            by = _by_name(results)
            self.assertIn(by["mysql_bin"].status, {WORKING, FAIL})
            if by["mysql_bin"].status == FAIL:
                self.assertEqual(by["world_db"].status, UNKNOWN)

    def test_json_serializable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            results = run_doctor(_settings(Path(d)), db_client=_FakeDb(world_tables=[], char_tables=[]))
            json.dumps([r.to_dict() for r in results])


if __name__ == "__main__":
    unittest.main()
