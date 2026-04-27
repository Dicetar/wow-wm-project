from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from wm.character.models import (
    ArcState,
    CharacterProfile,
    CharacterUnlock,
    ConversationSteeringNote,
    PromptQueueEntry,
    RewardInstance,
)
from wm.character.reader import CharacterStateBundle
from wm.context.builder import ContextPackBuildError, ContextPackBuilder, main
from wm.db.mysql_cli import MysqlCliError
from wm.events.models import WMEvent
from wm.journal.models import JournalCounters, JournalEvent, JournalSummary, SubjectCard
from wm.journal.reader import SubjectJournalBundle
from wm.reactive.models import PlayerQuestRuntimeState, ReactiveQuestRule
from wm.targets.resolver import TargetProfile


class ContextPackBuilderTests(unittest.TestCase):
    def test_builds_context_pack_from_event_target_and_journal(self) -> None:
        profile = _murloc_profile()
        journal = _journal_bundle(status="WORKING", source_flags=["subject_definition", "player_subject_journal"])
        builder = ContextPackBuilder(
            target_resolver=_SingleTargetResolver(profile),
            journal_loader=_SingleJournalLoader(journal),
            character_loader=_CharacterLoader(),
            event_store=_EventStore(),
            reactive_store=_ReactiveStore(),
            control_registry=_ControlRegistry(),
            native_snapshot_loader=_NativeSnapshotLoader(),
        )
        event = WMEvent(
            event_id=12,
            event_class="observed",
            event_type="kill",
            source="native_bridge",
            source_event_key="bridge:12",
            occurred_at="2026-04-14 12:00:00",
            player_guid=5406,
            subject_type="creature",
            subject_entry=46,
        )

        pack = builder.build_for_target(player_guid=5406, target_entry=46, source_event=event)
        data = pack.to_dict()

        self.assertEqual(data["schema_version"], "wm.context_pack.v1")
        self.assertEqual(data["pack_id"], "context:5406:creature:46:native_bridge:bridge:12")
        self.assertEqual(data["status"], "WORKING")
        self.assertEqual(data["source_event"]["event_type"], "kill")
        self.assertEqual(data["target_profile"]["name"], "Murloc Forager")
        self.assertEqual(data["subject_card"]["display_name"], "Murloc Forager")
        self.assertEqual(data["journal_summary"]["title"], "Murloc Forager")
        self.assertEqual(data["journal_status"], "WORKING")
        self.assertEqual(data["journal_source_flags"], ["subject_definition", "player_subject_journal"])
        self.assertEqual(data["character_state"]["profile"]["character_name"], "Jecia")
        self.assertEqual(len(data["recent_events"]), 1)
        self.assertEqual(len(data["related_subject_events"]), 1)
        self.assertEqual(data["quest_runtime"]["active_rule_count"], 1)
        self.assertEqual(data["quest_runtime"]["active_rules"][0]["runtime_state"]["current_state"], "none")
        self.assertEqual(data["eligible_recipes"][0]["id"], "reactive_bounty")
        self.assertEqual(data["policy"]["id"], "direct_apply")
        self.assertEqual(data["native_context_snapshot"]["snapshot_id"], 91)
        self.assertEqual(data["generation_input"]["player"]["name"], "Jecia")
        self.assertEqual(data["generation_input"]["journey"]["active_arc_keys"], ["murloc"])
        self.assertEqual(data["generation_input"]["journey"]["unlock_refs"], ["spell:900001"])
        self.assertEqual(data["generation_input"]["journey"]["steering"][0]["key"], "visible_first")
        self.assertEqual(data["generation_input"]["quest_runtime"]["states"], ["none"])
        self.assertEqual(data["generation_input"]["eligible_recipe_ids"], ["reactive_bounty"])
        self.assertEqual(data["notes"], [])

    def test_builds_partial_pack_when_journal_uses_resolver_fallback(self) -> None:
        journal = _journal_bundle(status="PARTIAL", source_flags=["subject_resolver"])
        builder = ContextPackBuilder(
            target_resolver=_SingleTargetResolver(_murloc_profile()),
            journal_loader=_SingleJournalLoader(journal),
        )

        pack = builder.build_for_target(player_guid=5406, target_entry=46)

        self.assertEqual(pack.status, "PARTIAL")
        self.assertIn("journal: no active wm_subject_definition row was loaded", pack.notes[0])

    def test_minimal_builder_marks_missing_optional_sections_partial(self) -> None:
        journal = _journal_bundle(status="WORKING", source_flags=["subject_definition", "player_subject_journal"])
        builder = ContextPackBuilder(
            target_resolver=_SingleTargetResolver(_murloc_profile()),
            journal_loader=_SingleJournalLoader(journal),
        )

        pack = builder.build_for_target(player_guid=5406, target_entry=46)

        self.assertEqual(pack.status, "PARTIAL")
        self.assertTrue(any(note.startswith("character_state:") for note in pack.notes))
        self.assertTrue(any(note.startswith("recent_events:") for note in pack.notes))
        self.assertTrue(any(note.startswith("control:") for note in pack.notes))

    def test_missing_target_raises(self) -> None:
        builder = ContextPackBuilder(
            target_resolver=_SingleTargetResolver(None),
            journal_loader=_SingleJournalLoader(_journal_bundle()),
        )

        with self.assertRaises(ContextPackBuildError):
            builder.build_for_target(player_guid=5406, target_entry=999999)

    def test_cli_marks_unresolved_target_unknown_without_traceback(self) -> None:
        stdout = io.StringIO()
        with patch("wm.context.builder.MysqlCliClient", return_value=object()):
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--target-entry",
                        "999999",
                        "--player-guid",
                        "5406",
                        "--lookup-json",
                        "data/lookup/sample_creature_template_full.json",
                        "--summary",
                    ]
                )

        self.assertEqual(exit_code, 2)
        self.assertIn("status: UNKNOWN", stdout.getvalue())
        self.assertIn("could not be resolved", stdout.getvalue())

    def test_cli_marks_unloadable_event_unknown_without_traceback(self) -> None:
        stdout = io.StringIO()
        with patch("wm.context.builder.MysqlCliClient", return_value=_FailingMysqlClient()):
            with redirect_stdout(stdout):
                exit_code = main(["--event-id", "12", "--summary"])

        self.assertEqual(exit_code, 2)
        self.assertIn("status: UNKNOWN", stdout.getvalue())
        self.assertIn("WM event 12 could not be loaded", stdout.getvalue())


def _murloc_profile() -> TargetProfile:
    return TargetProfile(
        entry=46,
        name="Murloc Forager",
        subname=None,
        level_min=9,
        level_max=10,
        faction_id=18,
        faction_label="Murloc",
        mechanical_type="HUMANOID",
        family=None,
        rank="NORMAL",
        unit_class="WARRIOR",
        service_roles=[],
        has_gossip_menu=False,
    )


def _journal_bundle(
    *,
    status: str = "WORKING",
    source_flags: list[str] | None = None,
) -> SubjectJournalBundle:
    subject = SubjectCard(subject_name="Murloc Forager", short_description="Shoreline pest.")
    counters = JournalCounters(kill_count=3)
    events = [JournalEvent(event_type="note", event_value="Observed near the shore.")]
    summary = JournalSummary(
        title="Murloc Forager",
        description="Shoreline pest.",
        history_lines=["Player killed 3", "Observed near the shore."],
        raw={"source": "test"},
    )
    return SubjectJournalBundle(
        subject_id=77 if status == "WORKING" else None,
        subject_card=subject,
        counters=counters,
        events=events,
        summary=summary,
        source_flags=source_flags or ["subject_definition", "player_subject_journal", "player_subject_event"],
        status=status,
    )


class _SingleTargetResolver:
    def __init__(self, profile: TargetProfile | None) -> None:
        self.profile = profile

    def resolve_creature_entry(self, entry: int) -> TargetProfile | None:
        del entry
        return self.profile


class _SingleJournalLoader:
    def __init__(self, bundle: SubjectJournalBundle) -> None:
        self.bundle = bundle

    def load_for_creature(self, *, player_guid: int, creature_entry: int, resolved_subject_card=None):
        del player_guid, creature_entry, resolved_subject_card
        return self.bundle


class _CharacterLoader:
    def load(self, *, character_guid: int) -> CharacterStateBundle:
        return CharacterStateBundle(
            profile=CharacterProfile(character_guid=character_guid, character_name="Jecia", wm_persona="tester", tone="direct"),
            arc_states=[ArcState(character_guid=character_guid, arc_key="murloc", stage_key="seen")],
            unlocks=[CharacterUnlock(character_guid=character_guid, unlock_kind="spell", unlock_id=900001)],
            rewards=[RewardInstance(character_guid=character_guid, reward_kind="item", template_id=23192)],
            conversation_steering=[
                ConversationSteeringNote(
                    character_guid=character_guid,
                    steering_key="visible_first",
                    body="Prefer visible effects.",
                    priority=10,
                )
            ],
            prompt_queue=[PromptQueueEntry(character_guid=character_guid, prompt_kind="branch_choice", body="What next?")],
        )


class _EventStore:
    def list_recent_events(self, *, event_class=None, player_guid=None, limit=20, newest_first=True):
        del event_class, limit, newest_first
        return [
            WMEvent(
                event_id=10,
                event_class="observed",
                event_type="kill",
                source="native_bridge",
                source_event_key="bridge:10",
                player_guid=player_guid,
                subject_type="creature",
                subject_entry=46,
            )
        ]

    def list_subject_events(
        self,
        *,
        player_guid: int,
        subject_type: str,
        subject_entry: int,
        event_type=None,
        event_class="observed",
        limit=200,
        newest_first=False,
    ):
        del event_type, limit, newest_first
        return [
            WMEvent(
                event_id=11,
                event_class=event_class,
                event_type="kill",
                source="native_bridge",
                source_event_key="bridge:11",
                player_guid=player_guid,
                subject_type=subject_type,
                subject_entry=subject_entry,
            )
        ]


class _ReactiveStore:
    def list_active_rules(self, *, subject_type=None, subject_entry=None, trigger_event_type=None, player_guid=None):
        del subject_type, subject_entry, trigger_event_type, player_guid
        return [
            ReactiveQuestRule(
                rule_key="reactive_bounty:auto:murloc",
                is_active=True,
                player_guid_scope=5406,
                subject_type="creature",
                subject_entry=46,
                trigger_event_type="kill",
                kill_threshold=2,
                window_seconds=120,
                quest_id=910001,
                turn_in_npc_entry=240,
                grant_mode="direct_quest_add",
                post_reward_cooldown_seconds=60,
            )
        ]

    def get_player_quest_runtime_state(self, *, player_guid: int, quest_id: int):
        return PlayerQuestRuntimeState(player_guid=player_guid, quest_id=quest_id, current_state="none")

    def fetch_character_quest_status(self, *, player_guid: int, quest_id: int) -> str:
        del player_guid, quest_id
        return "none"


class _ControlRegistry:
    registry = {"default_policy": "direct_apply"}
    registry_hash = "registry-hash"
    schema_hash = "schema-hash"
    default_policy = {"mode": "manual_first"}

    def eligible_recipes_for_event_type(self, event_type: str):
        return [{"id": "reactive_bounty", "trigger_event_types": [event_type]}]


class _NativeSnapshotLoader:
    def load_latest(self, *, player_guid: int):
        return {
            "snapshot_id": 91,
            "player_guid": player_guid,
            "context_kind": "nearby",
            "payload": {"nearby": []},
        }


class _FailingMysqlClient:
    def query(self, **kwargs):
        del kwargs
        raise MysqlCliError("world db unavailable")


if __name__ == "__main__":
    unittest.main()
