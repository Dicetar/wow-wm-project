from types import SimpleNamespace
import unittest

from wm.events.models import WMEvent
from wm.events.template_watch import SubjectMatchRule, subject_matches_template


class TemplateWatchTests(unittest.TestCase):
    def test_subject_match_accepts_westfall_murloc(self) -> None:
        matcher = SubjectMatchRule(faction_labels=["Murloc"], zone_ids=[40])
        event = WMEvent(
            event_class="observed",
            event_type="kill",
            source="test",
            source_event_key="kill:1",
            player_guid=5406,
            subject_type="creature",
            subject_entry=46,
            zone_id=40,
        )
        target_result = SimpleNamespace(
            entry=46,
            name="Murloc Forager",
            profile=SimpleNamespace(
                faction_label="Murloc",
                mechanical_type="HUMANOID",
                family=None,
            ),
        )

        self.assertTrue(subject_matches_template(matcher, event=event, target_result=target_result))

    def test_subject_match_rejects_wrong_zone(self) -> None:
        matcher = SubjectMatchRule(faction_labels=["Murloc"], zone_ids=[40])
        event = WMEvent(
            event_class="observed",
            event_type="kill",
            source="test",
            source_event_key="kill:2",
            player_guid=5406,
            subject_type="creature",
            subject_entry=46,
            zone_id=12,
        )
        target_result = SimpleNamespace(
            entry=46,
            name="Murloc Forager",
            profile=SimpleNamespace(
                faction_label="Murloc",
                mechanical_type="HUMANOID",
                family=None,
            ),
        )

        self.assertFalse(subject_matches_template(matcher, event=event, target_result=target_result))


if __name__ == "__main__":
    unittest.main()
