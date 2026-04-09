from __future__ import annotations

import unittest
from pathlib import Path

from wm.config import Settings
from wm.sources.addon_log.arm import arm_addon_log_cursor


class _FakeStore:
    def __init__(self, existing_cursor=None) -> None:
        self.existing_cursor = existing_cursor
        self.saved = None

    def get_cursor(self, *, adapter_name: str, cursor_key: str = "state"):
        del adapter_name, cursor_key
        return self.existing_cursor

    def set_cursor(self, *, adapter_name: str, cursor_key: str = "state", cursor_value: str) -> None:
        self.saved = (adapter_name, cursor_key, cursor_value)


class AddonLogArmTests(unittest.TestCase):
    def test_arm_moves_cursor_to_end_of_existing_file(self) -> None:
        base = Path("artifacts") / "test_tmp" / "addon_log_arm"
        base.mkdir(parents=True, exist_ok=True)
        path = base / "WMOps_existing.log"
        path.write_text(
            "noise WMB1|type=HELLO|player=Jecia|player_guid=5406|channel=WMBridgePrivate|ts=1712600000123\n",
            encoding="utf-8",
        )
        store = _FakeStore()
        settings = Settings(addon_log_path=str(path))

        result = arm_addon_log_cursor(settings=settings, store=store)  # type: ignore[arg-type]

        self.assertTrue(result.file_exists)
        self.assertEqual(result.armed_offset, path.stat().st_size)
        self.assertIsNotNone(store.saved)

    def test_arm_handles_missing_file(self) -> None:
        base = Path("artifacts") / "test_tmp" / "addon_log_arm"
        base.mkdir(parents=True, exist_ok=True)
        path = base / "WMOps_missing.log"
        if path.exists():
            path.unlink()
        store = _FakeStore()
        settings = Settings(addon_log_path=str(path))

        result = arm_addon_log_cursor(settings=settings, store=store)  # type: ignore[arg-type]

        self.assertFalse(result.file_exists)
        self.assertEqual(result.armed_offset, 0)
        self.assertIsNotNone(store.saved)


if __name__ == "__main__":
    unittest.main()
