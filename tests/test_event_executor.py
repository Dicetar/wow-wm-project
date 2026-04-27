import unittest
from pathlib import Path

from wm.config import Settings
from wm.events.executor import ReactionExecutor
from wm.events.models import PlannedAction
from wm.events.models import ReactionCooldownKey
from wm.events.models import ReactionPlan
from wm.events.models import SubjectRef
from wm.refs import CreatureRef
from wm.refs import NpcRef
from wm.refs import PlayerRef
from wm.refs import QuestRef


class _DummyClient:
    mysql_bin_path = "mysql"


class FakePublishResult:
    def __init__(self, *, mode: str) -> None:
        self.mode = mode
        self.applied = mode == "apply"

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "applied": self.applied,
            "validation": {"ok": True, "issues": []},
            "preflight": {
                "ok": False,
                "issues": [
                    {
                        "path": "reserved_slot.status",
                        "message": "Reserved slot for quest 910001 has status `free`; expected `staged` for fresh publish or `active` for already-published managed content.",
                        "severity": "error",
                    }
                ],
                "reserved_slot": {
                    "EntityType": "quest",
                    "ReservedID": "910001",
                    "SlotStatus": "free",
                    "ArcKey": None,
                    "CharacterGUID": None,
                    "SourceQuestID": None,
                    "NotesJSON": None,
                },
            },
        }


class FakePublisher:
    def __init__(self) -> None:
        self.calls: list[tuple[object, str]] = []

    def publish(self, *, draft, mode: str):
        self.calls.append((draft, mode))
        return FakePublishResult(mode=mode)


class FakeExecutionStore:
    def __init__(self) -> None:
        self.recorded_events = []
        self.logged_reactions = []
        self.cooldowns = []

    def record(self, events):
        self.recorded_events.extend(events)
        return None

    def log_reaction(self, *, plan, status: str, result: dict[str, object]) -> None:
        self.logged_reactions.append((plan, status, result))

    def set_cooldown(self, *, key, cooldown_seconds: int, metadata=None) -> None:
        self.cooldowns.append((key, cooldown_seconds, metadata))


class FakeSlotAllocator:
    def __init__(self) -> None:
        self.calls = []

    def ensure_slot_prepared(
        self,
        *,
        entity_type: str,
        reserved_id: int,
        arc_key: str | None = None,
        character_guid: int | None = None,
        source_quest_id: int | None = None,
        notes=None,
    ):
        self.calls.append((entity_type, reserved_id, arc_key, character_guid, source_quest_id, notes))
        return None


class FakeReactiveStore:
    def fetch_character_name(self, *, player_guid: int) -> str | None:
        return {42: "Qraag", 5406: "Qraaglock"}.get(player_guid)


class FakeQuestRuntimeManager:
    def __init__(self) -> None:
        self.preview_calls: list[tuple[int, str | None, int]] = []
        self.grant_calls: list[tuple[int, str | None, int]] = []

    def preview_grant(self, *, player_guid: int, player_name: str | None, quest_id: int):
        self.preview_calls.append((player_guid, player_name, quest_id))
        class Preview:
            ok = True
            def to_dict(self_nonlocal):
                return {
                    "ok": True,
                    "player_guid": player_guid,
                    "player_name": player_name,
                    "quest_id": quest_id,
                    "command_preview": f".quest add {quest_id} {player_name}",
                    "issues": [],
                    "notes": [],
                }
        return Preview()

    def grant_quest(self, *, player_guid: int, player_name: str | None, quest_id: int):
        self.grant_calls.append((player_guid, player_name, quest_id))
        class Result:
            ok = True
            def to_dict(self_nonlocal):
                return {
                    "command": f".quest add {quest_id} {player_name}",
                    "ok": True,
                    "result": "Quest added.",
                    "fault_code": None,
                    "fault_string": None,
                }
        return Result()


class FakeNativeRequest:
    def __init__(self, *, request_id: int, status: str = "done") -> None:
        self.request_id = request_id
        self.status = status

    def to_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "status": self.status,
            "error_text": None,
            "result": {"ok": self.status == "done", "message": "quest_added"},
        }


class FakeNativeBridgeActions:
    def __init__(self) -> None:
        self.submissions = []

    def is_player_scoped(self, *, player_guid: int, profile: str = "default") -> bool:
        return player_guid == 5406 and profile == "default"

    def get_action_policy(self, *, action_kind: str, profile: str = "default") -> dict[str, object] | None:
        if action_kind != "quest_add" or profile != "default":
            return None
        return {
            "action_kind": "quest_add",
            "profile": "default",
            "enabled": True,
            "max_risk_level": "medium",
            "cooldown_ms": 1000,
            "burst_limit": 5,
            "admin_only": False,
        }

    def submit(self, **kwargs):  # type: ignore[no-untyped-def]
        self.submissions.append(kwargs)
        return FakeNativeRequest(request_id=99)

    def wait(self, *, request_id: int):
        return FakeNativeRequest(request_id=request_id, status="done")


class ReactionExecutorTests(unittest.TestCase):
    def _plan(self) -> ReactionPlan:
        return ReactionPlan(
            plan_key="repeat_hunt_followup:42:creature:46",
            opportunity_type="repeat_hunt_followup",
            rule_type="repeat_hunt_followup",
            player_guid=42,
            subject=SubjectRef(subject_type="creature", subject_entry=46),
            actions=[
                PlannedAction(
                    kind="quest_publish",
                    payload={
                        "quest_id": 910001,
                        "quest_level": 10,
                        "min_level": 8,
                        "questgiver_entry": 1498,
                        "questgiver_name": "Bethor Iceshard",
                        "title": "Bounty: Murloc Forager",
                        "quest_description": "Cull them.",
                        "objective_text": "Slay them.",
                        "offer_reward_text": "Well done.",
                        "request_items_text": "Did you do it?",
                        "objective": {"target_entry": 46, "target_name": "Murloc Forager", "kill_count": 8},
                        "reward": {
                            "money_copper": 1200,
                            "reward_item_entry": 6827,
                            "reward_item_name": "Box of Supplies",
                            "reward_item_count": 1,
                            "reward_xp_difficulty": 4,
                            "reward_spell_id": 22888,
                            "reward_spell_display_id": 22888,
                            "reward_reputations": [{"faction_id": 72, "value": 75}],
                        },
                        "_wm_reserved_slot": {"entity_type": "quest", "reserved_id": 910001, "arc_key": "wm_event:repeat_hunt_followup"},
                    },
                ),
                PlannedAction(
                    kind="item_publish",
                    payload={"item_entry": 910100, "base_item_entry": 6948, "name": "WM Token"},
                ),
                PlannedAction(
                    kind="spell_publish",
                    payload={"spell_entry": 947000, "slot_kind": "visible_spell_slot", "name": "WM Passive", "base_visible_spell_id": 133},
                ),
            ],
            cooldown_key=ReactionCooldownKey(
                rule_type="repeat_hunt_followup",
                player_guid=42,
                subject_type="creature",
                subject_entry=46,
            ),
            cooldown_seconds=3600,
        )

    def test_dry_run_uses_publishers_without_setting_cooldown(self) -> None:
        store = FakeExecutionStore()
        slot_allocator = FakeSlotAllocator()
        executor = ReactionExecutor(client=_DummyClient(), settings=Settings(), store=store, slot_allocator=slot_allocator)
        executor.quest_publisher = FakePublisher()
        executor.item_publisher = FakePublisher()
        executor.spell_publisher = FakePublisher()

        result = executor.execute(plan=self._plan(), mode="dry-run")

        self.assertEqual(result.status, "dry-run")
        self.assertEqual([step.status for step in result.steps], ["dry-run", "dry-run", "dry-run"])
        self.assertEqual(store.cooldowns, [])
        self.assertEqual([event.event_type for event in store.recorded_events], ["reaction_planned"])
        self.assertEqual(slot_allocator.calls, [])
        quest_details = result.steps[0].details
        self.assertTrue(quest_details["dry_run_ready"])
        self.assertEqual(quest_details["slot_preparation"]["current_status"], "free")
        self.assertTrue(quest_details["slot_preparation"]["will_stage_on_apply"])
        self.assertTrue(any("would be staged automatically" in note for note in quest_details["dry_run_notes"]))
        quest_draft = executor.quest_publisher.calls[0][0]
        self.assertEqual(quest_draft.reward.reward_item_entry, 6827)
        self.assertEqual(quest_draft.reward.reward_xp_difficulty, 4)
        self.assertEqual(quest_draft.reward.reward_spell_id, 22888)
        self.assertEqual(quest_draft.reward.reward_reputations[0].faction_id, 72)

    def test_preview_is_read_only(self) -> None:
        store = FakeExecutionStore()
        slot_allocator = FakeSlotAllocator()
        executor = ReactionExecutor(client=_DummyClient(), settings=Settings(), store=store, slot_allocator=slot_allocator)
        executor.quest_publisher = FakePublisher()
        executor.item_publisher = FakePublisher()
        executor.spell_publisher = FakePublisher()

        result = executor.preview(plan=self._plan())

        self.assertEqual(result.mode, "preview")
        self.assertEqual(result.status, "preview")
        self.assertEqual([step.status for step in result.steps], ["dry-run", "dry-run", "dry-run"])
        self.assertEqual(store.recorded_events, [])
        self.assertEqual(store.logged_reactions, [])
        self.assertEqual(store.cooldowns, [])
        self.assertEqual(slot_allocator.calls, [])

    def test_apply_logs_action_events_and_sets_cooldown(self) -> None:
        store = FakeExecutionStore()
        slot_allocator = FakeSlotAllocator()
        executor = ReactionExecutor(client=_DummyClient(), settings=Settings(), store=store, slot_allocator=slot_allocator)
        executor.quest_publisher = FakePublisher()
        executor.item_publisher = FakePublisher()
        executor.spell_publisher = FakePublisher()

        result = executor.execute(plan=self._plan(), mode="apply")

        self.assertEqual(result.status, "applied")
        self.assertEqual(
            [event.event_type for event in store.recorded_events],
            ["reaction_planned", "quest_published", "item_published", "spell_published"],
        )
        self.assertEqual(len(store.logged_reactions), 1)
        self.assertEqual(len(store.cooldowns), 1)
        self.assertEqual(slot_allocator.calls[0][0], "quest")
        self.assertEqual(slot_allocator.calls[0][1], 910001)

    def test_reactive_quest_grant_preview_and_apply_use_runtime_path(self) -> None:
        store = FakeExecutionStore()
        runtime_manager = FakeQuestRuntimeManager()
        executor = ReactionExecutor(
            client=_DummyClient(),
            settings=Settings(),
            store=store,
            reactive_store=FakeReactiveStore(),  # type: ignore[arg-type]
            reactive_runtime=runtime_manager,  # type: ignore[arg-type]
        )
        plan = ReactionPlan(
            plan_key="reactive_bounty:kobold_vermin:5406:creature:6",
            opportunity_type="reactive_bounty_grant",
            rule_type="reactive_bounty:kobold_vermin",
            player_guid=5406,
            subject=SubjectRef(subject_type="creature", subject_entry=6),
            actions=[
                PlannedAction(
                    kind="quest_grant",
                    payload={
                        "quest_id": 910000,
                        "player_guid": 5406,
                        "rule_key": "reactive_bounty:kobold_vermin",
                        "turn_in_npc_entry": 197,
                    },
                )
            ],
        )

        preview = executor.preview(plan=plan)
        applied = executor.execute(plan=plan, mode="apply")

        self.assertEqual(preview.steps[0].kind, "quest_grant")
        self.assertTrue(preview.steps[0].details["dry_run_ready"])
        self.assertEqual(preview.steps[0].details["selected_transport"], "soap")
        self.assertEqual(applied.steps[0].status, "applied")
        self.assertEqual(
            [event.event_type for event in store.recorded_events],
            ["reaction_planned", "quest_grant_issued"],
        )
        self.assertEqual(runtime_manager.preview_calls[0], (5406, "Qraaglock", 910000))
        self.assertEqual(runtime_manager.grant_calls[0], (5406, "Qraaglock", 910000))

    def test_reactive_quest_grant_prefers_native_bridge_when_ready(self) -> None:
        store = FakeExecutionStore()
        runtime_manager = FakeQuestRuntimeManager()
        native_actions = FakeNativeBridgeActions()
        config_path = Path("artifacts") / "test-bridge-config.conf"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            config_path.write_text(
                "\n".join(
                    [
                        "[worldserver]",
                        "WmBridge.Enable = 1",
                        "WmBridge.ActionQueue.Enable = 1",
                        "WmBridge.DbControl.Enable = 1",
                        'WmBridge.PlayerGuidAllowList = ""',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            executor = ReactionExecutor(
                client=_DummyClient(),
                settings=Settings(wm_bridge_config_path=str(config_path), quest_grant_transport="auto"),
                store=store,
                reactive_store=FakeReactiveStore(),  # type: ignore[arg-type]
                reactive_runtime=runtime_manager,  # type: ignore[arg-type]
                native_bridge_actions=native_actions,  # type: ignore[arg-type]
            )
            plan = ReactionPlan(
                plan_key="reactive_bounty:kobold_vermin:5406:creature:6",
                opportunity_type="reactive_bounty_grant",
                rule_type="reactive_bounty:kobold_vermin",
                player_guid=5406,
                subject=SubjectRef(subject_type="creature", subject_entry=6),
                actions=[
                    PlannedAction(
                        kind="quest_grant",
                        payload={"quest_id": 910000, "player_guid": 5406, "rule_key": "reactive_bounty:kobold_vermin"},
                    )
                ],
            )

            preview = executor.preview(plan=plan)
            applied = executor.execute(plan=plan, mode="apply")
        finally:
            if config_path.exists():
                config_path.unlink()

        self.assertEqual(preview.steps[0].details["selected_transport"], "native_bridge")
        self.assertEqual(applied.steps[0].details["selected_transport"], "native_bridge")
        self.assertEqual(applied.steps[0].status, "applied")
        self.assertEqual(runtime_manager.grant_calls, [])
        self.assertEqual(native_actions.submissions[0]["action_kind"], "quest_add")
        self.assertEqual(native_actions.submissions[0]["payload"]["quest_id"], 910000)

    def test_native_quest_grant_idempotency_includes_trigger_identity(self) -> None:
        store = FakeExecutionStore()
        runtime_manager = FakeQuestRuntimeManager()
        native_actions = FakeNativeBridgeActions()
        config_path = Path("artifacts") / "test-bridge-config-idempotency.conf"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            config_path.write_text(
                "\n".join(
                    [
                        "[worldserver]",
                        "WmBridge.Enable = 1",
                        "WmBridge.ActionQueue.Enable = 1",
                        "WmBridge.DbControl.Enable = 1",
                        'WmBridge.PlayerGuidAllowList = ""',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            executor = ReactionExecutor(
                client=_DummyClient(),
                settings=Settings(wm_bridge_config_path=str(config_path), quest_grant_transport="auto"),
                store=store,
                reactive_store=FakeReactiveStore(),  # type: ignore[arg-type]
                reactive_runtime=runtime_manager,  # type: ignore[arg-type]
                native_bridge_actions=native_actions,  # type: ignore[arg-type]
            )

            def plan_for(source_event_key: str) -> ReactionPlan:
                return ReactionPlan(
                    plan_key="reactive_bounty:auto:zone:11:subject:1043:5406:creature:1043",
                    opportunity_type="reactive_bounty_grant",
                    rule_type="reactive_bounty:auto:zone:11:subject:1043",
                    player_guid=5406,
                    subject=SubjectRef(subject_type="creature", subject_entry=1043),
                    metadata={"source_event_key": source_event_key},
                    actions=[
                        PlannedAction(
                            kind="quest_grant",
                            payload={
                                "quest_id": 910046,
                                "player_guid": 5406,
                                "rule_key": "reactive_bounty:auto:zone:11:subject:1043",
                            },
                        )
                    ],
                )

            executor.execute(plan=plan_for("native_bridge:27665"), mode="apply")
            executor.execute(plan=plan_for("native_bridge:27665"), mode="apply")
            executor.execute(plan=plan_for("native_bridge:27670"), mode="apply")
        finally:
            if config_path.exists():
                config_path.unlink()

        keys = [submission["idempotency_key"] for submission in native_actions.submissions]
        self.assertEqual(len(keys), 3)
        self.assertEqual(keys[0], keys[1])
        self.assertNotEqual(keys[1], keys[2])
        self.assertIn("native_bridge:27665", keys[0])
        self.assertIn("native_bridge:27670", keys[2])

    def test_native_quest_grant_idempotency_falls_back_to_trigger_event_id(self) -> None:
        store = FakeExecutionStore()
        runtime_manager = FakeQuestRuntimeManager()
        native_actions = FakeNativeBridgeActions()
        config_path = Path("artifacts") / "test-bridge-config-trigger-id.conf"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            config_path.write_text(
                "\n".join(
                    [
                        "[worldserver]",
                        "WmBridge.Enable = 1",
                        "WmBridge.ActionQueue.Enable = 1",
                        "WmBridge.DbControl.Enable = 1",
                        'WmBridge.PlayerGuidAllowList = ""',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            executor = ReactionExecutor(
                client=_DummyClient(),
                settings=Settings(wm_bridge_config_path=str(config_path), quest_grant_transport="auto"),
                store=store,
                reactive_store=FakeReactiveStore(),  # type: ignore[arg-type]
                reactive_runtime=runtime_manager,  # type: ignore[arg-type]
                native_bridge_actions=native_actions,  # type: ignore[arg-type]
            )

            def plan_for(trigger_event_id: int) -> ReactionPlan:
                return ReactionPlan(
                    plan_key="reactive_bounty:auto:zone:11:subject:1069:5406:creature:1069",
                    opportunity_type="reactive_bounty_grant",
                    rule_type="reactive_bounty:auto:zone:11:subject:1069",
                    player_guid=5406,
                    subject=SubjectRef(subject_type="creature", subject_entry=1069),
                    metadata={"opportunity_metadata": {"trigger_event_id": trigger_event_id}},
                    actions=[
                        PlannedAction(
                            kind="quest_grant",
                            payload={
                                "quest_id": 910047,
                                "player_guid": 5406,
                                "rule_key": "reactive_bounty:auto:zone:11:subject:1069",
                            },
                        )
                    ],
                )

            executor.execute(plan=plan_for(27671), mode="apply")
            executor.execute(plan=plan_for(27671), mode="apply")
            executor.execute(plan=plan_for(27675), mode="apply")
        finally:
            if config_path.exists():
                config_path.unlink()

        keys = [submission["idempotency_key"] for submission in native_actions.submissions]
        self.assertEqual(len(keys), 3)
        self.assertEqual(keys[0], keys[1])
        self.assertNotEqual(keys[1], keys[2])
        self.assertIn("trigger_event:27671", keys[0])
        self.assertIn("trigger_event:27675", keys[2])

    def test_native_bridge_action_idempotency_includes_trigger_identity_and_suffix(self) -> None:
        store = FakeExecutionStore()
        native_actions = FakeNativeBridgeActions()
        executor = ReactionExecutor(
            client=_DummyClient(),
            settings=Settings(),
            store=store,
            native_bridge_actions=native_actions,  # type: ignore[arg-type]
        )

        def plan_for(source_event_key: str) -> ReactionPlan:
            return ReactionPlan(
                plan_key="area_pressure_refresh:5406:creature:46",
                opportunity_type="area_pressure_refresh",
                rule_type="area_pressure_refresh",
                player_guid=5406,
                subject=SubjectRef(subject_type="creature", subject_entry=46),
                metadata={"source_event_key": source_event_key},
                actions=[
                    PlannedAction(
                        kind="native_bridge_action",
                        payload={
                            "native_action_kind": "player_apply_aura",
                            "player_guid": 5406,
                            "payload": {"spell_id": 687},
                            "risk_level": "medium",
                            "idempotency_suffix": "aura",
                        },
                    )
                ],
            )

        executor.execute(plan=plan_for("native_bridge:30001"), mode="apply")
        executor.execute(plan=plan_for("native_bridge:30001"), mode="apply")
        executor.execute(plan=plan_for("native_bridge:30009"), mode="apply")

        keys = [submission["idempotency_key"] for submission in native_actions.submissions]
        self.assertEqual(len(keys), 3)
        self.assertEqual(keys[0], keys[1])
        self.assertNotEqual(keys[1], keys[2])
        self.assertIn("native_bridge:30001", keys[0])
        self.assertIn("native_bridge:30009", keys[2])
        self.assertTrue(keys[0].endswith(":native:player_apply_aura:aura"))

    def test_structured_ref_payloads_are_accepted(self) -> None:
        store = FakeExecutionStore()
        executor = ReactionExecutor(client=_DummyClient(), settings=Settings(), store=store)
        executor.quest_publisher = FakePublisher()
        plan = ReactionPlan(
            plan_key="reactive_bounty:kobold_vermin:5406:creature:6",
            opportunity_type="reactive_bounty_grant",
            rule_type="reactive_bounty:kobold_vermin",
            player_guid=5406,
            subject=SubjectRef(subject_type="creature", subject_entry=6),
            actions=[
                PlannedAction(
                    kind="quest_publish",
                    payload={
                        "quest": QuestRef(id=910000, title="Bounty: Kobold Vermin").to_dict(),
                        "quest_id": 910000,
                        "quest_level": 4,
                        "min_level": 2,
                        "questgiver": NpcRef(entry=197, name="Marshal McBride").to_dict(),
                        "questgiver_entry": 197,
                        "questgiver_name": "Marshal McBride",
                        "starter_npc": None,
                        "ender_npc": NpcRef(entry=197, name="Marshal McBride").to_dict(),
                        "start_npc_entry": None,
                        "end_npc_entry": 197,
                        "title": "Bounty: Kobold Vermin",
                        "quest_description": "Cull them.",
                        "objective_text": "Slay them.",
                        "offer_reward_text": "Well done.",
                        "request_items_text": "Did you do it?",
                        "objective": {
                            "target": CreatureRef(entry=6, name="Kobold Vermin").to_dict(),
                            "target_entry": 6,
                            "target_name": "Kobold Vermin",
                            "kill_count": 4,
                        },
                        "reward": {"money_copper": 900, "reward_item_count": 1},
                        "_wm_reserved_slot": {"entity_type": "quest", "reserved_id": 910000},
                    },
                ),
                PlannedAction(
                    kind="quest_grant",
                    payload={
                        "quest": QuestRef(id=910000, title="Bounty: Kobold Vermin").to_dict(),
                        "player": PlayerRef(guid=5406, name="Qraaglock").to_dict(),
                        "subject": CreatureRef(entry=6, name="Kobold Vermin").to_dict(),
                        "turn_in_npc": NpcRef(entry=197, name="Marshal McBride").to_dict(),
                        "quest_id": 910000,
                        "player_guid": 5406,
                    },
                ),
            ],
        )
        executor.reactive_store = FakeReactiveStore()  # type: ignore[assignment]
        executor.reactive_runtime = FakeQuestRuntimeManager()  # type: ignore[assignment]

        result = executor.preview(plan=plan)

        self.assertEqual(result.steps[0].status, "dry-run")
        self.assertEqual(result.steps[1].status, "dry-run")
        self.assertEqual(result.steps[1].details["quest"]["title"], "Bounty: Kobold Vermin")
        self.assertEqual(result.steps[1].details["player"]["guid"], 5406)


if __name__ == "__main__":
    unittest.main()
