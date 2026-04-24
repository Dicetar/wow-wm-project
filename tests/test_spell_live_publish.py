import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from wm.config import Settings
from wm.spells.live_publish import LiveSpellPublishResult, _render_summary, _sync_runtime, main
from wm.spells.publish import SpellPublishResult


class SpellLivePublishRuntimeTests(unittest.TestCase):
    def test_sync_runtime_apply_off_recommends_restart(self) -> None:
        result = _sync_runtime(
            settings=Settings(),
            mode="apply",
            runtime_sync_mode="off",
            soap_commands=[],
        )

        self.assertTrue(result.overall_ok)
        self.assertTrue(result.restart_recommended)
        self.assertFalse(result.enabled)

    def test_render_summary_shows_runtime_commands(self) -> None:
        summary = _render_summary(
            LiveSpellPublishResult(
                mode="apply",
                publish={
                    "applied": True,
                    "validation": {"ok": True, "issues": []},
                    "preflight": {"ok": True, "issues": []},
                },
                runtime_sync={
                    "enabled": True,
                    "protocol": "soap",
                    "overall_ok": True,
                    "commands": [{"ok": True, "command": ".reload spell_linked_spell", "result": "reloaded"}],
                    "note": "Spell rows were published.",
                },
                restart_recommended=True,
            )
        )

        self.assertIn("runtime_sync.protocol: soap", summary)
        self.assertIn(".reload spell_linked_spell", summary)
        self.assertIn("note: Spell rows were published.", summary)


class SpellLivePublishMainTests(unittest.TestCase):
    def test_main_apply_requires_publish_to_be_applied(self) -> None:
        publish_result = SpellPublishResult(
            mode="apply",
            draft={"spell_entry": 947000},
            validation={"ok": True, "issues": []},
            preflight={"ok": True, "issues": []},
            snapshot_preview={},
            sql_plan={},
            applied=False,
        )

        class FakePublisher:
            def __init__(self, **_kwargs) -> None:
                pass

            def publish(self, *, draft, mode):
                del draft, mode
                return publish_result

        original_settings = main.__globals__["Settings"]
        original_client = main.__globals__["MysqlCliClient"]
        original_publisher = main.__globals__["SpellPublisher"]
        original_sync = main.__globals__["_sync_runtime"]
        try:
            main.__globals__["Settings"] = type("SettingsStub", (), {"from_env": staticmethod(lambda: Settings())})
            main.__globals__["MysqlCliClient"] = lambda: object()
            main.__globals__["SpellPublisher"] = FakePublisher
            main.__globals__["_sync_runtime"] = lambda **_kwargs: type(
                "RuntimeSyncStub",
                (),
                {
                    "restart_recommended": False,
                    "overall_ok": True,
                    "to_dict": lambda self: {"enabled": False, "protocol": "none", "overall_ok": True, "commands": [], "note": None},
                },
            )()
            with redirect_stdout(io.StringIO()):
                exit_code = main(["--demo", "--mode", "apply", "--runtime-sync", "off", "--summary"])
        finally:
            main.__globals__["Settings"] = original_settings
            main.__globals__["MysqlCliClient"] = original_client
            main.__globals__["SpellPublisher"] = original_publisher
            main.__globals__["_sync_runtime"] = original_sync

        self.assertEqual(exit_code, 2)

    def test_main_writes_output_json(self) -> None:
        publish_result = SpellPublishResult(
            mode="dry-run",
            draft={"spell_entry": 947000},
            validation={"ok": True, "issues": []},
            preflight={"ok": True, "issues": []},
            snapshot_preview={"spell_proc": []},
            sql_plan={"statements": []},
            applied=False,
        )

        class FakePublisher:
            def __init__(self, **_kwargs) -> None:
                pass

            def publish(self, *, draft, mode):
                del draft, mode
                return publish_result

        original_settings = main.__globals__["Settings"]
        original_client = main.__globals__["MysqlCliClient"]
        original_publisher = main.__globals__["SpellPublisher"]
        original_sync = main.__globals__["_sync_runtime"]
        try:
            main.__globals__["Settings"] = type("SettingsStub", (), {"from_env": staticmethod(lambda: Settings())})
            main.__globals__["MysqlCliClient"] = lambda: object()
            main.__globals__["SpellPublisher"] = FakePublisher
            main.__globals__["_sync_runtime"] = lambda **_kwargs: type(
                "RuntimeSyncStub",
                (),
                {
                    "restart_recommended": False,
                    "overall_ok": True,
                    "to_dict": lambda self: {"enabled": False, "protocol": "none", "overall_ok": True, "commands": [], "note": None},
                },
            )()
            with tempfile.TemporaryDirectory() as tmp:
                output_path = Path(tmp).joinpath("spell_live_publish.json")
                with redirect_stdout(io.StringIO()):
                    exit_code = main(["--demo", "--mode", "dry-run", "--output-json", str(output_path)])
                payload = json.loads(output_path.read_text(encoding="utf-8"))
        finally:
            main.__globals__["Settings"] = original_settings
            main.__globals__["MysqlCliClient"] = original_client
            main.__globals__["SpellPublisher"] = original_publisher
            main.__globals__["_sync_runtime"] = original_sync

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["publish"]["draft"]["spell_entry"], 947000)
        self.assertEqual(payload["runtime_sync"]["protocol"], "none")


if __name__ == "__main__":
    unittest.main()
