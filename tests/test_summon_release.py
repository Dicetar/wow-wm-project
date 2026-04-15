import unittest

from wm.spells.platform import SpellBehaviorDebugClient
from wm.spells.summon_release import submit_release_summon


class FakeMysqlClient:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def query(self, **kwargs):
        sql = kwargs["sql"]
        self.queries.append(sql)
        if "LAST_INSERT_ID()" in sql:
            return [{"RequestID": "42"}]
        if "WHERE RequestID = 42" in sql:
            return [
                {
                    "RequestID": "42",
                    "PlayerGUID": "5406",
                    "BehaviorKind": "summon_bonebound_alpha_v3",
                    "PayloadJSON": '{"shell_spell_id": 940001}',
                    "Status": "done",
                    "ResultJSON": '{"ok": true}',
                    "ErrorText": None,
                }
            ]
        raise AssertionError(f"Unexpected query: {sql}")


class SettingsStub:
    world_db_host = "127.0.0.1"
    world_db_port = 33307
    world_db_user = "acore"
    world_db_password = "acore"
    world_db_name = "acore_world"
    native_bridge_action_wait_seconds = 5.0
    native_bridge_action_poll_seconds = 0.25


class ReleaseSummonTests(unittest.TestCase):
    def test_submit_fast_inserts_without_loading_request(self) -> None:
        client = FakeMysqlClient()
        debug_client = SpellBehaviorDebugClient(client=client, settings=SettingsStub())  # type: ignore[arg-type]

        request_id = debug_client.submit_fast(
            player_guid=5406,
            behavior_kind="summon_bonebound_alpha_v3",
            payload={"shell_spell_id": 940001},
        )

        self.assertEqual(request_id, 42)
        self.assertEqual(len(client.queries), 1)
        self.assertIn("INSERT INTO wm_spell_debug_request", client.queries[0])
        self.assertNotIn("SELECT RequestID, PlayerGUID", client.queries[0])

    def test_release_summon_submit_only_does_not_wait_or_preflight(self) -> None:
        client = FakeMysqlClient()

        result = submit_release_summon(
            client=client,  # type: ignore[arg-type]
            settings=SettingsStub(),  # type: ignore[arg-type]
            player_guid=5406,
            mode="apply",
        )

        self.assertTrue(result.ok)
        self.assertTrue(result.executed)
        self.assertEqual(result.request_id, 42)
        self.assertEqual(result.status, "pending")
        self.assertEqual(result.shell_spell_id, 940001)
        self.assertEqual(len(client.queries), 1)
        self.assertIn("no_preflight=true", result.notes or [])
        self.assertIn("submit_only=true", result.notes or [])

    def test_release_summon_dry_run_does_not_touch_db(self) -> None:
        client = FakeMysqlClient()

        result = submit_release_summon(
            client=client,  # type: ignore[arg-type]
            settings=SettingsStub(),  # type: ignore[arg-type]
            player_guid=5406,
            mode="dry-run",
        )

        self.assertTrue(result.ok)
        self.assertFalse(result.executed)
        self.assertEqual(result.status, "dry_run")
        self.assertEqual(client.queries, [])


if __name__ == "__main__":
    unittest.main()
