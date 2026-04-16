import json
import contextlib
import io
from pathlib import Path
import unittest
from unittest.mock import patch

from wm.config import Settings
from wm.reactive.install_bounty import main
from wm.reactive.install_bounty import ReactiveBountyInstaller
from wm.reactive.models import ReactiveQuestRule
from wm.reactive.templates import list_reactive_bounty_templates
from wm.reactive.templates import resolve_reactive_bounty_template_path


class _DummyClient:
    def query(self, *, host: str, port: int, user: str, password: str, database: str, sql: str):
        del host, port, user, password
        if database == "acore_world" and sql.lstrip().upper().startswith(("INSERT ", "UPDATE ", "DELETE ")):
            return []
        if database == "acore_world" and "FROM quest_template" in sql:
            return []
        if database == "acore_world" and "FROM creature_queststarter" in sql:
            return []
        if database == "acore_world" and "FROM creature_questender" in sql:
            return []
        if database == "acore_world" and "FROM quest_template_addon" in sql:
            return []
        raise AssertionError(f"Unexpected SQL in {database}: {sql}")


class _ExistingQuestClient(_DummyClient):
    def query(self, *, host: str, port: int, user: str, password: str, database: str, sql: str):
        del host, port, user, password
        if database == "acore_world" and sql.lstrip().upper().startswith(("INSERT ", "UPDATE ", "DELETE ")):
            return []
        if database == "acore_world" and "FROM quest_template WHERE ID = 910000" in sql:
            return [{"ID": "910000", "LogTitle": "Bounty: Kobold Vermin"}]
        if database == "acore_world" and "FROM creature_queststarter" in sql:
            return []
        if database == "acore_world" and "FROM creature_questender" in sql:
            return [{"id": "197"}]
        if database == "acore_world" and "FROM quest_template_addon" in sql:
            return [{"ID": "910000", "SpecialFlags": "1"}]
        raise AssertionError(f"Unexpected SQL in {database}: {sql}")


class FakeReactiveStore:
    def __init__(self) -> None:
        self.upserted = []

    def upsert_rule(self, rule: ReactiveQuestRule) -> None:
        self.upserted.append(rule)


class FakeSlotAllocator:
    def __init__(self) -> None:
        self.last_kwargs = None
        self.peeked_entity_type = None
        self.allocated = []
        self.released = []

    def ensure_slot_prepared(self, **kwargs):
        self.last_kwargs = kwargs
        return object()

    def peek_next_free_slot(self, *, entity_type: str):
        self.peeked_entity_type = entity_type
        return type("Slot", (), {"reserved_id": 910001})()

    def allocate_next_free_slot(self, **kwargs):
        self.allocated.append(kwargs)
        return type("Slot", (), {"reserved_id": 910001})()

    def release_slot(self, **kwargs):
        self.released.append(kwargs)
        return None


class FakePreflight:
    def __init__(self) -> None:
        self.compatibility = {
            "quest_description_supported": True,
            "objective_text_supported": True,
            "offer_reward_text_supported": True,
            "request_items_text_supported": True,
        }


class FakeQuestPublisher:
    def __init__(self, *, snapshot: dict | None = None) -> None:
        self.calls = []
        self.snapshot = snapshot or {
            "quest_template": [],
            "creature_queststarter": [],
            "creature_questender": [],
            "quest_template_addon": [],
            "quest_offer_reward": [],
            "quest_request_items": [],
        }

    def capture_snapshot_preview(self, draft):
        del draft
        return self.snapshot

    def preflight(self, draft):
        del draft
        return FakePreflight()

    def publish(self, *, draft, mode: str, **kwargs):
        self.publish_kwargs = kwargs
        self.calls.append((draft, mode))
        class Result:
            applied = mode == "apply"
            def to_dict(self_nonlocal):
                return {
                    "applied": mode == "apply",
                    "draft": draft.to_dict(),
                    "preflight": {"ok": True},
                }
        return Result()


class FakeQuestPublisherActiveSlot:
    def __init__(self, *, snapshot: dict | None = None) -> None:
        self.calls = []
        self.snapshot = snapshot or {
            "quest_template": [
                {
                    "ID": "910000",
                    "LogTitle": "Bounty: Defias Bandit",
                    "LogDescription": "Drive back 4 Defias Bandit, then report to Guard Thomas.",
                    "QuestDescription": "Your recent assault on Defias Bandit has drawn attention. Thin their numbers further, then report to Guard Thomas.",
                    "QuestCompletionLog": "Drive back 4 Defias Bandit, then report to Guard Thomas.",
                    "ObjectiveText1": "Slay 4 Defias Bandit.",
                    "RewardItem1": "0",
                    "RewardAmount1": "0",
                    "RewardSpell": "0",
                    "RewardDisplaySpell": "0",
                    "RequiredNpcOrGo1": "116",
                    "RequiredNpcOrGoCount1": "4",
                    "RewardMoney": "1200",
                }
            ],
            "creature_queststarter": [],
            "creature_questender": [{"id": "261"}],
            "quest_template_addon": [{"ID": "910000", "SpecialFlags": "1"}],
            "quest_offer_reward": [
                {"ID": "910000", "RewardText": "Guard Thomas nods as you report in. The pressure from Defias Bandit eases for now, but stay ready."}
            ],
            "quest_request_items": [
                {"ID": "910000", "CompletionText": "Drive back 4 Defias Bandit, then report to Guard Thomas."}
            ],
        }

    def capture_snapshot_preview(self, draft):
        del draft
        return self.snapshot

    def preflight(self, draft):
        del draft
        return FakePreflight()

    def publish(self, *, draft, mode: str, **kwargs):
        self.publish_kwargs = kwargs
        self.calls.append((draft, mode))
        class Result:
            applied = False
            def to_dict(self_nonlocal):
                return {
                    "applied": False,
                    "draft": draft.to_dict(),
                    "preflight": {
                        "ok": False,
                        "issues": [
                            {
                                "path": "reserved_slot.status",
                                "message": "Quest slot 910000 is already active. Use `wm.quests.edit_live` for in-place changes, or rollback / retire the old quest before publishing a new draft into this slot.",
                                "severity": "error",
                            }
                        ],
                    },
                    "sql_plan": {
                        "statements": [
                            "-- refresh active quest",
                            "DELETE FROM quest_template WHERE ID = 910000;",
                            "INSERT INTO quest_template (ID, LogTitle) VALUES (910000, 'Bounty: Defias Bandit');",
                        ]
                    },
                }
        return Result()


class FakeResolveResult:
    def __init__(self, *, entry: int, name: str, profile) -> None:
        self.entry = entry
        self.name = name
        self.profile = profile


class FakeResolver:
    def resolve(self, *, entry: int | None = None, name: str | None = None):
        del name
        if entry == 197:
            return FakeResolveResult(
                entry=197,
                name="Marshal McBride",
                profile=type("Profile", (), {"entry": 197, "name": "Marshal McBride", "level_max": 5, "mechanical_type": "HUMANOID", "family": None})(),
            )
        if entry == 240:
            return FakeResolveResult(
                entry=240,
                name="Marshal Dughan",
                profile=type("Profile", (), {"entry": 240, "name": "Marshal Dughan", "level_max": 10, "mechanical_type": "HUMANOID", "family": None})(),
            )
        if entry == 261:
            return FakeResolveResult(
                entry=261,
                name="Guard Thomas",
                profile=type("Profile", (), {"entry": 261, "name": "Guard Thomas", "level_max": 12, "mechanical_type": "HUMANOID", "family": None})(),
            )
        if entry == 116:
            return FakeResolveResult(
                entry=116,
                name="Defias Bandit",
                profile=type("Profile", (), {"entry": 116, "name": "Defias Bandit", "level_max": 9, "mechanical_type": "HUMANOID", "family": None})(),
            )
        if entry == 285:
            return FakeResolveResult(
                entry=285,
                name="Murloc",
                profile=type("Profile", (), {"entry": 285, "name": "Murloc", "level_max": 7, "mechanical_type": "HUMANOID", "family": None})(),
            )
        return FakeResolveResult(
            entry=6,
            name="Kobold Vermin",
            profile=type("Profile", (), {"entry": 6, "name": "Kobold Vermin", "level_max": 4, "mechanical_type": "HUMANOID", "family": None})(),
        )

    def fetch_template_defaults_for_questgiver(self, questgiver_entry: int) -> dict[str, object]:
        del questgiver_entry
        return {"QuestType": 2}


class ReactiveInstallTests(unittest.TestCase):
    def test_install_builds_direct_grant_turnin_only_quest(self) -> None:
        installer = ReactiveBountyInstaller(
            client=_DummyClient(),  # type: ignore[arg-type]
            settings=Settings(event_default_reward_money_copper=1200),
            reactive_store=FakeReactiveStore(),  # type: ignore[arg-type]
            slot_allocator=FakeSlotAllocator(),  # type: ignore[arg-type]
            quest_publisher=FakeQuestPublisher(),  # type: ignore[arg-type]
            resolver=FakeResolver(),  # type: ignore[arg-type]
        )
        reloaded_quest_ids: list[int] = []
        installer._reload_runtime_for_quest = lambda *, rule: reloaded_quest_ids.append(int(rule.quest_id))  # type: ignore[method-assign]
        rule = ReactiveQuestRule(
            rule_key="reactive_bounty:kobold_vermin",
            is_active=True,
            player_guid_scope=5406,
            subject_type="creature",
            subject_entry=6,
            trigger_event_type="kill",
            kill_threshold=4,
            window_seconds=120,
            quest_id=910000,
            turn_in_npc_entry=197,
            grant_mode="direct_quest_add",
            post_reward_cooldown_seconds=60,
            metadata={},
            notes=[],
        )

        result = installer.install(rule=rule, mode="apply")
        draft = installer.quest_publisher.calls[0][0]

        self.assertTrue(result.quest_publish["applied"])
        self.assertEqual(draft.grant_mode, "direct_quest_add")
        self.assertIsNone(draft.start_npc_entry)
        self.assertEqual(draft.end_npc_entry, 197)
        self.assertEqual(int(draft.template_defaults["SpecialFlags"]), 1)
        self.assertEqual(reloaded_quest_ids, [910000])

    def test_install_refreshes_active_slot_in_place_when_publish_preflight_blocks(self) -> None:
        installer = ReactiveBountyInstaller(
            client=_ExistingQuestClient(),  # type: ignore[arg-type]
            settings=Settings(),
            reactive_store=FakeReactiveStore(),  # type: ignore[arg-type]
            slot_allocator=FakeSlotAllocator(),  # type: ignore[arg-type]
            quest_publisher=FakeQuestPublisherActiveSlot(),  # type: ignore[arg-type]
            resolver=FakeResolver(),  # type: ignore[arg-type]
        )
        rule = ReactiveQuestRule(
            rule_key="reactive_bounty:template:defias_bandit",
            is_active=True,
            player_guid_scope=5406,
            subject_type="creature",
            subject_entry=116,
            trigger_event_type="kill",
            kill_threshold=4,
            window_seconds=300,
            quest_id=910000,
            turn_in_npc_entry=261,
            grant_mode="direct_quest_add",
            post_reward_cooldown_seconds=60,
            metadata={
                "objective_target_name": "Defias Bandits",
                "quest_title": "Bounty: Defias Bandits",
            },
            notes=[],
        )

        result = installer.install(rule=rule, mode="apply")

        self.assertTrue(result.quest_publish["applied"])
        self.assertTrue(result.quest_publish["live_refresh_applied"])

    def test_install_applies_plural_target_name_overrides_to_reactive_quest_text(self) -> None:
        quest_publisher = FakeQuestPublisher()
        installer = ReactiveBountyInstaller(
            client=_DummyClient(),  # type: ignore[arg-type]
            settings=Settings(),
            reactive_store=FakeReactiveStore(),  # type: ignore[arg-type]
            slot_allocator=FakeSlotAllocator(),  # type: ignore[arg-type]
            quest_publisher=quest_publisher,  # type: ignore[arg-type]
            resolver=FakeResolver(),  # type: ignore[arg-type]
        )
        rule = ReactiveQuestRule(
            rule_key="reactive_bounty:template:defias_bandit",
            is_active=True,
            player_guid_scope=5406,
            subject_type="creature",
            subject_entry=116,
            trigger_event_type="kill",
            kill_threshold=4,
            window_seconds=300,
            quest_id=910000,
            turn_in_npc_entry=261,
            grant_mode="direct_quest_add",
            post_reward_cooldown_seconds=60,
            metadata={
                "objective_target_name": "Defias Bandits",
                "quest_title": "Bounty: Defias Bandits",
            },
            notes=[],
        )

        installer.install(rule=rule, mode="apply")
        draft = quest_publisher.calls[0][0]

        self.assertEqual(draft.title, "Bounty: Defias Bandits")
        self.assertEqual(draft.objective.target_name, "Defias Bandits")
        self.assertIn("Defias Bandits", draft.objective_text)

    def test_install_applies_item_and_spell_reward_overrides(self) -> None:
        quest_publisher = FakeQuestPublisher()
        installer = ReactiveBountyInstaller(
            client=_DummyClient(),  # type: ignore[arg-type]
            settings=Settings(),
            reactive_store=FakeReactiveStore(),  # type: ignore[arg-type]
            slot_allocator=FakeSlotAllocator(),  # type: ignore[arg-type]
            quest_publisher=quest_publisher,  # type: ignore[arg-type]
            resolver=FakeResolver(),  # type: ignore[arg-type]
        )
        rule = ReactiveQuestRule(
            rule_key="reactive_bounty:template:murloc",
            is_active=True,
            player_guid_scope=5406,
            subject_type="creature",
            subject_entry=285,
            trigger_event_type="kill",
            kill_threshold=5,
            window_seconds=30,
            quest_id=910000,
            turn_in_npc_entry=240,
            grant_mode="direct_quest_add",
            post_reward_cooldown_seconds=60,
            metadata={
                "objective_target_name": "Murlocs",
                "quest_title": "Bounty: Murlocs",
                "reward_item_entry": 45574,
                "reward_item_name": "Stormwind Tabard",
                "reward_item_count": 1,
                "reward_xp_difficulty": 4,
                "reward_spell_id": 22888,
                "reward_spell_display_id": 22888,
                "reward_reputations": [{"faction_id": 72, "value": 75}],
                "subject_name_prefix": "Murloc",
            },
            notes=[],
        )

        installer.install(rule=rule, mode="apply")
        draft = quest_publisher.calls[0][0]

        self.assertEqual(draft.reward.reward_item_entry, 45574)
        self.assertEqual(draft.reward.reward_item_name, "Stormwind Tabard")
        self.assertEqual(draft.reward.reward_xp_difficulty, 4)
        self.assertEqual(draft.reward.reward_spell_id, 22888)
        self.assertEqual(draft.reward.reward_spell_display_id, 22888)
        self.assertEqual(draft.reward.reward_reputations[0].faction_id, 72)
        self.assertEqual(draft.reward.reward_reputations[0].value, 75)

    def test_install_dry_run_allows_free_slot_preview_without_mutating_slot(self) -> None:
        quest_publisher = FakeQuestPublisher()
        installer = ReactiveBountyInstaller(
            client=_DummyClient(),  # type: ignore[arg-type]
            settings=Settings(),
            reactive_store=FakeReactiveStore(),  # type: ignore[arg-type]
            slot_allocator=FakeSlotAllocator(),  # type: ignore[arg-type]
            quest_publisher=quest_publisher,  # type: ignore[arg-type]
            resolver=FakeResolver(),  # type: ignore[arg-type]
        )
        rule = ReactiveQuestRule(
            rule_key="reactive_bounty:template:murloc",
            is_active=True,
            player_guid_scope=5406,
            subject_type="creature",
            subject_entry=285,
            trigger_event_type="kill",
            kill_threshold=2,
            window_seconds=120,
            quest_id=910001,
            turn_in_npc_entry=240,
            grant_mode="direct_quest_add",
            post_reward_cooldown_seconds=60,
            metadata={},
            notes=[],
        )

        result = installer.install(rule=rule, mode="dry-run")

        self.assertFalse(result.quest_publish["applied"])
        self.assertEqual(quest_publisher.publish_kwargs, {"allow_free_reserved_slot_preview": True})
        self.assertIn("Would stage and publish", result.notes[-1])

    def test_cli_accepts_plural_target_name_overrides(self) -> None:
        captured_rule: ReactiveQuestRule | None = None

        class FakeInstaller:
            def __init__(self, **kwargs) -> None:
                del kwargs

            def install(self, *, rule: ReactiveQuestRule, mode: str):
                nonlocal captured_rule
                captured_rule = rule

                class Result:
                    def __init__(self) -> None:
                        self.mode = mode
                        self.rule = rule.to_dict()
                        self.quest_exists = False
                        self.quest_matches_reactive_shape = False
                        self.quest_publish = None
                        self.notes = []

                    def to_dict(self_nonlocal):
                        return {
                            "mode": self_nonlocal.mode,
                            "rule": self_nonlocal.rule,
                            "quest_exists": self_nonlocal.quest_exists,
                            "quest_matches_reactive_shape": self_nonlocal.quest_matches_reactive_shape,
                            "quest_publish": self_nonlocal.quest_publish,
                            "notes": self_nonlocal.notes,
                        }

                return Result()

        with (
            patch("wm.reactive.install_bounty.Settings.from_env", return_value=Settings()),
            patch("wm.reactive.install_bounty.MysqlCliClient", return_value=object()),
            patch("wm.reactive.install_bounty.ReactiveBountyInstaller", FakeInstaller),
            patch("wm.reactive.install_bounty.ReactiveQuestStore") as reactive_store_cls,
            patch("wm.reactive.install_bounty.LiveCreatureResolver") as resolver_cls,
        ):
            reactive_store_cls.return_value.fetch_character_name.return_value = "Jecia"
            resolver_cls.return_value.resolve.side_effect = [
                FakeResolveResult(
                    entry=116,
                    name="Defias Bandit",
                    profile=type("Profile", (), {"entry": 116, "name": "Defias Bandit", "level_max": 9, "mechanical_type": "HUMANOID", "family": None})(),
                ),
                FakeResolveResult(
                    entry=261,
                    name="Guard Thomas",
                    profile=type("Profile", (), {"entry": 261, "name": "Guard Thomas", "level_max": 12, "mechanical_type": "HUMANOID", "family": None})(),
                ),
            ]

            exit_code = main(
                [
                    "--rule-key",
                    "reactive_bounty:template:defias_bandit",
                    "--player-guid",
                    "5406",
                    "--subject-entry",
                    "116",
                    "--quest-id",
                    "910000",
                    "--turn-in-npc-entry",
                    "261",
                    "--window-seconds",
                    "300",
                    "--objective-target-name",
                    "Defias Bandits",
                    "--quest-title",
                    "Bounty: Defias Bandits",
                    "--mode",
                    "dry-run",
                    "--summary",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertIsNotNone(captured_rule)
        assert captured_rule is not None
        self.assertEqual(captured_rule.metadata["objective_target_name"], "Defias Bandits")
        self.assertEqual(captured_rule.metadata["quest_title"], "Bounty: Defias Bandits")
        self.assertEqual(captured_rule.quest.title, "Bounty: Defias Bandits")

    def test_cli_template_loads_known_bounty_defaults(self) -> None:
        captured_rule: ReactiveQuestRule | None = None
        fake_slot_allocator = FakeSlotAllocator()

        class FakeInstaller:
            def __init__(self, **kwargs) -> None:
                del kwargs

            def install(self, *, rule: ReactiveQuestRule, mode: str):
                nonlocal captured_rule
                captured_rule = rule

                class Result:
                    def __init__(self) -> None:
                        self.mode = mode
                        self.rule = rule.to_dict()
                        self.quest_exists = False
                        self.quest_matches_reactive_shape = False
                        self.quest_publish = None
                        self.notes = []

                    def to_dict(self_nonlocal):
                        return {
                            "mode": self_nonlocal.mode,
                            "rule": self_nonlocal.rule,
                            "quest_exists": self_nonlocal.quest_exists,
                            "quest_matches_reactive_shape": self_nonlocal.quest_matches_reactive_shape,
                            "quest_publish": self_nonlocal.quest_publish,
                            "notes": self_nonlocal.notes,
                        }

                return Result()

        template_path = Path("artifacts") / "test_reactive_bounty_template.json"
        template_path.parent.mkdir(parents=True, exist_ok=True)
        template_path.write_text(
            json.dumps(
                {
                    "rule_key": "reactive_bounty:template:defias_bandit",
                    "subject_entry": 116,
                    "turn_in_npc_entry": 261,
                    "kill_threshold": 4,
                    "window_seconds": 300,
                    "post_reward_cooldown_seconds": 60,
                    "objective_target_name": "Defias Bandits",
                    "quest_title": "Bounty: Defias Bandits",
                }
            ),
            encoding="utf-8",
        )

        try:
            with (
                patch("wm.reactive.install_bounty.Settings.from_env", return_value=Settings()),
                patch("wm.reactive.install_bounty.MysqlCliClient", return_value=object()),
                patch("wm.reactive.install_bounty.ReactiveBountyInstaller", FakeInstaller),
                patch("wm.reactive.install_bounty.ReservedSlotDbAllocator", return_value=fake_slot_allocator),
                patch("wm.reactive.install_bounty.ReactiveQuestStore") as reactive_store_cls,
                patch("wm.reactive.install_bounty.LiveCreatureResolver") as resolver_cls,
            ):
                reactive_store_cls.return_value.fetch_character_name.return_value = "Jecia"
                reactive_store_cls.return_value.get_rule_by_key.return_value = None
                resolver_cls.return_value.resolve.side_effect = [
                    FakeResolveResult(
                        entry=116,
                        name="Defias Bandit",
                        profile=type("Profile", (), {"entry": 116, "name": "Defias Bandit", "level_max": 9, "mechanical_type": "HUMANOID", "family": None})(),
                    ),
                    FakeResolveResult(
                        entry=261,
                        name="Guard Thomas",
                        profile=type("Profile", (), {"entry": 261, "name": "Guard Thomas", "level_max": 12, "mechanical_type": "HUMANOID", "family": None})(),
                    ),
                ]

                exit_code = main(
                    [
                        "--template",
                        str(template_path),
                        "--player-guid",
                        "5406",
                        "--mode",
                        "dry-run",
                        "--summary",
                    ]
                )
        finally:
            if template_path.exists():
                template_path.unlink()

        self.assertEqual(exit_code, 0)
        self.assertIsNotNone(captured_rule)
        assert captured_rule is not None
        self.assertEqual(captured_rule.rule_key, "reactive_bounty:template:defias_bandit")
        self.assertEqual(captured_rule.subject_entry, 116)
        self.assertEqual(captured_rule.turn_in_npc_entry, 261)
        self.assertEqual(captured_rule.window_seconds, 300)
        self.assertEqual(captured_rule.quest_id, 910001)
        self.assertEqual(captured_rule.metadata["objective_target_name"], "Defias Bandits")
        self.assertEqual(captured_rule.quest.title, "Bounty: Defias Bandits")

    def test_template_catalog_resolves_bundled_keys(self) -> None:
        templates = list_reactive_bounty_templates()
        keys = {template.key for template in templates}

        self.assertIn("defias_bandits_guard_thomas", keys)
        self.assertIn("murlocs_dughan_tabard_dragonslayer", keys)
        self.assertEqual(
            resolve_reactive_bounty_template_path("defias_bandit").name,
            "defias_bandits_guard_thomas.json",
        )
        self.assertEqual(
            resolve_reactive_bounty_template_path("murloc").name,
            "murlocs_dughan_tabard_dragonslayer.json",
        )

    def test_cli_lists_templates_without_db_clients(self) -> None:
        output = io.StringIO()

        with (
            patch("wm.reactive.install_bounty.Settings.from_env", side_effect=AssertionError("no settings for list")),
            patch("wm.reactive.install_bounty.MysqlCliClient", side_effect=AssertionError("no mysql for list")),
            contextlib.redirect_stdout(output),
        ):
            exit_code = main(["--list-templates", "--summary"])

        self.assertEqual(exit_code, 0)
        rendered = output.getvalue()
        self.assertIn("defias_bandits_guard_thomas", rendered)
        self.assertIn("murlocs_dughan_tabard_dragonslayer", rendered)

    def test_cli_template_key_loads_bundled_template(self) -> None:
        captured_rule: ReactiveQuestRule | None = None
        fake_slot_allocator = FakeSlotAllocator()

        class FakeInstaller:
            def __init__(self, **kwargs) -> None:
                del kwargs

            def install(self, *, rule: ReactiveQuestRule, mode: str):
                nonlocal captured_rule
                captured_rule = rule

                class Result:
                    def __init__(self) -> None:
                        self.mode = mode
                        self.rule = rule.to_dict()
                        self.quest_exists = False
                        self.quest_matches_reactive_shape = False
                        self.quest_publish = None
                        self.notes = []

                    def to_dict(self_nonlocal):
                        return {
                            "mode": self_nonlocal.mode,
                            "rule": self_nonlocal.rule,
                            "quest_exists": self_nonlocal.quest_exists,
                            "quest_matches_reactive_shape": self_nonlocal.quest_matches_reactive_shape,
                            "quest_publish": self_nonlocal.quest_publish,
                            "notes": self_nonlocal.notes,
                        }

                return Result()

        with (
            patch("wm.reactive.install_bounty.Settings.from_env", return_value=Settings()),
            patch("wm.reactive.install_bounty.MysqlCliClient", return_value=object()),
            patch("wm.reactive.install_bounty.ReactiveBountyInstaller", FakeInstaller),
            patch("wm.reactive.install_bounty.ReservedSlotDbAllocator", return_value=fake_slot_allocator),
            patch("wm.reactive.install_bounty.ReactiveQuestStore") as reactive_store_cls,
            patch("wm.reactive.install_bounty.LiveCreatureResolver") as resolver_cls,
        ):
            reactive_store_cls.return_value.fetch_character_name.return_value = "Jecia"
            reactive_store_cls.return_value.get_rule_by_key.return_value = None
            resolver_cls.return_value.resolve.side_effect = [
                FakeResolveResult(
                    entry=285,
                    name="Murloc",
                    profile=type("Profile", (), {"entry": 285, "name": "Murloc", "level_max": 7, "mechanical_type": "HUMANOID", "family": None})(),
                ),
                FakeResolveResult(
                    entry=240,
                    name="Marshal Dughan",
                    profile=type("Profile", (), {"entry": 240, "name": "Marshal Dughan", "level_max": 25, "mechanical_type": "HUMANOID", "family": None})(),
                ),
            ]

            exit_code = main(
                [
                    "--template-key",
                    "murloc",
                    "--player-guid",
                    "5406",
                    "--mode",
                    "dry-run",
                    "--summary",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertIsNotNone(captured_rule)
        assert captured_rule is not None
        self.assertEqual(captured_rule.rule_key, "reactive_bounty:template:murloc")
        self.assertEqual(captured_rule.subject_entry, 285)
        self.assertEqual(captured_rule.turn_in_npc_entry, 240)
        self.assertEqual(captured_rule.quest_id, 910001)

    def test_cli_template_loads_reward_and_prefix_overrides(self) -> None:
        captured_rule: ReactiveQuestRule | None = None
        fake_slot_allocator = FakeSlotAllocator()

        class FakeInstaller:
            def __init__(self, **kwargs) -> None:
                del kwargs

            def install(self, *, rule: ReactiveQuestRule, mode: str):
                nonlocal captured_rule
                captured_rule = rule

                class Result:
                    def __init__(self) -> None:
                        self.mode = mode
                        self.rule = rule.to_dict()
                        self.quest_exists = False
                        self.quest_matches_reactive_shape = False
                        self.quest_publish = None
                        self.notes = []

                    def to_dict(self_nonlocal):
                        return {
                            "mode": self_nonlocal.mode,
                            "rule": self_nonlocal.rule,
                            "quest_exists": self_nonlocal.quest_exists,
                            "quest_matches_reactive_shape": self_nonlocal.quest_matches_reactive_shape,
                            "quest_publish": self_nonlocal.quest_publish,
                            "notes": self_nonlocal.notes,
                        }

                return Result()

        template_path = Path("artifacts") / "test_reactive_bounty_murloc_template.json"
        template_path.parent.mkdir(parents=True, exist_ok=True)
        template_path.write_text(
            json.dumps(
                {
                    "rule_key": "reactive_bounty:template:murloc",
                    "subject_entry": 285,
                    "subject_name_prefix": "Murloc",
                    "turn_in_npc_entry": 240,
                    "kill_threshold": 5,
                    "window_seconds": 30,
                    "post_reward_cooldown_seconds": 60,
                    "objective_target_name": "Murlocs",
                    "quest_title": "Bounty: Murlocs",
                    "reward_item_entry": 45574,
                    "reward_item_name": "Stormwind Tabard",
                    "reward_item_count": 1,
                    "reward_xp_difficulty": 4,
                    "reward_spell_id": 22888,
                    "reward_spell_display_id": 22888,
                    "reward_reputations": [{"faction_id": 72, "value": 75}]
                }
            ),
            encoding="utf-8",
        )

        try:
            with (
                patch("wm.reactive.install_bounty.Settings.from_env", return_value=Settings()),
                patch("wm.reactive.install_bounty.MysqlCliClient", return_value=object()),
                patch("wm.reactive.install_bounty.ReactiveBountyInstaller", FakeInstaller),
                patch("wm.reactive.install_bounty.ReservedSlotDbAllocator", return_value=fake_slot_allocator),
                patch("wm.reactive.install_bounty.ReactiveQuestStore") as reactive_store_cls,
                patch("wm.reactive.install_bounty.LiveCreatureResolver") as resolver_cls,
            ):
                reactive_store_cls.return_value.fetch_character_name.return_value = "Jecia"
                reactive_store_cls.return_value.get_rule_by_key.return_value = None
                resolver_cls.return_value.resolve.side_effect = [
                    FakeResolveResult(
                        entry=285,
                        name="Murloc",
                        profile=type("Profile", (), {"entry": 285, "name": "Murloc", "level_max": 7, "mechanical_type": "HUMANOID", "family": None})(),
                    ),
                    FakeResolveResult(
                        entry=240,
                        name="Marshal Dughan",
                        profile=type("Profile", (), {"entry": 240, "name": "Marshal Dughan", "level_max": 25, "mechanical_type": "HUMANOID", "family": None})(),
                    ),
                ]

                exit_code = main(
                    [
                        "--template",
                        str(template_path),
                        "--player-guid",
                        "5406",
                        "--mode",
                        "dry-run",
                        "--summary",
                    ]
                )
        finally:
            if template_path.exists():
                template_path.unlink()

        self.assertEqual(exit_code, 0)
        self.assertIsNotNone(captured_rule)
        assert captured_rule is not None
        self.assertEqual(captured_rule.quest_id, 910001)
        self.assertEqual(captured_rule.metadata["subject_name_prefix"], "Murloc")
        self.assertEqual(captured_rule.metadata["reward_item_entry"], 45574)
        self.assertEqual(captured_rule.metadata["reward_xp_difficulty"], 4)
        self.assertEqual(captured_rule.metadata["reward_spell_id"], 22888)
        self.assertEqual(captured_rule.metadata["reward_reputations"], [{"faction_id": 72, "value": 75}])

    def test_cli_apply_archives_previous_rule_slot_when_switching_to_fresh_quest_id(self) -> None:
        captured_rule: ReactiveQuestRule | None = None
        fake_slot_allocator = FakeSlotAllocator()

        class FakeInstaller:
            def __init__(self, **kwargs) -> None:
                del kwargs

            def install(self, *, rule: ReactiveQuestRule, mode: str):
                nonlocal captured_rule
                captured_rule = rule

                class Result:
                    def __init__(self) -> None:
                        self.mode = mode
                        self.rule = rule.to_dict()
                        self.quest_exists = False
                        self.quest_matches_reactive_shape = False
                        self.quest_publish = {"applied": mode == "apply", "preflight": {"ok": True}}
                        self.notes = []

                    def to_dict(self_nonlocal):
                        return {
                            "mode": self_nonlocal.mode,
                            "rule": self_nonlocal.rule,
                            "quest_exists": self_nonlocal.quest_exists,
                            "quest_matches_reactive_shape": self_nonlocal.quest_matches_reactive_shape,
                            "quest_publish": self_nonlocal.quest_publish,
                            "notes": self_nonlocal.notes,
                        }

                return Result()

        existing_rule = ReactiveQuestRule(
            rule_key="reactive_bounty:template:murloc",
            is_active=True,
            player_guid_scope=5406,
            subject_type="creature",
            subject_entry=285,
            trigger_event_type="kill",
            kill_threshold=2,
            window_seconds=120,
            quest_id=910000,
            turn_in_npc_entry=240,
            grant_mode="direct_quest_add",
            post_reward_cooldown_seconds=60,
            metadata={},
            notes=[],
        )

        with (
            patch("wm.reactive.install_bounty.Settings.from_env", return_value=Settings()),
            patch("wm.reactive.install_bounty.MysqlCliClient", return_value=object()),
            patch("wm.reactive.install_bounty.ReactiveBountyInstaller", FakeInstaller),
            patch("wm.reactive.install_bounty.ReservedSlotDbAllocator", return_value=fake_slot_allocator),
            patch("wm.reactive.install_bounty.ReactiveQuestStore") as reactive_store_cls,
            patch("wm.reactive.install_bounty.LiveCreatureResolver") as resolver_cls,
        ):
            reactive_store_cls.return_value.fetch_character_name.return_value = "Jecia"
            reactive_store_cls.return_value.get_rule_by_key.return_value = existing_rule
            resolver_cls.return_value.resolve.side_effect = [
                FakeResolveResult(
                    entry=285,
                    name="Murloc",
                    profile=type("Profile", (), {"entry": 285, "name": "Murloc", "level_max": 7, "mechanical_type": "HUMANOID", "family": None})(),
                ),
                FakeResolveResult(
                    entry=240,
                    name="Marshal Dughan",
                    profile=type("Profile", (), {"entry": 240, "name": "Marshal Dughan", "level_max": 25, "mechanical_type": "HUMANOID", "family": None})(),
                ),
            ]

            exit_code = main(
                [
                    "--rule-key",
                    "reactive_bounty:template:murloc",
                    "--player-guid",
                    "5406",
                    "--subject-entry",
                    "285",
                    "--turn-in-npc-entry",
                    "240",
                    "--kill-threshold",
                    "2",
                    "--window-seconds",
                    "120",
                    "--mode",
                    "apply",
                    "--summary",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertIsNotNone(captured_rule)
        assert captured_rule is not None
        self.assertEqual(captured_rule.quest_id, 910001)
        self.assertEqual(
            fake_slot_allocator.released,
            [{"entity_type": "quest", "reserved_id": 910000, "archive": True}],
        )


if __name__ == "__main__":
    unittest.main()
