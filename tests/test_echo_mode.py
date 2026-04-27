import unittest

from wm.spells.echo_mode import ECHO_MODE_BEHAVIOR_KIND, normalize_echo_mode, normalize_hunt_radius, submit_echo_mode


class FakeMysqlClient:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def query(self, **kwargs):
        sql = kwargs["sql"]
        self.queries.append(sql)
        if "LAST_INSERT_ID()" in sql:
            return [{"RequestID": "77"}]
        if "WHERE RequestID = 77" in sql:
            return [
                {
                    "RequestID": "77",
                    "PlayerGUID": "5406",
                    "BehaviorKind": ECHO_MODE_BEHAVIOR_KIND,
                    "PayloadJSON": '{"mode": "hunt"}',
                    "Status": "done",
                    "ResultJSON": '{"ok": true, "message": "bonebound_echo_mode_hunt"}',
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


class EchoModeTests(unittest.TestCase):
    def test_normalize_aliases(self) -> None:
        self.assertEqual(normalize_echo_mode("seek"), "hunt")
        self.assertEqual(normalize_echo_mode("AGGRESSIVE"), "hunt")
        self.assertEqual(normalize_echo_mode("guard"), "follow")
        self.assertEqual(normalize_echo_mode("follow"), "follow")
        self.assertEqual(normalize_echo_mode("tp"), "teleport")
        self.assertEqual(normalize_echo_mode("recall"), "teleport")
        self.assertEqual(normalize_echo_mode("teleport"), "teleport")
        with self.assertRaises(ValueError):
            normalize_echo_mode("explode")

    def test_normalize_hunt_radius_clamps_operator_input(self) -> None:
        self.assertEqual(normalize_hunt_radius(None), None)
        self.assertEqual(normalize_hunt_radius(1), 5.0)
        self.assertEqual(normalize_hunt_radius(150), 100.0)
        self.assertEqual(normalize_hunt_radius("42.5"), 42.5)
        with self.assertRaises(ValueError):
            normalize_hunt_radius(0)

    def test_submit_hunt_mode_uses_debug_request_contract(self) -> None:
        client = FakeMysqlClient()

        result = submit_echo_mode(
            client=client,  # type: ignore[arg-type]
            settings=SettingsStub(),  # type: ignore[arg-type]
            player_guid=5406,
            echo_mode="seek",
            mode="apply",
            wait=True,
        )

        self.assertTrue(result.ok)
        self.assertTrue(result.executed)
        self.assertEqual(result.request_id, 77)
        self.assertEqual(result.status, "done")
        self.assertEqual(result.echo_mode, "hunt")
        self.assertIn("INSERT INTO wm_spell_debug_request", client.queries[0])
        self.assertIn(ECHO_MODE_BEHAVIOR_KIND, client.queries[0])
        self.assertIn('"mode": "hunt"', client.queries[0])

    def test_submit_hunt_mode_can_set_seek_radius(self) -> None:
        client = FakeMysqlClient()

        result = submit_echo_mode(
            client=client,  # type: ignore[arg-type]
            settings=SettingsStub(),  # type: ignore[arg-type]
            player_guid=5406,
            echo_mode="seek",
            hunt_radius=150,
            mode="apply",
            wait=True,
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.hunt_radius, 100.0)
        self.assertIn('"hunt_radius": 100.0', client.queries[0])

    def test_dry_run_does_not_touch_db(self) -> None:
        client = FakeMysqlClient()

        result = submit_echo_mode(
            client=client,  # type: ignore[arg-type]
            settings=SettingsStub(),  # type: ignore[arg-type]
            player_guid=5406,
            echo_mode="follow",
            mode="dry-run",
        )

        self.assertTrue(result.ok)
        self.assertFalse(result.executed)
        self.assertEqual(result.status, "dry_run")
        self.assertEqual(client.queries, [])

    def test_submit_teleport_uses_echo_mode_contract(self) -> None:
        client = FakeMysqlClient()

        result = submit_echo_mode(
            client=client,  # type: ignore[arg-type]
            settings=SettingsStub(),  # type: ignore[arg-type]
            player_guid=5406,
            echo_mode="recall",
            mode="dry-run",
        )

        self.assertTrue(result.ok)
        self.assertFalse(result.executed)
        self.assertEqual(result.echo_mode, "teleport")
        self.assertEqual(result.hunt_radius, None)
        self.assertEqual(client.queries, [])


if __name__ == "__main__":
    unittest.main()
