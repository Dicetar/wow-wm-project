from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from wm.autoplay.llm import AutoplayLlmAdapter
from wm.autoplay.llm import llm_generation_schema
from wm.autoplay.policy import AutoplayPolicy, SafeWindow
from wm.autoplay.service import AutoplayRuntimeConfig, AutoplayService, drive_pending_runtime
from wm.autoplay.service import _chat_max_tokens
from wm.autoplay.service import _compact_autoplay_context
from wm.autoplay.service import _merged_control_config
from wm.autoplay.service import _normalize_lanes
from wm.autoplay.service import _CHAT_PART_LIMIT
from wm.autoplay.service import _CHAT_REPLY_MAX_CHARS
from wm.autoplay.service import _sanitize_chat_reply
from wm.autoplay.service import _split_chat_message
from wm.autoplay.service import status_summary
from wm.autoplay.state import AutoplayStateStore
from wm.autoplay.state import utc_now_iso
from wm.config import Settings
from wm.events.models import WMEvent
from wm.llm.lmstudio import LmStudioSettings
from wm.llm.proposal_adapter import Proposal, ProposalKind
from wm.panel.approval_gate import ApprovalGate
from wm.panel.issues_queue import IssuesQueue
from wm.panel.state import PanelState


QUEST_DRAFT = {
    "schema_version": "wm.quest.release.repeatable_bounty.v1",
    "quest_kind": "repeatable_bounty",
    "player_guid": 1,
    "slot_policy": "fresh_reserved_required",
    "repeatable": True,
    "quest": {"quest_level": 70, "min_level": 68, "grant_mode": "npc_start", "template_defaults": {"SpecialFlags": 1}},
    "objective": {"kind": "kill", "target_entry": 21059, "kill_count": 3},
    "reward": {"kind": "none"},
}

ITEM_DRAFT = {
    "schema_version": "wm.item.release.managed_power.v1",
    "content_kind": "item",
    "player_guid": 1,
    "item_key": "test_item",
    "item_entry": 910500,
    "slot_policy": "fresh_item_slot_required",
    "base_item_entry": 2994,
    "visibility": {"player_visible_state_required": True, "tooltip_required": True, "wearer_aura_spell_id": 132},
    "reward_integration": {"fresh_quest_required_when_reward_changes": True},
    "runtime": {"native_behavior_required": True, "audit_required": True, "rollback_required": True},
    "effects": [{"effect_key": "wearer", "kind": "wearer_aura", "spell_id": 132}],
}

SPELL_DRAFT = {
    "schema_version": "wm.spell.release.managed_spell.v1",
    "content_kind": "spell",
    "player_guid": 1,
    "spell_key": "test_spell",
    "spell_entry": 947001,
    "slot_kind": "visible_spell_slot",
    "name": "Autoplay Test Spell",
    "base_visible_spell_id": 133,
    "proc_rules": [],
    "linked_spells": [],
    "runtime": {"audit_required": True, "rollback_required": True, "client_patch_required": True},
}

ABILITY_DRAFT = {
    "schema_version": "wm.ability.release.shell_power.v1",
    "content_kind": "ability",
    "player_guid": 1,
    "ability_key": "test_ability",
    "ability_type": "self_aura",
    "shell_family": "self_aura",
    "slot_policy": "existing_named_shell",
    "behavior_kind": "native_behavior",
    "client_truth": {"client_patch_required": True, "server_dbc_required": True, "spellbook_button_required": True},
    "runtime": {"native_behavior_required": True, "audit_required": True},
}

SCENE_DRAFT = {
    "schema_version": "wm.scene.release.native_sequence.v1",
    "content_kind": "scene",
    "player_guid": 1,
    "scene_key": "test_scene",
    "scene_type": "creature_marker",
    "slot_policy": "no_visible_id_required",
    "trigger": {"kind": "manual_operator", "source_event_required": False},
    "runtime": {"native_actions_required": True, "audit_required": True, "player_scope_required": True},
    "steps": [
        {
            "step_key": "say",
            "native_action_kind": "player_chat_message",
            "payload": {"message": "hello", "style": "channel", "channel_name": "WM", "sender_name": "WorldMaster"},
            "risk_level": "low",
            "idempotency_suffix": "say",
            "requires_live_proof": True,
        }
    ],
}

ACTION_DRAFT = {
    "schema_version": "control.proposal.v1",
    "source_event": {"event_id": 1, "source": "native_bridge", "source_event_key": "evt1"},
    "player": {"guid": 1},
    "selected_recipe": "manual_admin_action",
    "action": {"kind": "native_bridge_action", "payload": {"native_action_kind": "debug_ping", "payload": {}}},
    "rationale": "test",
    "risk": {"level": "low", "irreversible": False, "notes": []},
    "author": {"kind": "llm", "name": "autoplay"},
    "metadata": {},
}


class FakeLlmClient:
    def __init__(self, draft):
        self.draft = draft
        self.settings = SimpleNamespace(base_url="http://localhost:1234/v1", model="local-model")

    def list_models(self):
        return ["local-model"]

    def generate_json(self, **kwargs):
        return {"request": kwargs, "content": "{}", "parsed": dict(self.draft)}


def test_policy_blocks_unsafe_risk_and_stages_dbc_until_safe_window():
    policy = AutoplayPolicy(max_auto_risk="low")
    blocked = policy.decide(
        schema_version="wm.scene.release.native_sequence.v1",
        lane="scene",
        risk="medium",
        readiness_ok=True,
        lm_ok=True,
        session_ok=True,
        dry_run_ok=True,
        rollback_available=True,
        safe_window=SafeWindow(),
    )
    assert blocked.status == "blocked"
    assert "risk_exceeds_policy:medium>low" in blocked.blockers

    staged = policy.decide(
        schema_version="wm.ability.release.shell_power.v1",
        payload=ABILITY_DRAFT,
        readiness_ok=True,
        lm_ok=True,
        session_ok=True,
        dry_run_ok=True,
        rollback_available=True,
        safe_window=SafeWindow(client_running=True),
    )
    assert staged.status == "maintenance_pending"
    assert staged.maintenance_reasons == ["dbc_safe_window_required"]


def test_policy_blocks_stale_source_events():
    policy = AutoplayPolicy(max_source_event_age_seconds=10)
    decision = policy.decide(
        schema_version="wm.scene.release.native_sequence.v1",
        readiness_ok=True,
        lm_ok=True,
        session_ok=True,
        dry_run_ok=True,
        rollback_available=True,
        source_event_at="2026-05-25T00:00:00Z",
        now=datetime(2026, 5, 25, 0, 1, tzinfo=timezone.utc),
    )
    assert "source_event_stale" in decision.blockers


def test_llm_adapter_generates_and_locks_all_enabled_lane_drafts():
    samples = [QUEST_DRAFT, ITEM_DRAFT, SPELL_DRAFT, ABILITY_DRAFT, SCENE_DRAFT, ACTION_DRAFT]
    for sample in samples:
        adapter = AutoplayLlmAdapter(client=FakeLlmClient(sample))
        result = adapter.generate(
            schema_version=sample["schema_version"],
            instruction="draft safe content",
            deterministic_facts={
                "player_guid": 5408,
                "allowed_native_action_kinds": ["player_chat_message"],
                "source_event": {
                    "event_id": 10,
                    "source": "native_bridge",
                    "source_event_key": "native_bridge:10",
                    "event_type": "kill",
                    "metadata": {"too": "large"},
                },
            },
        )
        assert result.ok, (sample["schema_version"], result.issues)
        if result.schema_version == "control.proposal.v1":
            assert result.draft["player"]["guid"] == 5408
            assert result.draft["author"]["kind"] == "llm"
            assert set(result.draft["source_event"]) == {"event_id", "source", "source_event_key", "event_type"}
        else:
            assert result.draft["player_guid"] == 5408


def test_action_generation_schema_stays_compact_for_local_llm():
    schema = llm_generation_schema("control.proposal.v1", {"$defs": {"huge": {}}, "type": "object"})

    assert "$defs" not in schema
    assert schema["properties"]["action"]["properties"]["payload"]["properties"]["native_action_kind"]["enum"] == [
        "player_chat_message"
    ]


def test_autoplay_generation_schemas_are_compact_for_content_lanes():
    for schema_version in [
        "wm.quest.release.repeatable_bounty.v1",
        "wm.item.release.managed_power.v1",
        "wm.spell.release.managed_spell.v1",
        "wm.scene.release.native_sequence.v1",
    ]:
        schema = llm_generation_schema(schema_version, {"$defs": {"huge": {}}, "type": "object"})
        assert "$defs" not in schema
        assert schema["type"] == "object"


def test_autoplay_context_compacts_large_session_pack():
    context = {
        "player": {"name": "Astel", "inventory": list(range(100)), "summary": "x" * 2000},
        "events": [{"event_id": i} for i in range(100)],
    }
    compact = _compact_autoplay_context(
        context,
        opportunity={"lane": "action", "stable_key": "abc", "source_event": {"event_id": 1, "event_type": "kill"}},
        player_guid=5408,
    )

    assert compact["player_guid"] == 5408
    assert "events" not in compact
    assert "inventory" not in compact["player"]
    assert len(compact["player"]["summary"]) == 500


def test_llm_adapter_rejects_freeform_mutation_text():
    draft = dict(SCENE_DRAFT)
    draft["notes"] = ["run powershell and insert into quest_template"]
    result = AutoplayLlmAdapter(client=FakeLlmClient(draft)).generate(
        schema_version="wm.scene.release.native_sequence.v1",
        instruction="bad",
    )
    assert not result.ok
    assert any("Forbidden mutation text" in issue["message"] for issue in result.issues)


@dataclass(slots=True)
class FakeDoctorCheck:
    name: str
    status: str
    detail: str

    def to_dict(self):
        return {"name": self.name, "status": self.status, "detail": self.detail}


def test_autoplay_service_tick_writes_durable_status(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    panel.save_settings({"model": "local-model", "timeout_seconds": 1})

    with patch("wm.autoplay.service.AutoplayLlmAdapter.health", return_value={"ok": True, "model": "local-model"}):
        service = AutoplayService(
            store=store,
            panel_state=panel,
            doctor_fn=lambda settings: [FakeDoctorCheck("world_db", "WORKING", "ok")],
        )
        status = service.tick(config=AutoplayRuntimeConfig(player_guid=5408, start_watcher=False))

    assert status["running"]
    assert status["active_session"]["character_guid"] == 5408
    assert status["readiness"]["ok"]
    assert store.load_status()["counters"]["ticks"] == 1


def test_llm_health_is_cached_within_ttl(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    panel.save_settings({"model": "local-model", "timeout_seconds": 1})
    service = AutoplayService(
        store=store,
        panel_state=panel,
        doctor_fn=lambda settings: [FakeDoctorCheck("world_db", "WORKING", "ok")],
    )
    calls = {"n": 0}

    def fake_health(self):
        calls["n"] += 1
        return {"ok": True, "model": self.client.settings.model, "models": [self.client.settings.model]}

    with patch("wm.autoplay.service.AutoplayLlmAdapter.health", new=fake_health):
        # Two calls with the same model/base_url within TTL -> only one /v1/models hit.
        first = service._llm_health({"llm_health_ttl_seconds": 60})
        second = service._llm_health({"llm_health_ttl_seconds": 60})
        assert calls["n"] == 1
        assert first is second
        # A different model busts the cache key and forces a fresh probe.
        service._llm_health({"llm_health_ttl_seconds": 60, "llm_model": "other-model"})
        assert calls["n"] == 2
        # Re-querying the new model stays cached too.
        service._llm_health({"llm_health_ttl_seconds": 60, "llm_model": "other-model"})
        assert calls["n"] == 2


def _ambient_service(tmp_path: Path) -> AutoplayService:
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    panel.save_settings({"model": "local-model", "timeout_seconds": 1})
    return AutoplayService(
        store=store,
        panel_state=panel,
        doctor_fn=lambda settings: [FakeDoctorCheck("world_db", "WORKING", "ok")],
    )


def _ambient_args(**over):
    args = {
        "control_config": {
            "llm_ambient_narration_enabled": True,
            "llm_ambient_cooldown_seconds": 150,
            "llm_event_age_seconds": 300,
        },
        "settings": Settings.from_env(),
        "readiness": {"ok": True},
        "session": {"character_guid": 5408},
        "llm": {"ok": True},
        "status": {},
    }
    args.update(over)
    return args


def test_ambient_narration_fires_on_notable_event(tmp_path: Path):
    service = _ambient_service(tmp_path)
    event = {
        "event_type": "enter_area",
        "player_guid": 5408,
        "zone_id": 40,
        "area_id": 108,
        "event_value": "Sentinel Hill",
        "source_event_key": "area-1",
        "occurred_at": utc_now_iso(),
    }
    with patch.object(service, "_recent_events", return_value=[event]), patch.object(
        service, "_narrate_ambient_cue", return_value={"ok": True, "message": "The dust settles over Sentinel Hill."}
    ) as narrate:
        record = service._drive_ambient_narration(**_ambient_args())
    assert record is not None
    assert record["kind"] == "enter_area"
    assert record["ok"] is True
    assert "Sentinel Hill" in record["descriptor"]
    narrate.assert_called_once()
    # the moment is claimed so it cannot re-fire
    assert "area-1" in service.store.load_seen_event_keys()


def test_ambient_narration_skips_ordinary_events(tmp_path: Path):
    service = _ambient_service(tmp_path)
    kill = {"event_type": "kill", "player_guid": 5408, "source_event_key": "kill-9", "occurred_at": utc_now_iso()}
    with patch.object(service, "_recent_events", return_value=[kill]), patch.object(
        service, "_narrate_ambient_cue"
    ) as narrate:
        record = service._drive_ambient_narration(**_ambient_args())
    assert record is None
    narrate.assert_not_called()


def test_ambient_narration_respects_cooldown(tmp_path: Path):
    service = _ambient_service(tmp_path)
    event = {
        "event_type": "quest_completed",
        "player_guid": 5408,
        "event_value": "Defend the Farm",
        "source_event_key": "quest-7",
        "occurred_at": utc_now_iso(),
    }
    status = {"latest_ambient": {"at": utc_now_iso()}}  # just narrated -> on cooldown
    with patch.object(service, "_recent_events", return_value=[event]), patch.object(
        service, "_narrate_ambient_cue"
    ) as narrate:
        record = service._drive_ambient_narration(**_ambient_args(status=status))
    assert record is None
    narrate.assert_not_called()


def test_ambient_death_bypasses_cooldown(tmp_path: Path):
    service = _ambient_service(tmp_path)
    death = {
        "event_type": "death", "player_guid": 5408, "event_value": "Westfall",
        "source_event_key": "death-1", "occurred_at": utc_now_iso(),
    }
    status = {"latest_ambient": {"at": utc_now_iso()}}  # cooldown active right now
    with patch.object(service, "_recent_events", return_value=[death]), patch.object(
        service, "_narrate_ambient_cue", return_value={"ok": True, "message": "Astel has fallen."}
    ) as narrate:
        record = service._drive_ambient_narration(**_ambient_args(status=status))
    assert record is not None and record["kind"] == "death"
    narrate.assert_called_once()


def test_ambient_prefers_high_priority_over_zone_change(tmp_path: Path):
    service = _ambient_service(tmp_path)
    # newest-first: a zone change is newest, a level-up is older but high-priority
    events = [
        {"event_type": "enter_area", "player_guid": 5408, "event_value": "Goldshire", "source_event_key": "area-9", "occurred_at": utc_now_iso()},
        {"event_type": "level_up", "player_guid": 5408, "event_value": "14", "source_event_key": "lvl-1", "occurred_at": utc_now_iso()},
    ]
    with patch.object(service, "_recent_events", return_value=events), patch.object(
        service, "_narrate_ambient_cue", return_value={"ok": True, "message": "Astel reaches level 14."}
    ):
        record = service._drive_ambient_narration(**_ambient_args())
    assert record is not None and record["kind"] == "level_up"


def test_ambient_narration_disabled_returns_none(tmp_path: Path):
    service = _ambient_service(tmp_path)
    event = {"event_type": "enter_area", "player_guid": 5408, "source_event_key": "area-2", "occurred_at": utc_now_iso()}
    cfg = {"llm_ambient_narration_enabled": False, "llm_ambient_cooldown_seconds": 150, "llm_event_age_seconds": 300}
    with patch.object(service, "_recent_events", return_value=[event]), patch.object(
        service, "_narrate_ambient_cue"
    ) as narrate:
        record = service._drive_ambient_narration(**_ambient_args(control_config=cfg))
    assert record is None
    narrate.assert_not_called()


def test_remembered_facts_surfaces_active_steering(tmp_path: Path):
    from wm.autoplay.service import _chat_identity_facts
    context = {
        "speaker": {"guid": 5408, "name": "Astel"},
        "session_context_pack": {
            "conversation_steering": [
                {"steering_key": "k1", "steering_kind": "preferred_theme", "body": "Prefers undead foes."},
                {"steering_key": "k2", "steering_kind": "player_fact", "body": ""},  # no body -> skipped
                {"steering_key": "k3", "steering_kind": "player_fact", "body": "old", "is_active": False},  # inactive
            ],
        },
    }
    identity = _chat_identity_facts(context, player_guid=5408)
    assert identity["remembered"] == [{"kind": "preferred_theme", "body": "Prefers undead foes."}]


def test_capture_conversation_memory_persists_durable_note(tmp_path: Path):
    service = _ambient_service(tmp_path)
    note = {"steering_key": "prefers_undead", "steering_kind": "preferred_theme", "body": "Likes undead.", "source": "conversation"}
    with patch("wm.autoplay.memory_extract.build_memory_client", return_value=object()), patch(
        "wm.autoplay.memory_extract.extract_memory_note", return_value=note
    ), patch.object(service, "_persist_conversation_memory") as persist:
        service._capture_conversation_memory(
            control_config={"llm_conversation_memory_enabled": True},
            settings=Settings.from_env(),
            player_guid=5408,
            message="I love hunting undead.",
            world_context={},
        )
    persist.assert_called_once()
    assert persist.call_args.kwargs["note"] == note


def test_capture_conversation_memory_skips_when_nothing_durable(tmp_path: Path):
    service = _ambient_service(tmp_path)
    with patch("wm.autoplay.memory_extract.build_memory_client", return_value=object()), patch(
        "wm.autoplay.memory_extract.extract_memory_note", return_value=None
    ), patch.object(service, "_persist_conversation_memory") as persist:
        service._capture_conversation_memory(
            control_config={"llm_conversation_memory_enabled": True},
            settings=Settings.from_env(),
            player_guid=5408,
            message="hello there",
            world_context={},
        )
    persist.assert_not_called()


def test_looks_like_memory_statement():
    from wm.autoplay.service import _looks_like_memory_statement
    assert _looks_like_memory_statement("Remember that I prefer undead.")
    assert _looks_like_memory_statement("call me Ser Astel")
    assert _looks_like_memory_statement("I hate murlocs")
    assert not _looks_like_memory_statement("where am i?")
    assert not _looks_like_memory_statement("heal me")
    assert not _looks_like_memory_statement("")


def test_voice_world_digest_drops_heavy_sections():
    from wm.autoplay.service import _voice_world_digest
    full = {
        "live_location": {"zone_name": "Westfall", "area_name": "Sentinel Hill", "fresh": True, "x": 1.0, "y": 2.0},
        "perception": {"source": "native_bridge_perception", "creature_count": 7, "gameobject_count": 2, "detail_note": "x"},
        "events": {"recent_wm_chat": [{"m": 1}, {"m": 2}, {"m": 3}, {"m": 4}], "recent_global": [1, 2, 3]},
        "database": {"online_characters": list(range(25)), "active_quests": list(range(25))},
        "session_context_pack": {"big": "blob"},
    }
    digest = _voice_world_digest(full)
    assert set(digest.keys()) == {"live_location", "perception", "recent_wm_chat"}
    assert digest["live_location"]["zone_name"] == "Westfall"
    assert "x" not in digest["live_location"]  # coordinates dropped from voice digest
    assert digest["perception"]["creature_count"] == 7
    assert "detail_note" not in digest["perception"]
    assert len(digest["recent_wm_chat"]) == 3  # capped


def test_looks_like_scene_request():
    from wm.autoplay.service import _looks_like_scene_request
    assert _looks_like_scene_request("summon a guard and have it greet me")
    assert _looks_like_scene_request("stage an ambush")
    assert not _looks_like_scene_request("where am i?")
    assert not _looks_like_scene_request("heal me")


def test_handle_scene_request_parks_pending_scene(tmp_path: Path):
    from wm.autoplay.scene_compose import ComposedScene
    service = _ambient_service(tmp_path)
    scene = ComposedScene(scene_name="Greeting", steps=[
        {"native_action_kind": "creature_spawn", "payload": {"creature_entry": 68, "arc_key": "g", "duration_ms": 60000}, "expected_effect": ""},
        {"native_action_kind": "creature_say", "payload": {"arc_key": "g", "text": "Well met."}, "expected_effect": ""},
    ])
    with patch("wm.autoplay.scene_compose.extract_scene_request", return_value=scene), \
         patch("wm.autoplay.intent_extract.build_intent_client", return_value=object()), \
         patch("wm.targets.name_resolver.get_default_creature_name_resolver", return_value=object()), \
         patch.object(service, "_speak", return_value={"ok": True}):
        result = service._handle_scene_request(
            settings=Settings.from_env(), control_config={}, player_guid=5408,
            message="summon a guard to greet me", world_context={},
        )
    assert result == {"scene": "pending", "scene_name": "Greeting", "steps": 2}
    pending = service.store.load_pending_intent(5408)
    assert pending["kind"] == "scene"
    assert len(pending["steps"]) == 2


def test_apply_pending_runs_scene_steps(tmp_path: Path):
    service = _ambient_service(tmp_path)

    class FakeApplied:
        status = "applied"

    executed = []

    class FakeCoord:
        def execute(self, *, proposal, mode, confirm_live_apply):
            executed.append(proposal.action.payload["native_action_kind"])
            return FakeApplied()

    pending = {
        "kind": "scene", "scene_name": "Greeting", "risk": "medium",
        "steps": [
            {"native_action_kind": "creature_spawn", "payload": {"creature_entry": 68, "duration_ms": 60000}},
            {"native_action_kind": "creature_say", "payload": {"arc_key": "g", "text": "Hi"}},
        ],
    }
    with patch.object(service, "_control_coordinator", return_value=FakeCoord()), \
         patch.object(service, "_speak", return_value={"ok": True}):
        result = service._apply_pending(
            settings=Settings.from_env(), player_guid=5408, pending=pending, source_message="yes",
        )
    assert result["scene"] == "applied"
    assert result["steps_executed"] == 2
    assert executed == ["creature_spawn", "creature_say"]


def test_handle_intent_spawn_resolves_name_to_entry(tmp_path: Path):
    service = _ambient_service(tmp_path)

    class FakeResolver:
        def best_entry(self, name):
            return 883 if str(name).strip().lower() == "deer" else None

    class FakeDry:
        status = "dry-run"

    class FakeCoord:
        def execute(self, **kwargs):
            return FakeDry()

    with patch("wm.targets.name_resolver.get_default_creature_name_resolver", return_value=FakeResolver()), \
         patch.object(service, "_control_coordinator", return_value=FakeCoord()), \
         patch.object(service, "_speak", return_value={"ok": True}):
        result = service._handle_intent(
            settings=Settings.from_env(),
            control_config={},
            player_guid=5408,
            intent={"verb": "creature_spawn", "args": {"creature_name": "deer"}, "reason": "spawn deer"},
            source_message="spawn a deer",
        )
    assert result["intent"] == "pending"  # creature_spawn is confirm-mode
    pending = service.store.load_pending_intent(5408)
    payload = pending["proposal"]["action"]["payload"]["payload"]
    assert payload["creature_entry"] == 883
    assert payload["resolved_from_name"] == "deer"


def test_handle_intent_spawn_unresolved_name_rejected(tmp_path: Path):
    service = _ambient_service(tmp_path)

    class FakeResolver:
        def best_entry(self, name):
            return None

    with patch("wm.targets.name_resolver.get_default_creature_name_resolver", return_value=FakeResolver()), \
         patch.object(service, "_speak", return_value={"ok": True}):
        result = service._handle_intent(
            settings=Settings.from_env(),
            control_config={},
            player_guid=5408,
            intent={"verb": "creature_spawn", "args": {"creature_name": "frobnicator"}, "reason": "x"},
            source_message="spawn a frobnicator",
        )
    assert result["intent"] == "rejected"
    assert "frobnicator" in result["reason"]


def test_persist_conversation_memory_builds_valid_plan(tmp_path: Path):
    # Exercises the REAL persist path (import + journey plan build + validation),
    # faking only the DB client. This is what catches a wrong class import.
    service = _ambient_service(tmp_path)
    captured_sql: list[str] = []

    class FakeMysql:
        def query(self, **kwargs):
            captured_sql.append(kwargs.get("sql", ""))
            return []

    note = {"steering_key": "prefers_undead", "steering_kind": "preferred_theme", "body": "Likes undead.", "source": "conversation"}
    with patch("wm.db.mysql_cli.MysqlCliClient", return_value=FakeMysql()):
        service._persist_conversation_memory(settings=Settings.from_env(), player_guid=5408, note=note)
    # The steering upsert SQL was issued against the conversation steering table.
    assert any("wm_character_conversation_steering" in sql for sql in captured_sql)
    assert any("prefers_undead" in sql for sql in captured_sql)


def test_capture_conversation_memory_disabled(tmp_path: Path):
    service = _ambient_service(tmp_path)
    with patch("wm.autoplay.memory_extract.extract_memory_note") as extract, patch.object(
        service, "_persist_conversation_memory"
    ) as persist:
        service._capture_conversation_memory(
            control_config={"llm_conversation_memory_enabled": False},
            settings=Settings.from_env(),
            player_guid=5408,
            message="remember this please",
            world_context={},
        )
    extract.assert_not_called()
    persist.assert_not_called()


def test_autoplay_service_generates_llm_draft_from_recent_event(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    panel.save_settings({"model": "local-model", "timeout_seconds": 1})
    event = WMEvent(
        event_class="observed",
        event_type="kill",
        source="test",
        source_event_key="kill-1",
        occurred_at=utc_now_iso(),
        player_guid=1,
        subject_type="creature",
        subject_entry=21059,
        event_id=10,
    )

    with patch("wm.autoplay.service.build_session_context_pack", return_value={"player_guid": 1}):
        service = AutoplayService(
            store=store,
            panel_state=panel,
            doctor_fn=lambda settings: [FakeDoctorCheck("world_db", "WORKING", "ok")],
        )
        with patch.object(service, "_llm_health", return_value={"ok": True, "model": "local-model"}):
            with patch.object(service, "_recent_events", return_value=[event]):
                with patch.object(service, "_llm_adapter", return_value=AutoplayLlmAdapter(client=FakeLlmClient(SCENE_DRAFT))):
                    with patch.object(service, "_control_coordinator", return_value=FakeControlCoordinator()):
                        status = service.tick(
                            config=AutoplayRuntimeConfig(
                                player_guid=1,
                                start_watcher=False,
                                llm_cooldown_seconds=0,
                                llm_lanes=("scene",),
                            )
                        )

    assert status["latest_opportunity"]["source_event_key"] == "kill-1"
    assert status["latest_proposal"]["ok"] is True
    assert status["counters"]["drafts_generated"] == 1
    assert panel.list_drafts(limit=1)[0]["origin"] == "autoplay_llm"
    assert "kill-1" in store.load_seen_event_keys()


def test_drive_pending_runtime_dry_runs_then_applies_eligible_proposal(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    calls: list[str] = []

    def quest_applier(proposal, *, mode):
        calls.append(mode)
        return {"ok": True, "mode": mode}

    gate = ApprovalGate(issues=IssuesQueue(), quest_compiler=quest_applier, quest_rollback=lambda entry, mode: {"ok": True})
    gate.submit(Proposal(kind=ProposalKind.QUEST, character_guid=5408, payload=QUEST_DRAFT))
    runtime = SimpleNamespace(gate=gate)

    results = drive_pending_runtime(
        runtime=runtime,
        store=store,
        policy=AutoplayPolicy(),
        readiness_ok=True,
        lm_ok=True,
        safe_window=SafeWindow(),
    )

    assert calls == ["dry-run", "apply"]
    assert results[0]["policy"]["status"] == "allow"
    assert gate.pending() == []


def test_drive_pending_runtime_stages_dbc_proposal_without_applying(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    calls: list[str] = []

    def ability_applier(proposal, *, mode):
        calls.append(mode)
        return {"ok": True, "mode": mode}

    gate = ApprovalGate(issues=IssuesQueue(), ability_compiler=ability_applier)
    gate.submit(Proposal(kind=ProposalKind.ABILITY, character_guid=5408, payload=ABILITY_DRAFT))
    runtime = SimpleNamespace(gate=gate)

    results = drive_pending_runtime(
        runtime=runtime,
        store=store,
        policy=AutoplayPolicy(),
        readiness_ok=True,
        lm_ok=True,
        safe_window=SafeWindow(client_running=True),
    )

    assert calls == ["dry-run"]
    assert results[0]["policy"]["status"] == "maintenance_pending"
    assert gate.pending()
    assert store.load_status()["maintenance_pending"]


class FakeControlExecutionResult:
    def __init__(self, *, status: str, proposal):
        self.status = status
        self.proposal = proposal

    def to_dict(self):
        return {"status": self.status, "proposal": self.proposal.model_dump(mode="json")}


class FakeControlCoordinator:
    def __init__(self):
        self.calls: list[tuple[str, object]] = []
        self.executor = FakePlanExecutor()

    def execute(self, *, proposal, mode: str, confirm_live_apply: bool = False):
        self.calls.append((mode, proposal))
        if mode == "dry-run":
            return FakeControlExecutionResult(status="dry-run", proposal=proposal)
        assert confirm_live_apply
        return FakeControlExecutionResult(status="applied", proposal=proposal)


class FakePlanResult:
    def __init__(self, *, status: str, plan):
        self.status = status
        self.plan = plan

    def to_dict(self):
        return {"status": self.status, "plan_key": self.plan.plan_key, "actions": [action.kind for action in self.plan.actions]}


class FakePlanExecutor:
    def __init__(self):
        self.calls: list[tuple[str, object]] = []

    def preview(self, *, plan):
        self.calls.append(("dry-run", plan))
        return FakePlanResult(status="preview", plan=plan)

    def execute(self, *, plan, mode: str):
        self.calls.append((mode, plan))
        return FakePlanResult(status="applied", plan=plan)


def _autoplay_record(*, draft_id: str, lane: str, payload: dict) -> dict:
    return {
        "draft_id": draft_id,
        "ok": True,
        "origin": "autoplay_llm",
        "state": "VALIDATED",
        "lane": lane,
        "schema_version": payload["schema_version"],
        "player_guid": payload.get("player_guid") or payload.get("player", {}).get("guid"),
        "opportunity": {
            "opportunity_id": f"{draft_id}-opportunity",
            "source_event_at": utc_now_iso(),
            "source_event": {"event_id": 1, "source": "test", "source_event_key": f"{draft_id}-event"},
        },
        "parsed_json": payload,
        "issues": [],
    }


def test_autoplay_service_auto_applies_policy_eligible_action_draft(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    store.add_draft(_autoplay_record(draft_id="action-1", lane="action", payload=dict(ACTION_DRAFT)))
    coordinator = FakeControlCoordinator()
    service = AutoplayService(
        store=store,
        panel_state=panel,
        doctor_fn=lambda settings: [FakeDoctorCheck("world_db", "WORKING", "ok")],
    )

    with patch.object(service, "_llm_health", return_value={"ok": True, "model": "local-model"}):
        with patch.object(service, "_recent_events", return_value=[]):
            with patch.object(service, "_control_coordinator", return_value=coordinator):
                status = service.tick(config=AutoplayRuntimeConfig(player_guid=1, start_watcher=False, llm_cooldown_seconds=0))

    assert [mode for mode, _proposal in coordinator.calls] == ["dry-run", "apply"]
    runtime_proposal = coordinator.calls[0][1]
    assert runtime_proposal.author.kind == "manual_admin"
    assert runtime_proposal.source_event is None
    assert runtime_proposal.metadata["autoplay_original_author"]["kind"] == "llm"
    assert status["latest_proposal"]["state"] == "APPLIED"
    assert status["counters"]["auto_applied"] == 1
    assert runtime_proposal.idempotency_key in store.load_idempotency_keys()


def test_autoplay_service_auto_applies_policy_eligible_scene_draft(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    store.add_draft(_autoplay_record(draft_id="scene-1", lane="scene", payload=dict(SCENE_DRAFT)))
    coordinator = FakeControlCoordinator()
    service = AutoplayService(
        store=store,
        panel_state=panel,
        doctor_fn=lambda settings: [FakeDoctorCheck("world_db", "WORKING", "ok")],
    )

    with patch.object(service, "_llm_health", return_value={"ok": True, "model": "local-model"}):
        with patch.object(service, "_recent_events", return_value=[]):
            with patch.object(service, "_control_coordinator", return_value=coordinator):
                status = service.tick(config=AutoplayRuntimeConfig(player_guid=1, start_watcher=False, llm_cooldown_seconds=0))

    assert [mode for mode, _proposal in coordinator.calls] == ["dry-run", "apply"]
    runtime_proposal = coordinator.calls[0][1]
    assert runtime_proposal.author.kind == "manual_admin"
    assert runtime_proposal.action.payload["native_action_kind"] == "player_chat_message"
    assert status["latest_proposal"]["state"] == "APPLIED"
    assert status["latest_autoplay"]["status"] == "applied"


def test_autoplay_service_parks_scene_draft_when_policy_blocks_risk(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    risky_scene = dict(SCENE_DRAFT)
    risky_scene["steps"] = [dict(SCENE_DRAFT["steps"][0], risk_level="medium")]
    store.add_draft(_autoplay_record(draft_id="scene-risk", lane="scene", payload=risky_scene))
    coordinator = FakeControlCoordinator()
    service = AutoplayService(
        store=store,
        panel_state=panel,
        doctor_fn=lambda settings: [FakeDoctorCheck("world_db", "WORKING", "ok")],
    )

    with patch.object(service, "_llm_health", return_value={"ok": True, "model": "local-model"}):
        with patch.object(service, "_recent_events", return_value=[]):
            with patch.object(service, "_control_coordinator", return_value=coordinator):
                status = service.tick(config=AutoplayRuntimeConfig(player_guid=1, start_watcher=False, llm_cooldown_seconds=0))

    assert [mode for mode, _proposal in coordinator.calls] == ["dry-run"]
    assert status["latest_proposal"]["state"] == "PARKED"
    assert status["latest_proposal"]["policy"]["status"] == "blocked"
    assert "risk_exceeds_policy:medium>low" in status["latest_proposal"]["policy"]["blockers"]


def test_autoplay_service_auto_publishes_eligible_quest_draft(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    quest = dict(QUEST_DRAFT)
    quest["quest"] = {
        **quest["quest"],
        "quest_id": 910777,
        "questgiver_entry": 240,
        "questgiver_name": "Marshal McBride",
        "title": "WM Test Bounty",
        "quest_description": "Cull them.",
        "objective_text": "Cull them.",
        "offer_reward_text": "Done.",
        "request_items_text": "Report back.",
        "grant_mode": "direct_grant",
    }
    quest["objective"] = {**quest["objective"], "target_name": "Wolf"}
    store.add_draft(_autoplay_record(draft_id="quest-1", lane="quest", payload=quest))
    coordinator = FakeControlCoordinator()
    service = AutoplayService(
        store=store,
        panel_state=panel,
        doctor_fn=lambda settings: [FakeDoctorCheck("world_db", "WORKING", "ok")],
    )

    with patch.object(service, "_llm_health", return_value={"ok": True, "model": "local-model"}):
        with patch.object(service, "_recent_events", return_value=[]):
            with patch.object(service, "_control_coordinator", return_value=coordinator):
                status = service.tick(config=AutoplayRuntimeConfig(player_guid=1, start_watcher=False, llm_cooldown_seconds=0))

    assert [mode for mode, _plan in coordinator.executor.calls] == ["dry-run", "apply"]
    plan = coordinator.executor.calls[0][1]
    assert [action.kind for action in plan.actions] == ["quest_publish", "quest_grant"]
    assert status["latest_proposal"]["state"] == "APPLIED"


def test_autoplay_service_chat_replies_through_native_action(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    coordinator = FakeControlCoordinator()
    service = AutoplayService(
        store=store,
        panel_state=panel,
        doctor_fn=lambda settings: [FakeDoctorCheck("world_db", "WORKING", "ok")],
    )

    with patch.object(service, "_llm_health", return_value={"ok": True, "model": "local-model"}):
        with patch.object(service, "_chat_world_context", return_value={"speaker": {"guid": 5408, "name": "Astel"}}):
            with patch.object(service, "_chat_reply", return_value={"message": "The road bends east.", "raw_content": "{}"}):
                with patch.object(service, "_control_coordinator", return_value=coordinator):
                    result = service.chat_once(
                        config=AutoplayRuntimeConfig(player_guid=5408, start_watcher=False),
                        message="What now?",
                    )

    assert result["ok"] is True
    assert [mode for mode, _proposal in coordinator.calls] == ["dry-run", "apply"]
    proposal = coordinator.calls[0][1]
    assert proposal.action.payload["native_action_kind"] == "player_chat_message"
    assert proposal.action.payload["payload"]["channel_name"] == "WM"
    assert proposal.action.payload["payload"]["message"] == "The road bends east."


def test_autoplay_service_forget_context_chat_resets_epoch_without_model(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    coordinator = FakeControlCoordinator()
    service = AutoplayService(
        store=store,
        panel_state=panel,
        doctor_fn=lambda settings: [FakeDoctorCheck("world_db", "WORKING", "ok")],
    )

    with patch.object(service, "_llm_health", return_value={"ok": True, "model": "local-model"}):
        with patch.object(service, "_chat_reply", side_effect=AssertionError("forget context should not call model")):
            with patch.object(service, "_control_coordinator", return_value=coordinator):
                result = service.chat_once(
                    config=AutoplayRuntimeConfig(player_guid=5408, start_watcher=False, llm_model="local-model"),
                    message="forget context",
                )

    status = store.load_status()
    assert result["ok"] is True
    assert result["reply"]["source"] == "context_reset"
    assert status["config"]["llm_chat_context_epoch"] == 1
    assert status["latest_chat_context_reset"]["actor_guid"] == 5408
    assert coordinator.calls[0][1].action.payload["payload"]["message"] == "Context forgotten. Fresh WM chat context epoch 1 is active."


def test_autoplay_service_chat_reply_failure_is_parked(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    service = AutoplayService(
        store=store,
        panel_state=panel,
        doctor_fn=lambda settings: [FakeDoctorCheck("world_db", "WORKING", "ok")],
    )

    with patch.object(service, "_llm_health", return_value={"ok": True, "model": "local-model"}):
        with patch.object(service, "_chat_world_context", return_value={"speaker": {"guid": 5408, "name": "Astel"}}):
            with patch.object(service, "_chat_reply", side_effect=RuntimeError("empty model response")):
                result = service.chat_once(
                    config=AutoplayRuntimeConfig(player_guid=5408, start_watcher=False),
                    message="Are you there?",
                )

    assert result["ok"] is False
    assert result["error"] == "reply_failed"
    assert store.load_status()["issues"][0]["reason"] == "chat_reply_failed"


def test_autoplay_service_replies_to_wm_chat_events(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    store.update_status(latest_proposal={"at": utc_now_iso(), "draft_id": "recent-draft"})
    coordinator = FakeControlCoordinator()
    event = WMEvent(
        event_class="observed",
        event_type="wm_chat",
        source="addon_log",
        source_event_key="towm-1",
        occurred_at=utc_now_iso(),
        player_guid=5408,
        subject_type="player",
        subject_entry=5408,
        event_value="Where should I go next?",
        event_id=77,
        metadata={"message": "Where should I go next?"},
    )
    service = AutoplayService(
        store=store,
        panel_state=panel,
        doctor_fn=lambda settings: [FakeDoctorCheck("world_db", "WORKING", "ok")],
    )

    with patch.object(service, "_llm_health", return_value={"ok": True, "model": "local-model"}):
        with patch.object(service, "_recent_events", return_value=[event]):
            with patch.object(service, "_chat_world_context", return_value={"speaker": {"guid": 5408, "name": "Astel"}}):
                with patch.object(service, "_chat_reply", return_value={"message": "Follow the smoke east.", "raw_content": "{}"}):
                    with patch.object(service, "_control_coordinator", return_value=coordinator):
                        status = service.tick(
                            config=AutoplayRuntimeConfig(
                                player_guid=5408,
                                start_watcher=False,
                                llm_cooldown_seconds=60,
                                llm_lanes=("scene", "action"),
                            )
                        )

    assert status["latest_generation"]["ok"] is True
    assert status["latest_generation"]["lane"] == "chat"
    assert status["latest_chat"]["reply"]["message"] == "Follow the smoke east."
    assert status["counters"]["chat_replies"] == 1
    assert [mode for mode, _proposal in coordinator.calls] == ["dry-run", "apply"]
    assert "towm-1" in store.load_seen_event_keys()


def test_autoplay_service_replies_to_wm_chat_from_any_player(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    coordinator = FakeControlCoordinator()
    event = WMEvent(
        event_class="observed",
        event_type="wm_chat",
        source="native_bridge",
        source_event_key="native_bridge:any-player-chat",
        occurred_at=utc_now_iso(),
        player_guid=7777,
        subject_type="player",
        subject_entry=7777,
        event_value="Do you know my name?",
        event_id=88,
        metadata={"message": "Do you know my name?", "player_name": "Astel"},
    )
    service = AutoplayService(
        store=store,
        panel_state=panel,
        doctor_fn=lambda settings: [FakeDoctorCheck("world_db", "WORKING", "ok")],
    )
    captured: dict[str, object] = {}

    def fake_chat_reply(**kwargs):
        captured.update(kwargs)
        return {"message": "Astel, I can hear you.", "raw_content": "{}"}

    with patch.object(service, "_llm_health", return_value={"ok": True, "model": "local-model"}):
        with patch.object(service, "_recent_events", return_value=[event]) as recent:
            with patch.object(service, "_chat_world_context", return_value={"speaker": {"guid": 7777, "name": "Astel"}}):
                with patch.object(service, "_chat_reply", side_effect=fake_chat_reply):
                    with patch.object(service, "_control_coordinator", return_value=coordinator):
                        status = service.tick(
                            config=AutoplayRuntimeConfig(
                                player_guid=5408,
                                start_watcher=False,
                                llm_cooldown_seconds=60,
                                llm_lanes=("scene", "action"),
                                llm_ambient_narration_enabled=False,
                            )
                        )

    assert status["latest_generation"]["ok"] is True
    recent.assert_called_once()
    assert recent.call_args.kwargs["player_guid"] is None
    assert captured["player_guid"] == 7777
    assert captured["world_context"] == {"speaker": {"guid": 7777, "name": "Astel"}}
    proposal = coordinator.calls[0][1]
    assert proposal.player.guid == 7777
    assert proposal.action.payload["payload"]["message"] == "Astel, I can hear you."
    assert "native_bridge:any-player-chat" in store.load_seen_event_keys()


def test_autoplay_service_forget_context_event_resets_epoch_and_marks_seen(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    coordinator = FakeControlCoordinator()
    event = WMEvent(
        event_class="observed",
        event_type="wm_chat",
        source="native_bridge",
        source_event_key="native_bridge:forget-context",
        occurred_at=utc_now_iso(),
        player_guid=5408,
        subject_type="player",
        subject_entry=5408,
        event_value="forget context",
        event_id=89,
        metadata={"message": "forget context", "player_name": "Astel"},
    )
    service = AutoplayService(
        store=store,
        panel_state=panel,
        doctor_fn=lambda settings: [FakeDoctorCheck("world_db", "WORKING", "ok")],
    )

    with patch.object(service, "_llm_health", return_value={"ok": True, "model": "local-model"}):
        with patch.object(service, "_recent_events", return_value=[event]):
            with patch.object(service, "_chat_reply", side_effect=AssertionError("forget context should not call model")):
                with patch.object(service, "_control_coordinator", return_value=coordinator):
                    status = service.tick(
                        config=AutoplayRuntimeConfig(player_guid=5408, start_watcher=False, llm_lanes=("chat",))
                    )

    assert status["latest_generation"]["ok"] is True
    assert status["latest_generation"]["reply"]["source"] == "context_reset"
    assert store.load_status()["config"]["llm_chat_context_epoch"] == 1
    assert "native_bridge:forget-context" in store.load_seen_event_keys()


def test_forget_context_event_works_when_llm_is_unavailable(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    coordinator = FakeControlCoordinator()
    event = WMEvent(
        event_class="observed",
        event_type="wm_chat",
        source="native_bridge",
        source_event_key="native_bridge:forget-context-offline",
        occurred_at=utc_now_iso(),
        player_guid=5408,
        subject_type="player",
        subject_entry=5408,
        event_value="forget context",
        event_id=90,
        metadata={"message": "forget context", "player_name": "Astel"},
    )
    service = AutoplayService(
        store=store,
        panel_state=panel,
        doctor_fn=lambda settings: [FakeDoctorCheck("soap", "FAIL", "down")],
    )

    with patch.object(service, "_llm_health", return_value={"ok": False, "model": "local-model", "error": "down"}):
        with patch.object(service, "_recent_events", return_value=[event]):
            with patch.object(service, "_control_coordinator", return_value=coordinator):
                status = service.tick(
                    config=AutoplayRuntimeConfig(player_guid=5408, start_watcher=False, llm_lanes=("chat",))
                )

    assert status["readiness"]["ok"] is False
    assert status["latest_generation"]["ok"] is True
    assert status["latest_generation"]["reply"]["source"] == "context_reset"
    assert status["config"]["llm_chat_context_epoch"] == 1


def test_chat_reply_is_sanitized_for_in_game_message():
    message = _sanitize_chat_reply("**Header**\n\n- Do this very long thing " + "x" * 200)

    assert "\n" not in message
    assert "**" not in message
    assert len(message) <= _CHAT_REPLY_MAX_CHARS
    assert _sanitize_chat_reply('"World Master here."') == "World Master here."


def test_long_chat_reply_is_split_into_in_game_parts():
    text = "World Master speaks. " * 60  # ~1260 chars, well over one packet
    sanitized = _sanitize_chat_reply(text)
    parts = _split_chat_message(sanitized)

    assert len(parts) > 1
    assert all(len(part) <= _CHAT_PART_LIMIT for part in parts)
    # short replies are delivered as a single part, unchanged
    assert _split_chat_message("All is well, traveler.") == ["All is well, traveler."]


def test_chat_reply_uses_text_schema_mode_and_short_output(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    panel.save_settings({"model": "local-model", "max_tokens": 2048, "schema_mode": "json_schema"})
    captured = {}

    class FakeChatClient:
        def __init__(self, settings):
            captured["settings"] = settings

        def generate_text(self, **kwargs):
            captured["request"] = kwargs
            return {"content": "{\"message\":\"The road bends east.\"}"}

    service = AutoplayService(store=store, panel_state=panel)

    with patch("wm.autoplay.service.LmStudioClient", FakeChatClient):
        reply = service._chat_reply(control_config={}, player_guid=5408, message="What now?")

    assert reply["message"] == "The road bends east."
    assert captured["settings"].schema_mode == "text"
    assert captured["settings"].max_tokens == 128
    assert captured["request"]["messages"][0]["role"] == "system"
    request_payload = json.loads(captured["request"]["messages"][1]["content"])
    assert request_payload["authoritative_player_identity"]["player_guid"] == 5408
    # The voice gets only the trimmed digest; the verb manifest is no longer sent.
    assert "wm_tools" not in request_payload
    assert set(request_payload["world_context"].keys()) == {"live_location", "perception", "recent_wm_chat"}


def test_qwen_chat_gets_larger_completion_budget():
    assert _chat_max_tokens(LmStudioSettings(model="qwen3.5-test", max_tokens=2048)) == 512
    assert _chat_max_tokens(LmStudioSettings(model="local-model", max_tokens=2048)) == 128


def test_chat_reply_uses_supplied_world_context(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    panel.save_settings({"model": "local-model"})
    captured = {}

    class FakeChatClient:
        def __init__(self, settings):
            captured["settings"] = settings

        def generate_text(self, **kwargs):
            captured["request"] = kwargs
            return {"content": "Hello, Astel."}

    service = AutoplayService(store=store, panel_state=panel)
    world_context = {
        "schema_version": "wm.autoplay.chat_world_context.v1",
        "speaker": {"guid": 5408, "name": "Astel"},
        "live_location": {"zone_name": "Westfall", "area_name": "Sentinel Hill", "fresh": True},
        "perception": {"source": "native_bridge_perception", "creature_count": 5, "gameobject_count": 1},
        "database": {"online_characters": [{"guid": 5408, "name": "Astel"}]},
    }

    with patch("wm.autoplay.service.LmStudioClient", FakeChatClient):
        reply = service._chat_reply(
            control_config={},
            player_guid=5408,
            message="Greet me by name.",
            world_context=world_context,
        )

    request_payload = json.loads(captured["request"]["messages"][1]["content"])
    assert reply["message"] == "Hello, Astel."
    # The voice receives the trimmed digest (location + ambient counts), not the
    # heavy sections; identity (incl. name) travels in authoritative_player_identity.
    assert request_payload["world_context"]["live_location"]["zone_name"] == "Westfall"
    assert request_payload["world_context"]["perception"]["creature_count"] == 5
    assert "database" not in request_payload["world_context"]
    assert request_payload["authoritative_player_identity"]["character_name"] == "Astel"


def test_chat_reply_answers_identity_from_authoritative_context(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    panel.save_settings({"model": "local-model"})

    class FakeChatClient:
        def __init__(self, settings):
            self.settings = settings

        def generate_text(self, **kwargs):
            raise AssertionError("identity questions should not call the model")

    service = AutoplayService(store=store, panel_state=panel)
    world_context = {
        "schema_version": "wm.autoplay.chat_world_context.v1",
        "speaker": {"guid": 5408, "name": "Astel"},
        "database": {"character_row": {"guid": 5408, "name": "Astel"}},
    }

    with patch("wm.autoplay.service.LmStudioClient", FakeChatClient):
        reply = service._chat_reply(
            control_config={},
            player_guid=5408,
            message="What is my character name?",
            world_context=world_context,
        )

    assert reply["message"] == "Astel"
    assert reply["source"] == "deterministic_fact"


def test_chat_reply_accepts_plain_text_from_local_model(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    panel.save_settings({"model": "local-model"})

    class FakeChatClient:
        def __init__(self, settings):
            self.settings = settings

        def generate_text(self, **kwargs):
            return {"content": "Follow the smoke east."}

    service = AutoplayService(store=store, panel_state=panel)

    with patch("wm.autoplay.service.LmStudioClient", FakeChatClient):
        reply = service._chat_reply(control_config={}, player_guid=5408, message="What now?")

    assert reply["message"] == "Follow the smoke east."
    assert reply["raw_content"] == "Follow the smoke east."


def test_chat_reply_guards_unsuitable_channel_output(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    panel.save_settings({"model": "local-model"})

    class FakeChatClient:
        def __init__(self, settings):
            self.settings = settings

        def generate_text(self, **kwargs):
            return {"content": "I grope your breasts."}

    service = AutoplayService(store=store, panel_state=panel)

    with patch("wm.autoplay.service.LmStudioClient", FakeChatClient):
        reply = service._chat_reply(control_config={}, player_guid=5408, message="How would you respond?")

    assert reply["message"] == "I will keep this to the world at hand. What do you want to do next?"


def test_chat_reply_retries_after_empty_local_model_response(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    panel.save_settings({"model": "local-model"})
    calls = []

    class FakeChatClient:
        def __init__(self, settings):
            self.settings = settings

        def generate_text(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise RuntimeError("LM Studio response message content was empty.")
            return {"content": "I am listening."}

    service = AutoplayService(store=store, panel_state=panel)

    with patch("wm.autoplay.service.LmStudioClient", FakeChatClient):
        reply = service._chat_reply(control_config={}, player_guid=5408, message="Hello?")

    assert len(calls) == 2
    assert reply["message"] == "I am listening."


def test_chat_reply_falls_back_after_repeated_empty_local_model_response(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    panel.save_settings({"model": "local-model"})

    class FakeChatClient:
        def __init__(self, settings):
            self.settings = settings

        def generate_text(self, **kwargs):
            raise RuntimeError("LM Studio response message content was empty.")

    service = AutoplayService(store=store, panel_state=panel)

    with patch("wm.autoplay.service.LmStudioClient", FakeChatClient):
        reply = service._chat_reply(control_config={}, player_guid=5408, message="Hello?")

    assert reply["source"] == "llm_fallback"
    assert reply["model"] == "local-model"
    assert "local model returned no words" in reply["message"]


def test_chat_lane_is_valid_for_direct_player_chat_only():
    assert _normalize_lanes("chat") == ["chat"]


def test_merged_control_config_runtime_model_overrides_stale_command():
    merged = _merged_control_config(
        config=AutoplayRuntimeConfig(llm_model="new-model", llm_base_url="http://new/v1"),
        status={"config": {"llm_model": "status-model", "llm_base_url": "http://status/v1"}},
        command={"config": {"llm_model": "command-model", "llm_base_url": "http://command/v1"}},
    )

    assert merged["llm_model"] == "new-model"
    assert merged["llm_base_url"] == "http://new/v1"


def test_run_forever_uses_panel_model_when_no_cli_model(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    panel.save_settings({"model": "panel-model", "base_url": "http://panel/v1"})
    store.configure({"llm_model": "old-command-model", "llm_base_url": "http://old/v1"})
    service = AutoplayService(store=store, panel_state=panel, doctor_fn=lambda settings: [])

    code = service.run_forever(
        config=AutoplayRuntimeConfig(
            player_guid=5408,
            start_watcher=False,
            llm_enabled=False,
            llm_model=None,
            llm_base_url=None,
        ),
        once=True,
    )

    assert code == 0
    command_config = store.load_command()["config"]
    assert command_config["llm_model"] == "panel-model"
    assert command_config["llm_base_url"] == "http://panel/v1"


def test_paused_tick_preserves_chat_context_reset_from_command(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    store.set_paused(True)
    store.reset_chat_context(actor_guid=5408, source="panel")
    service = AutoplayService(store=store, panel_state=panel, doctor_fn=lambda settings: [])

    status = service.tick(config=AutoplayRuntimeConfig(player_guid=5408, start_watcher=False, llm_enabled=False))

    assert status["paused"] is True
    assert status["config"]["llm_chat_context_epoch"] == 1
    assert store.load_status()["config"]["llm_chat_context_epoch"] == 1


def test_status_summary_includes_selected_model():
    summary = status_summary({
        "status": "running",
        "running": True,
        "paused": False,
        "active_session": {"character_guid": 5408},
        "readiness": {"ok": True},
        "llm": {"ok": True, "model": "visible-model"},
        "config": {"llm_enabled": True, "llm_chat_enabled": True, "llm_lanes": ["chat"]},
        "counters": {},
    })

    assert "model=visible-model" in summary


from wm.autoplay.intent import (
    default_verb_modes,
    resolve_verb_modes,
    IntentRejection,
    compile_intent,
    is_affirmation,
    is_negation,
)
from wm.autoplay.tools import autoplay_tool_manifest
from wm.autoplay.intent_extract import extract_chat_intent
from wm.autoplay.world_context import _live_location_from_presence
from wm.autoplay.world_context import _perception_from_row
from wm.autoplay.service import _chat_identity_facts


def test_default_verb_modes_low_auto_medium_high_confirm():
    modes = default_verb_modes()
    assert modes["player_restore_health_power"] == "auto"
    assert modes["player_apply_aura"] == "confirm"
    assert "player_teleport" not in modes


def test_resolve_verb_modes_applies_overrides_and_ignores_unimplemented():
    resolved = resolve_verb_modes({"player_apply_aura": "auto", "player_teleport": "auto"})
    assert resolved["player_apply_aura"] == "auto"
    assert "player_teleport" not in resolved
    assert resolved["player_restore_health_power"] == "auto"


def test_manifest_excludes_off_verbs_and_lists_modes():
    modes = {"player_restore_health_power": "auto", "player_apply_aura": "off"}
    manifest = autoplay_tool_manifest(modes=modes)
    verbs = {item["kind"]: item for item in manifest["native_actions"]}
    assert "player_apply_aura" not in verbs
    assert verbs["player_restore_health_power"]["mode"] == "auto"


def test_manifest_includes_payload_arg_contracts():
    manifest = autoplay_tool_manifest(modes={"creature_spawn": "confirm"})
    spawn = {item["kind"]: item for item in manifest["native_actions"]}["creature_spawn"]
    # creature_spawn now accepts a creature_entry OR a creature_name (resolved by WM).
    assert spawn["required_any"] == ["creature_entry", "creature_name"]
    assert "duration_ms" in spawn["optional"]


class _FakeIntentClient:
    def __init__(self, parsed):
        self._parsed = parsed
        self.calls = []

    def generate_json(self, **kwargs):
        self.calls.append(kwargs)
        return {"parsed": self._parsed}


def _spawn_manifest():
    return autoplay_tool_manifest(modes={"creature_spawn": "confirm"})


def test_extract_chat_intent_returns_typed_verb_when_act_true():
    client = _FakeIntentClient(
        {"act": True, "verb": "creature_spawn", "args": {"creature_entry": 299}, "reason": "player asked"}
    )
    intent = extract_chat_intent(
        client=client,
        player_guid=5408,
        message="spawn a defias footpad",
        manifest=_spawn_manifest(),
    )
    assert intent == {"verb": "creature_spawn", "args": {"creature_entry": 299}, "reason": "player asked"}


def test_extract_chat_intent_returns_none_when_act_false():
    client = _FakeIntentClient({"act": False, "verb": "", "args": {}, "reason": "just chatting"})
    intent = extract_chat_intent(
        client=client, player_guid=5408, message="hello there", manifest=_spawn_manifest()
    )
    assert intent is None


def test_extract_chat_intent_rejects_verb_outside_catalog():
    client = _FakeIntentClient(
        {"act": True, "verb": "player_teleport", "args": {}, "reason": "x"}
    )
    intent = extract_chat_intent(
        client=client, player_guid=5408, message="teleport me", manifest=_spawn_manifest()
    )
    assert intent is None


def test_extract_chat_intent_swallows_client_errors():
    class _BoomClient:
        def generate_json(self, **kwargs):
            raise RuntimeError("LM Studio offline")

    intent = extract_chat_intent(
        client=_BoomClient(), player_guid=5408, message="spawn a wolf", manifest=_spawn_manifest()
    )
    assert intent is None


def test_live_location_from_presence_maps_online_row():
    row = {
        "PlayerGUID": 5408, "Online": 1, "MapID": 0, "ZoneID": 1519, "AreaID": 1519,
        "ZoneName": "Stormwind City", "AreaName": "Stormwind City",
        "PosX": -8913.0, "PosY": 554.6, "PosZ": 93.7, "Orientation": 0.6,
        "Level": 13, "HealthPct": 100, "InCombat": 0, "UpdatedAt": "2026-05-29 12:00:00",
    }
    live = _live_location_from_presence(row)
    assert live["source"] == "native_bridge_presence"
    assert live["fresh"] is True
    assert live["zone_id"] == 1519
    assert live["zone_name"] == "Stormwind City"
    assert live["x"] == -8913.0
    assert live["in_combat"] is False


def test_live_location_from_presence_offline_is_not_fresh():
    row = {"PlayerGUID": 5408, "Online": 0, "MapID": 0, "ZoneID": 40, "PosX": 1.0}
    live = _live_location_from_presence(row)
    assert live["fresh"] is False
    assert live["online"] is False


def test_live_location_from_presence_unavailable_without_row():
    live = _live_location_from_presence(None)
    assert live["source"] == "unavailable"
    assert live["fresh"] is False


def test_perception_from_row_is_counts_only_ambient():
    row = {
        "PlayerGUID": 5408, "MapID": 0, "ZoneID": 1519, "AreaID": 1519,
        "CreatureCount": 7, "GameObjectCount": 2,
        "PayloadJSON": json.dumps({"nearby_creatures": [{"name": "x"}]}),
        "UpdatedAt": "2026-05-29 12:00:00",
    }
    perception = _perception_from_row(row)
    assert perception["source"] == "native_bridge_perception"
    assert perception["creature_count"] == 7
    assert perception["gameobject_count"] == 2
    assert perception["zone_id"] == 1519
    # ambient block carries counts only, never per-entity detail
    assert "nearest_creatures" not in perception
    assert "nearest_gameobjects" not in perception
    assert "detail_note" in perception


def test_perception_from_row_unavailable_without_row():
    perception = _perception_from_row(None)
    assert perception["source"] == "unavailable"


def test_identity_facts_prefer_live_location_over_stale_db():
    context = {
        "speaker": {"guid": 5408, "name": "Astel"},
        "database": {
            "character_row": {
                "name": "Astel", "level": 13, "class": "Paladin",
                "map": 0, "zone": 40,
            }
        },
        "live_location": {
            "source": "native_bridge_snapshot", "fresh": True,
            "map_id": 0, "zone_id": 1519, "area_id": 1519,
            "x": -8913.0, "y": 554.6, "z": 93.7, "o": 0.6,
        },
    }
    facts = _chat_identity_facts(context, player_guid=5408)
    assert facts["zone"] == "1519"
    assert facts["location_source"] == "native_bridge_snapshot"
    assert facts["location_fresh"] is True
    assert facts["position"]["x"] == -8913.0
    assert facts["level"] == "13"


def test_identity_facts_mark_unavailable_location_without_snapshot():
    context = {
        "speaker": {"guid": 5408, "name": "Astel"},
        "database": {"character_row": {"name": "Astel", "map": 0, "zone": 40}},
        "live_location": {"source": "unavailable", "fresh": False},
    }
    facts = _chat_identity_facts(context, player_guid=5408)
    assert facts["location_source"] == "unavailable"
    assert facts["location_fresh"] is False
    assert facts["position"] is None
    # falls back to the stale characters-row zone only as a last resort
    assert facts["zone"] == "40"


def test_compile_intent_rejects_off_verb():
    out = compile_intent(player_guid=5408, verb="player_teleport", args={}, modes={})
    assert isinstance(out, IntentRejection)


def test_compile_intent_rejects_missing_required_args():
    out = compile_intent(player_guid=5408, verb="player_add_item", args={}, modes={"player_add_item": "confirm"})
    assert isinstance(out, IntentRejection)


def test_compile_intent_builds_proposal_with_locked_guid():
    out = compile_intent(
        player_guid=5408,
        verb="player_restore_health_power",
        args={"health_percent": 100},
        modes={"player_restore_health_power": "auto"},
    )
    assert not isinstance(out, IntentRejection)
    assert out.proposal.player.guid == 5408
    assert out.mode == "auto"
    assert out.risk == "low"


def test_affirmation_and_negation():
    assert is_affirmation("yes") and is_affirmation("Do it!") and is_affirmation("go ahead")
    assert is_negation("no") and is_negation("cancel") and is_negation("forget it")
    assert not is_affirmation("what can you do?")
    assert not is_negation("spawn a wolf")


def test_pending_intent_roundtrip_and_expiry(tmp_path):
    store = AutoplayStateStore(root=tmp_path)
    store.set_pending_intent(5408, {"verb": "creature_spawn", "summary": "spawn a wolf"}, ttl_seconds=120)
    loaded = store.load_pending_intent(5408)
    assert loaded and loaded["verb"] == "creature_spawn"
    store.set_pending_intent(5408, {"verb": "x"}, ttl_seconds=0)
    assert store.load_pending_intent(5408) is None
    store.set_pending_intent(5408, {"verb": "y"}, ttl_seconds=120)
    store.clear_pending_intent(5408, reason="rejected")
    assert store.load_pending_intent(5408) is None
