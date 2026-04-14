from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from wm.journal.inspect import _bundle_to_dict, _render_summary, main
from wm.journal.models import JournalCounters, JournalEvent, JournalSummary, SubjectCard
from wm.journal.reader import SubjectJournalBundle


class JournalInspectTests(unittest.TestCase):
    def test_bundle_to_dict_and_summary(self) -> None:
        bundle = _bundle()

        payload = _bundle_to_dict(
            bundle=bundle,
            player_guid=42,
            target_profile={"entry": 69, "name": "Timber Wolf"},
        )
        summary = _render_summary(payload)

        self.assertEqual(payload["status"], "WORKING")
        self.assertEqual(payload["subject_id"], 9001)
        self.assertEqual(payload["counters"]["kill_count"], 4)
        self.assertEqual(payload["events"][0]["event_type"], "note")
        self.assertIn("journal: player=42 target=69 | Timber Wolf", summary)
        self.assertIn("counters: kills=4", summary)

    def test_main_summary_uses_static_target_resolver_and_journal_reader(self) -> None:
        stdout = io.StringIO()
        with patch("wm.journal.inspect.MysqlCliClient", return_value=object()):
            with patch("wm.journal.inspect.load_subject_journal_for_creature", return_value=_bundle()):
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "--player-guid",
                            "42",
                            "--target-entry",
                            "69",
                            "--lookup-json",
                            "data/lookup/sample_creature_template_full.json",
                            "--summary",
                        ]
                    )

        self.assertEqual(exit_code, 0)
        text = stdout.getvalue()
        self.assertIn("journal: player=42 target=69 | Timber Wolf", text)
        self.assertIn("status: WORKING", text)

    def test_main_returns_2_for_unknown_static_target(self) -> None:
        stdout = io.StringIO()
        with patch("wm.journal.inspect.MysqlCliClient", return_value=object()):
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--player-guid",
                        "42",
                        "--target-entry",
                        "999999",
                        "--lookup-json",
                        "data/lookup/sample_creature_template_full.json",
                    ]
                )

        self.assertEqual(exit_code, 2)
        self.assertIn("journal_resolved=false", stdout.getvalue())


def _bundle() -> SubjectJournalBundle:
    subject = SubjectCard(subject_name="Timber Wolf", short_description="Local wolf.")
    counters = JournalCounters(kill_count=4)
    events = [JournalEvent(event_type="note", event_value="Seen near the road.")]
    summary = JournalSummary(
        title="Timber Wolf",
        description="Local wolf.",
        history_lines=["Player killed 4", "Seen near the road."],
        raw={"source": "test"},
    )
    return SubjectJournalBundle(
        subject_id=9001,
        subject_card=subject,
        counters=counters,
        events=events,
        summary=summary,
        source_flags=["subject_definition", "player_subject_journal", "player_subject_event"],
        status="WORKING",
    )


if __name__ == "__main__":
    unittest.main()
