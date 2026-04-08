import importlib
from pathlib import Path
import unittest

from wm.events.models import LocationRef
from wm.events.models import ReactionCooldownKey
from wm.events.models import WMEvent


class EventModelTests(unittest.TestCase):
    def test_cooldown_key_is_stable(self) -> None:
        key = ReactionCooldownKey(
            rule_type="repeat_hunt_followup",
            player_guid=42,
            subject_type="creature",
            subject_entry=299,
        )
        self.assertEqual(key.to_reaction_key(), "repeat_hunt_followup:42:creature:299")

    def test_event_exposes_subject_and_location_views(self) -> None:
        event = WMEvent(
            event_class="observed",
            event_type="kill",
            source="db_poll",
            source_event_key="101",
            player_guid=7,
            subject_type="creature",
            subject_entry=46,
            map_id=0,
            zone_id=12,
            area_id=87,
        )
        self.assertEqual(event.subject.subject_type, "creature")
        self.assertEqual(event.subject.subject_entry, 46)
        self.assertEqual(event.location, LocationRef(map_id=0, zone_id=12, area_id=87))

    def test_quest_publish_import_resolves_to_package(self) -> None:
        module = importlib.import_module("wm.quests.publish")
        module_path = Path(module.__file__)
        self.assertEqual(module_path.name, "__init__.py")
        self.assertEqual(module_path.parent.name, "publish")


if __name__ == "__main__":
    unittest.main()
