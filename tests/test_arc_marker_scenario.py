from __future__ import annotations

from datetime import datetime, timezone
import unittest

from wm.arcs.marker_scenario import MarkerArcScenarioGenerator
from wm.arcs.marker_scenario import MarkerScenarioError
from wm.config import Settings


class FakePanelState:
    def __init__(self, session=None) -> None:
        self.session = session

    def load_session(self):
        return self.session


class FakeClient:
    def __init__(self, *, online: bool = True, target_rows=None, turn_in_rows=None, race: int = 1) -> None:
        self.online = online
        self.target_rows = target_rows if target_rows is not None else [
            {
                "entry": "3100",
                "name": "Forest Gnoll",
                "minlevel": "14",
                "maxlevel": "15",
                "faction": "20",
                "type": "7",
                "rank": "0",
                "unit_class": "1",
                "spawn_count": "7",
                "map_id": "0",
                "zone_id": "40",
            }
        ]
        self.turn_in_rows = turn_in_rows if turn_in_rows is not None else [
            {
                "entry": "5234",
                "name": "Sentinel Hill Scout",
                "subname": "",
                "faction": "11",
                "faction_name": "Stormwind",
                "quest_starter_count": "4",
                "quest_ender_count": "2",
                "spawn_count": "3",
            }
        ]
        self.race = race
        self.queries: list[str] = []

    def query(self, *, host, port, user, password, database, sql):
        del host, port, user, password
        self.queries.append(sql)
        if database == "acore_characters" and "SELECT guid, name, race, class, level, map, zone, online" in sql:
            return [
                {
                    "guid": "7777",
                    "name": "Markerone",
                    "race": str(self.race),
                    "class": "1",
                    "level": "15",
                    "map": "0",
                    "zone": "40",
                    "online": "1" if self.online else "0",
                }
            ]
        if database == "acore_characters" and "SELECT race FROM characters" in sql:
            return [{"race": str(self.race)}]
        if database == "acore_world" and "FROM wm_bridge_player_presence" in sql:
            return [
                {
                    "PlayerGUID": "7777",
                    "Online": "1" if self.online else "0",
                    "MapID": "0",
                    "ZoneID": "40",
                    "AreaID": "108",
                    "ZoneName": "Westfall",
                    "AreaName": "Sentinel Hill",
                    "Level": "15",
                }
            ]
        if database == "acore_world" and "JOIN creature_template ct ON ct.entry = c.id1" in sql:
            return list(self.target_rows)
        if database == "acore_world" and "creature_queststarter" in sql and "quest_starter_count" in sql:
            return list(self.turn_in_rows)
        raise AssertionError(f"Unexpected SQL for {database}: {sql}")


def _settings() -> Settings:
    return Settings(world_db_port=33307, char_db_port=33307, soap_enabled=False)


class MarkerArcScenarioGeneratorTests(unittest.TestCase):
    def test_generates_zone_compatible_scenario_for_runtime_player(self) -> None:
        generator = MarkerArcScenarioGenerator(client=FakeClient(), settings=_settings())  # type: ignore[arg-type]

        payload = generator.generate(player_guid=7777)

        self.assertEqual(payload["schema_version"], "wm.arc_reward_factory.personal_arc.v1")
        self.assertEqual(payload["player_guid"], 7777)
        self.assertEqual(payload["target"]["creature_entry"], 3100)
        self.assertEqual(payload["target"]["target_name"], "Forest Gnoll")
        self.assertEqual(payload["turn_in_npc"]["entry"], 5234)
        self.assertEqual(payload["turn_in_npc"]["name"], "Sentinel Hill Scout")
        self.assertIn("Sentinel Hill", payload["summary"])
        self.assertNotEqual(payload["target"]["creature_entry"], 116)
        self.assertNotEqual(payload["turn_in_npc"]["entry"], 261)

    def test_resolves_active_marker_session_when_player_guid_is_omitted(self) -> None:
        session = {
            "source": "marker",
            "marker_spell_id": 946602,
            "character_guid": 7777,
            "character_name": "Markerone",
            "selected_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "marker": {"character_online": True},
            "bridge_event_id": 12345,
        }
        generator = MarkerArcScenarioGenerator(
            client=FakeClient(),  # type: ignore[arg-type]
            settings=_settings(),
            panel_state=FakePanelState(session),  # type: ignore[arg-type]
        )

        payload = generator.generate()

        self.assertEqual(payload["player_guid"], 7777)
        self.assertIn("marker_spell_id:946602", payload["notes"])

    def test_rejects_offline_runtime_player(self) -> None:
        generator = MarkerArcScenarioGenerator(client=FakeClient(online=False), settings=_settings())  # type: ignore[arg-type]

        with self.assertRaisesRegex(MarkerScenarioError, "not online"):
            generator.generate(player_guid=7777)

    def test_rejects_missing_zone_target_instead_of_fixture_fallback(self) -> None:
        generator = MarkerArcScenarioGenerator(
            client=FakeClient(target_rows=[]),  # type: ignore[arg-type]
            settings=_settings(),
        )

        with self.assertRaisesRegex(MarkerScenarioError, "no zone-compatible target"):
            generator.generate(player_guid=7777)

    def test_rejects_missing_questgiver_instead_of_fixture_fallback(self) -> None:
        generator = MarkerArcScenarioGenerator(
            client=FakeClient(turn_in_rows=[]),  # type: ignore[arg-type]
            settings=_settings(),
        )

        with self.assertRaisesRegex(MarkerScenarioError, "no faction-compatible questgiver"):
            generator.generate(player_guid=7777)


if __name__ == "__main__":
    unittest.main()
