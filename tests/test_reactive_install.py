import unittest

from wm.config import Settings
from wm.reactive.install_bounty import ReactiveBountyInstaller
from wm.reactive.models import ReactiveQuestRule


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
    def ensure_slot_prepared(self, **kwargs):
        self.last_kwargs = kwargs
        return object()


class FakeQuestPublisher:
    def __init__(self) -> None:
        self.calls = []

    def publish(self, *, draft, mode: str):
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
    def __init__(self) -> None:
        self.calls = []

    def publish(self, *, draft, mode: str):
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
        if entry == 116:
            return FakeResolveResult(
                entry=116,
                name="Defias Bandit",
                profile=type("Profile", (), {"entry": 116, "name": "Defias Bandit", "level_max": 9, "mechanical_type": "HUMANOID", "family": None})(),
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
            rule_key="reactive_bounty:auto:defias_bandit",
            is_active=True,
            player_guid_scope=5406,
            subject_type="creature",
            subject_entry=116,
            trigger_event_type="kill",
            kill_threshold=4,
            window_seconds=120,
            quest_id=910000,
            turn_in_npc_entry=240,
            grant_mode="direct_quest_add",
            post_reward_cooldown_seconds=60,
            metadata={},
            notes=[],
        )

        result = installer.install(rule=rule, mode="apply")

        self.assertTrue(result.quest_publish["applied"])
        self.assertTrue(result.quest_publish["live_refresh_applied"])


if __name__ == "__main__":
    unittest.main()
