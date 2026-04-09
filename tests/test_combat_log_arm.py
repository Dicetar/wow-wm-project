from __future__ import annotations

import unittest
from pathlib import Path

from wm.config import Settings
from wm.sources.combat_log.arm import arm_combat_log_cursor


class _FakeStore:
    def __init__(self, existing_cursor=None) -> None:
        self.existing_cursor = existing_cursor
        self.saved = None

    def get_cursor(self, *, adapter_name: str, cursor_key: str = "state"):
        del adapter_name, cursor_key
        return self.existing_cursor

    def set_cursor(self, *, adapter_name: str, cursor_key: str = "state", cursor_value: str) -> None:
        self.saved = (adapter_name, cursor_key, cursor_value)


class _Cursor:
    def __init__(self, cursor_value: str) -> None:
        self.cursor_value = cursor_value


class CombatLogArmTests(unittest.TestCase):
    def test_arm_moves_cursor_to_end_of_existing_file(self) -> None:
        base = Path("artifacts") / "test_tmp" / "combat_log_arm"
        base.mkdir(parents=True, exist_ok=True)
        path = base / "WoWCombatLog_existing.txt"
        content = "4/8 18:00:00.000  PARTY_KILL,0x1,\"Jecia\",0x511,0x2,\"Kobold Vermin\",0xa28\n"
        path.write_text(content, encoding="utf-8")
        store = _FakeStore()
        settings = Settings(combat_log_path=str(path))

        result = arm_combat_log_cursor(settings=settings, store=store)  # type: ignore[arg-type]

        self.assertTrue(result.file_exists)
        self.assertEqual(result.armed_offset, path.stat().st_size)
        self.assertIsNotNone(store.saved)

    def test_arm_handles_missing_file(self) -> None:
        base = Path("artifacts") / "test_tmp" / "combat_log_arm"
        base.mkdir(parents=True, exist_ok=True)
        path = base / "WoWCombatLog_missing.txt"
        if path.exists():
            path.unlink()
        store = _FakeStore()
        settings = Settings(combat_log_path=str(path))

        result = arm_combat_log_cursor(settings=settings, store=store)  # type: ignore[arg-type]

        self.assertFalse(result.file_exists)
        self.assertEqual(result.armed_offset, 0)
        self.assertIsNotNone(store.saved)


if __name__ == "__main__":
    unittest.main()
