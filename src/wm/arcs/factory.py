from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import sys
from typing import Any

from wm.character.eligibility import build_journey_eligibility
from wm.character.journey import CharacterJourneyStore
from wm.character.journey import build_journey_operations
from wm.character.journey import validate_journey_plan
from wm.character.reader import CharacterStateReader
from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient, MysqlCliError
from wm.items.publish import ItemPublisher
from wm.items.publish import load_managed_item_draft
from wm.quests.bounty import build_bounty_quest_draft
from wm.quests.generate_bounty import LiveCreatureResolver
from wm.quests.publish import QuestPublisher
from wm.reserved.db_allocator import ReservedSlotDbAllocator
from wm.runtime_sync import build_default_quest_reload_commands
from wm.runtime_sync import sync_runtime_after_publish


SCENARIO_VERSION = "wm.arc_reward_factory.personal_arc.v1"

_TOP_LEVEL_KEYS = {
    "schema_version",
    "arc_key",
    "player_guid",
    "title",
    "summary",
    "beats",
    "target",
    "turn_in_npc",
    "quest",
    "reward",
    "journey_updates",
    "runtime_sync",
    "notes",
}
_BEAT_KEYS = {"beat_key", "label", "kind", "description"}
_TARGET_KEYS = {"creature_entry", "target_name", "kill_count"}
_NPC_KEYS = {"entry", "name"}
_QUEST_KEYS = {
    "title",
    "quest_description",
    "objective_text",
    "offer_reward_text",
    "request_items_text",
    "quest_level",
    "min_level",
    "grant_mode",
}
_REWARD_KEYS = {
    "kind",
    "item_draft_path",
    "item_entry",
    "item_name",
    "item_count",
    "reward_item_mode",
    "is_equipped_gate",
}
_JOURNEY_KEYS = {"stage_key", "branch_key", "conversation_steering", "prompt_queue"}
_STEERING_KEYS = {"steering_key", "steering_kind", "body", "priority", "source", "is_active", "metadata"}
_PROMPT_KEYS = {"prompt_kind", "body"}
_RUNTIME_SYNC_KEYS = {"mode", "item_commands", "quest_commands", "notes"}
_FORBIDDEN_KEYS = {
    "sql",
    "sql_text",
    "sql_file",
    "freeform_sql",
    "gm_command",
    "gm_commands",
    "freeform_gm",
    "shell_command",
    "shell_commands",
    "command",
    "commands",
    "llm_mutation",
    "direct_mutation",
}
_GENERATED_ARC_QUEST_FLAGS = 8


@dataclass(slots=True)
class ArcFactoryIssue:
    path: str
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PersonalArcScenario:
    schema_version: str
    arc_key: str
    player_guid: int
    title: str
    summary: str
    beats: list[dict[str, Any]]
    target: dict[str, Any]
    turn_in_npc: dict[str, Any]
    quest: dict[str, Any]
    reward: dict[str, Any]
    journey_updates: dict[str, Any] = field(default_factory=dict)
    runtime_sync: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "arc_key": self.arc_key,
            "player_guid": self.player_guid,
            "title": self.title,
            "summary": self.summary,
            "beats": self.beats,
            "target": self.target,
            "turn_in_npc": self.turn_in_npc,
            "quest": self.quest,
            "reward": {
                **self.reward,
                "item_draft_path": str(self.reward.get("item_draft_path")),
            },
            "journey_updates": self.journey_updates,
            "runtime_sync": self.runtime_sync,
            "notes": self.notes,
        }


@dataclass(slots=True)
class ArcFactoryResult:
    mode: str
    arc_key: str
    player_guid: int
    outcome: str
    ok: bool
    applied: bool = False
    restart_recommended: bool = False
    scenario: dict[str, Any] = field(default_factory=dict)
    eligibility: dict[str, Any] | None = None
    item_publish: dict[str, Any] | None = None
    quest_publish: dict[str, Any] | None = None
    journey: dict[str, Any] | None = None
    runtime_sync: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None
    allocated_quest_id: int | None = None
    preview_quest_id: int | None = None
    notes: list[str] = field(default_factory=list)
    issues: list[ArcFactoryIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "arc_key": self.arc_key,
            "player_guid": self.player_guid,
            "outcome": self.outcome,
            "ok": self.ok,
            "applied": self.applied,
            "restart_recommended": self.restart_recommended,
            "scenario": self.scenario,
            "eligibility": self.eligibility,
            "item_publish": self.item_publish,
            "quest_publish": self.quest_publish,
            "journey": self.journey,
            "runtime_sync": self.runtime_sync,
            "verification": self.verification,
            "allocated_quest_id": self.allocated_quest_id,
            "preview_quest_id": self.preview_quest_id,
            "notes": self.notes,
            "issues": [issue.to_dict() for issue in self.issues],
        }


class ArcRewardFactory:
    def __init__(
        self,
        *,
        client: MysqlCliClient,
        settings: Settings,
        character_loader: Any | None = None,
        journey_store: Any | None = None,
        item_publisher: Any | None = None,
        quest_publisher: Any | None = None,
        slot_allocator: Any | None = None,
        resolver: Any | None = None,
    ) -> None:
        self.client = client
        self.settings = settings
        self.character_loader = character_loader or CharacterStateReader(client=client, settings=settings)
        self.journey_store = journey_store or CharacterJourneyStore(client=client, settings=settings)
        self.item_publisher = item_publisher or ItemPublisher(client=client, settings=settings)
        self.quest_publisher = quest_publisher or QuestPublisher(client=client, settings=settings)
        self.slot_allocator = slot_allocator or ReservedSlotDbAllocator(client=client, settings=settings)
        self.resolver = resolver or LiveCreatureResolver(client=client, settings=settings)

    def run(self, *, scenario: PersonalArcScenario, mode: str, runtime_sync_mode: str = "scenario") -> ArcFactoryResult:
        if mode == "dry-run":
            return self.dry_run(scenario=scenario, runtime_sync_mode=runtime_sync_mode)
        if mode == "apply":
            return self.apply(scenario=scenario, runtime_sync_mode=runtime_sync_mode)
        if mode == "verify":
            return self.verify(scenario=scenario)
        raise ValueError(f"Unsupported arc factory mode: {mode}")

    def dry_run(self, *, scenario: PersonalArcScenario, runtime_sync_mode: str) -> ArcFactoryResult:
        issues: list[ArcFactoryIssue] = []
        eligibility = self._eligibility(scenario=scenario, issues=issues)
        existing_quest_id = self._existing_arc_source_quest_id(scenario=scenario)
        if existing_quest_id is not None:
            verification = self._verify_state(scenario=scenario, issues=issues)
            ok = not _has_error(issues)
            return ArcFactoryResult(
                mode="dry-run",
                arc_key=scenario.arc_key,
                player_guid=scenario.player_guid,
                outcome="WORKING" if ok else "PARTIAL",
                ok=ok,
                applied=False,
                scenario=scenario.to_dict(),
                eligibility=eligibility,
                verification=verification,
                preview_quest_id=int(existing_quest_id),
                notes=[
                    f"Arc `{scenario.arc_key}` is already recorded on source quest {existing_quest_id}; dry-run verified existing state instead of previewing a duplicate quest.",
                    *scenario.notes,
                ],
                issues=issues,
            )
        reward = self._reward_item_publish(scenario=scenario, mode="dry-run", issues=issues)
        preview_slot = self.slot_allocator.peek_next_free_slot(entity_type="quest")
        if preview_slot is None:
            issues.append(ArcFactoryIssue(path="reserved_slot.quest", message="No free managed quest slot is available."))
            preview_quest_id = None
            quest_publish = None
            journey = None
            runtime_sync = self._runtime_sync(scenario=scenario, mode="dry-run", quest_id=None, runtime_sync_mode=runtime_sync_mode)
        else:
            preview_quest_id = int(preview_slot.reserved_id)
            quest_draft = self._build_quest_draft(scenario=scenario, quest_id=preview_quest_id)
            quest_publish = self.quest_publisher.publish(
                draft=quest_draft,
                mode="dry-run",
                allow_free_reserved_slot_preview=True,
            ).to_dict()
            issues.extend(_publish_issues(quest_publish, prefix="quest_publish"))
            journey_plan = self._build_journey_plan(scenario=scenario, quest_id=preview_quest_id)
            journey = self._journey_preview(journey_plan)
            runtime_sync = self._runtime_sync(
                scenario=scenario,
                mode="dry-run",
                quest_id=preview_quest_id,
                runtime_sync_mode=runtime_sync_mode,
            )

        item_publish = reward["publish"]
        issues.extend(reward["issues"])
        ok = (
            _eligibility_ready(eligibility)
            and _publish_ok(item_publish)
            and (quest_publish is None or _publish_ok(quest_publish))
            and not _has_error(issues)
            and preview_quest_id is not None
        )
        return ArcFactoryResult(
            mode="dry-run",
            arc_key=scenario.arc_key,
            player_guid=scenario.player_guid,
            outcome="WORKING" if ok else "BROKEN",
            ok=ok,
            applied=False,
            restart_recommended=False,
            scenario=scenario.to_dict(),
            eligibility=eligibility,
            item_publish=item_publish,
            quest_publish=quest_publish,
            journey=journey,
            runtime_sync=runtime_sync,
            preview_quest_id=preview_quest_id,
            notes=[
                "Dry-run checks journey eligibility, managed item publish, fresh quest-slot availability, quest publish preflight, journey writes, and runtime-sync intent without mutation.",
                "The quest slot is previewed only; apply mode allocates a fresh slot again.",
                *_bridge_lab_notes(settings=self.settings, player_guid=scenario.player_guid),
                *scenario.notes,
            ],
            issues=issues,
        )

    def apply(self, *, scenario: PersonalArcScenario, runtime_sync_mode: str) -> ArcFactoryResult:
        issues: list[ArcFactoryIssue] = []
        eligibility = self._eligibility(scenario=scenario, issues=issues)
        if not _eligibility_ready(eligibility):
            issues.append(ArcFactoryIssue(path="eligibility", message="Journey eligibility is not ready for arc factory."))
            return _base_result(scenario=scenario, mode="apply", outcome="BROKEN", eligibility=eligibility, issues=issues)
        existing_quest_id = self._existing_arc_source_quest_id(scenario=scenario)
        if existing_quest_id is not None:
            verification = self._verify_state(scenario=scenario, issues=issues)
            ok = not _has_error(issues)
            return ArcFactoryResult(
                mode="apply",
                arc_key=scenario.arc_key,
                player_guid=scenario.player_guid,
                outcome="WORKING" if ok else "PARTIAL",
                ok=ok,
                applied=False,
                scenario=scenario.to_dict(),
                eligibility=eligibility,
                verification=verification,
                allocated_quest_id=int(existing_quest_id),
                notes=[
                    f"Arc `{scenario.arc_key}` is already recorded on source quest {existing_quest_id}; apply skipped duplicate publication.",
                    "Use a new arc_key for a new visible quest iteration.",
                ],
                issues=issues,
            )

        reward = self._reward_item_publish(scenario=scenario, mode="apply", issues=issues)
        item_publish = reward["publish"]
        issues.extend(reward["issues"])
        if not _publish_applied(item_publish):
            return ArcFactoryResult(
                mode="apply",
                arc_key=scenario.arc_key,
                player_guid=scenario.player_guid,
                outcome="BROKEN",
                ok=False,
                applied=False,
                scenario=scenario.to_dict(),
                eligibility=eligibility,
                item_publish=item_publish,
                notes=["Managed reward item did not publish cleanly; quest allocation and journey mutation were skipped."],
                issues=issues,
            )

        slot = self.slot_allocator.allocate_next_free_slot(
            entity_type="quest",
            arc_key=scenario.arc_key,
            character_guid=scenario.player_guid,
            source_quest_id=None,
            notes=[
                f"arc_factory:{scenario.arc_key}",
                "slot_strategy:fresh_reserved_slot",
                f"reward_item_entry:{int(scenario.reward['item_entry'])}",
            ],
        )
        if slot is None:
            issues.append(ArcFactoryIssue(path="reserved_slot.quest", message="No free managed quest slot is available."))
            return ArcFactoryResult(
                mode="apply",
                arc_key=scenario.arc_key,
                player_guid=scenario.player_guid,
                outcome="BROKEN",
                ok=False,
                applied=False,
                scenario=scenario.to_dict(),
                eligibility=eligibility,
                item_publish=item_publish,
                notes=["Managed reward item published, but quest allocation failed; no quest or journey mutation was applied."],
                issues=issues,
            )

        quest_id = int(slot.reserved_id)
        quest_publish: dict[str, Any] | None = None
        journey: dict[str, Any] | None = None
        quest_draft = self._build_quest_draft(scenario=scenario, quest_id=quest_id)
        journey_plan = self._build_journey_plan(scenario=scenario, quest_id=quest_id)
        try:
            quest_publish = self.quest_publisher.publish(draft=quest_draft, mode="apply").to_dict()
            issues.extend(_publish_issues(quest_publish, prefix="quest_publish"))
            if not _publish_applied(quest_publish):
                self.slot_allocator.release_slot(entity_type="quest", reserved_id=quest_id)
                return ArcFactoryResult(
                    mode="apply",
                    arc_key=scenario.arc_key,
                    player_guid=scenario.player_guid,
                    outcome="BROKEN",
                    ok=False,
                    applied=False,
                    scenario=scenario.to_dict(),
                    eligibility=eligibility,
                    item_publish=item_publish,
                    quest_publish=quest_publish,
                    allocated_quest_id=quest_id,
                    notes=["Quest publish failed; the freshly allocated slot was released."],
                    issues=issues,
                )
            journey_result = self.journey_store.apply_plan(plan=journey_plan, mode="apply")
            journey = journey_result.to_dict()
            if not bool(journey.get("ok", False)):
                issues.append(
                    ArcFactoryIssue(
                        path="journey.apply",
                        message=str(journey.get("error") or "Journey apply failed after quest publish."),
                    )
                )
        except Exception as exc:
            if not _publish_applied(quest_publish):
                try:
                    self.slot_allocator.release_slot(entity_type="quest", reserved_id=quest_id)
                except Exception:
                    pass
            issues.append(ArcFactoryIssue(path="apply", message=_safe_error(exc)))
            return ArcFactoryResult(
                mode="apply",
                arc_key=scenario.arc_key,
                player_guid=scenario.player_guid,
                outcome="BROKEN",
                ok=False,
                applied=False,
                scenario=scenario.to_dict(),
                eligibility=eligibility,
                item_publish=item_publish,
                quest_publish=quest_publish,
                journey=journey,
                allocated_quest_id=quest_id,
                notes=[
                    (
                        "Apply failed before quest publish completed; attempted to release the freshly allocated quest slot."
                        if not _publish_applied(quest_publish)
                        else "Apply failed after quest publish completed; the live quest slot was left in place for repair/verify."
                    )
                ],
                issues=issues,
            )

        runtime_sync = self._runtime_sync(
            scenario=scenario,
            mode="apply",
            quest_id=quest_id,
            runtime_sync_mode=runtime_sync_mode,
        )
        runtime_ok = bool(runtime_sync.get("overall_ok", False))
        ok = runtime_ok and not _has_error(issues)
        return ArcFactoryResult(
            mode="apply",
            arc_key=scenario.arc_key,
            player_guid=scenario.player_guid,
            outcome="PARTIAL" if ok else "BROKEN",
            ok=ok,
            applied=ok,
            restart_recommended=bool(runtime_sync.get("restart_recommended", False)),
            scenario=scenario.to_dict(),
            eligibility=eligibility,
            item_publish=item_publish,
            quest_publish=quest_publish,
            journey=journey,
            runtime_sync=runtime_sync,
            allocated_quest_id=quest_id,
            notes=[
                f"Published personal arc quest {quest_id} in a fresh reserved slot and recorded the arc/reward in the character journey spine.",
                "Outcome remains PARTIAL until Jecia accepts/completes the quest and the reward is visible in-game.",
                *scenario.notes,
            ],
            issues=issues,
        )

    def verify(self, *, scenario: PersonalArcScenario) -> ArcFactoryResult:
        issues: list[ArcFactoryIssue] = []
        eligibility = self._eligibility(scenario=scenario, issues=issues)
        verification = self._verify_state(scenario=scenario, issues=issues)
        ok = not _has_error(issues)
        return ArcFactoryResult(
            mode="verify",
            arc_key=scenario.arc_key,
            player_guid=scenario.player_guid,
            outcome="WORKING" if ok else "PARTIAL",
            ok=ok,
            applied=False,
            scenario=scenario.to_dict(),
            eligibility=eligibility,
            verification=verification,
            notes=[
                "Verify checks character arc/reward records, managed quest slot rows, quest publish rows, and reward item rows.",
                "Gameplay acceptance is still operator-observed: Jecia must see and complete the quest, then confirm reward visibility.",
            ],
            issues=issues,
        )

    def _eligibility(self, *, scenario: PersonalArcScenario, issues: list[ArcFactoryIssue]) -> dict[str, Any]:
        try:
            bundle = self.character_loader.load(character_guid=int(scenario.player_guid))
            snapshot = build_journey_eligibility(bundle).to_dict()
        except Exception as exc:
            issues.append(ArcFactoryIssue(path="eligibility", message=_safe_error(exc)))
            snapshot = build_journey_eligibility(None).to_dict()
        if not bool(snapshot.get("ready_for_arc_factory", False)):
            blocked = ", ".join(str(item) for item in snapshot.get("blocked_reasons") or []) or "not ready"
            issues.append(ArcFactoryIssue(path="eligibility.ready_for_arc_factory", message=blocked))
        return snapshot

    def _reward_item_publish(self, *, scenario: PersonalArcScenario, mode: str, issues: list[ArcFactoryIssue]) -> dict[str, Any]:
        reward = scenario.reward
        if reward.get("kind") != "managed_item":
            return {
                "publish": None,
                "issues": [
                    ArcFactoryIssue(
                        path="reward.kind",
                        message="Arc Factory V1 supports managed_item rewards only. Shell-backed rewards are a later lane.",
                    )
                ],
            }
        draft = load_managed_item_draft(reward["item_draft_path"])
        local_issues: list[ArcFactoryIssue] = []
        if int(draft.item_entry) != int(reward["item_entry"]):
            local_issues.append(
                ArcFactoryIssue(
                    path="reward.item_entry",
                    message=f"Reward item_entry {reward['item_entry']} does not match item draft entry {draft.item_entry}.",
                )
            )
        if local_issues:
            return {"publish": None, "issues": local_issues}
        try:
            publish = self.item_publisher.publish(draft=draft, mode=mode).to_dict()
        except Exception as exc:
            issues.append(ArcFactoryIssue(path="item_publish", message=_safe_error(exc)))
            publish = None
        return {"publish": publish, "issues": _publish_issues(publish, prefix="item_publish") if publish else []}

    def _build_quest_draft(self, *, scenario: PersonalArcScenario, quest_id: int):
        target_entry = int(scenario.target["creature_entry"])
        turn_in_entry = int(scenario.turn_in_npc["entry"])
        target = self.resolver.resolve(entry=target_entry)
        turn_in = self.resolver.resolve(entry=turn_in_entry)
        quest_config = scenario.quest
        target_name = _text_or_default(scenario.target.get("target_name"), target.name)
        template_defaults = _generated_arc_template_defaults(
            self.resolver.fetch_template_defaults_for_questgiver(turn_in.entry)
        )
        draft = build_bounty_quest_draft(
            quest_id=int(quest_id),
            questgiver_entry=turn_in.entry,
            questgiver_name=_text_or_default(scenario.turn_in_npc.get("name"), turn_in.name),
            target_profile=target.profile,
            target_name=target_name,
            title=_text_or_default(quest_config.get("title"), scenario.title),
            kill_count=int(scenario.target.get("kill_count") or 4),
            quest_level=_int_or_none(quest_config.get("quest_level")),
            min_level=_int_or_none(quest_config.get("min_level")),
            # This repack's quest-details packet can surface RewardMoney as a bogus
            # visible item when a fixed item reward is also present.
            reward_money_copper=0,
            reward_item_entry=int(scenario.reward["item_entry"]),
            reward_item_name=_text_or_default(scenario.reward.get("item_name"), str(scenario.reward["item_entry"])),
            reward_item_count=int(scenario.reward.get("item_count") or 1),
            reward_item_mode=str(scenario.reward.get("reward_item_mode") or "fixed"),
            start_npc_entry=(None if str(quest_config.get("grant_mode") or "npc_start") == "direct_quest_add" else turn_in.entry),
            end_npc_entry=turn_in.entry,
            grant_mode=str(quest_config.get("grant_mode") or "npc_start"),
            template_defaults=template_defaults,
        )
        if quest_config.get("quest_description") not in (None, ""):
            draft.quest_description = str(quest_config["quest_description"])
        if quest_config.get("objective_text") not in (None, ""):
            draft.objective_text = str(quest_config["objective_text"])
        if quest_config.get("offer_reward_text") not in (None, ""):
            draft.offer_reward_text = str(quest_config["offer_reward_text"])
        if quest_config.get("request_items_text") not in (None, ""):
            draft.request_items_text = str(quest_config["request_items_text"])
        draft.tags.extend(["personal_arc", f"arc:{scenario.arc_key}", f"player:{scenario.player_guid}"])
        return draft

    def _build_journey_plan(self, *, scenario: PersonalArcScenario, quest_id: int) -> dict[str, Any]:
        reward = scenario.reward
        journey = scenario.journey_updates or {}
        plan = {
            "schema_version": "wm.character_journey.seed.v1",
            "player_guid": int(scenario.player_guid),
            "arc_states": [
                {
                    "arc_key": scenario.arc_key,
                    "stage_key": _text_or_default(journey.get("stage_key"), "quest_published"),
                    "status": "active",
                    "branch_key": journey.get("branch_key"),
                    "summary": scenario.summary,
                }
            ],
            "reward_instances": [
                {
                    "reward_kind": "item",
                    "template_id": int(reward["item_entry"]),
                    "source_arc_key": scenario.arc_key,
                    "source_quest_id": int(quest_id),
                    "is_equipped_gate": bool(reward.get("is_equipped_gate", False)),
                }
            ],
            "conversation_steering": journey.get("conversation_steering") or [],
            "prompt_queue": journey.get("prompt_queue") or [],
            "metadata": {"factory": "wm.arcs.factory", "scenario_version": SCENARIO_VERSION},
        }
        validate_journey_plan(plan)
        return plan

    def _journey_preview(self, journey_plan: dict[str, Any]) -> dict[str, Any]:
        operations = build_journey_operations(journey_plan)
        return {
            "schema_version": "wm.character_journey.seed.v1",
            "mode": "dry-run",
            "ok": True,
            "mutated": False,
            "operation_count": len(operations),
            "operations": [operation.to_dict() for operation in operations],
        }

    def _runtime_sync(
        self,
        *,
        scenario: PersonalArcScenario,
        mode: str,
        quest_id: int | None,
        runtime_sync_mode: str,
    ) -> dict[str, Any]:
        effective_mode = _runtime_sync_mode(scenario=scenario, runtime_sync_mode=runtime_sync_mode)
        commands = [str(command) for command in scenario.runtime_sync.get("item_commands") or []]
        commands.extend(str(command) for command in scenario.runtime_sync.get("quest_commands") or [])
        if quest_id is not None and not scenario.runtime_sync.get("quest_commands"):
            commands.extend(build_default_quest_reload_commands(questgiver_entry=int(scenario.turn_in_npc["entry"])))
        return sync_runtime_after_publish(
            settings=self.settings,
            mode=mode,
            runtime_sync_mode=effective_mode,
            soap_commands=commands,
            no_sync_note=(
                "Arc quest/item rows changed in the live DB. "
                "No runtime reload command was sent; restart worldserver if quest or item state stays stale."
            ),
            synced_note=(
                "Arc quest/item rows changed in the live DB and configured runtime command(s) were sent. "
                "Restart worldserver if the live quest or item state remains stale."
            ),
        ).to_dict()

    def _verify_state(self, *, scenario: PersonalArcScenario, issues: list[ArcFactoryIssue]) -> dict[str, Any]:
        item_entry = int(scenario.reward["item_entry"])
        arc_rows = self._char_rows(
            "SELECT CharacterGUID, ArcKey, StageKey, Status, BranchKey, Summary "
            "FROM wm_character_arc_state "
            f"WHERE CharacterGUID = {int(scenario.player_guid)} AND ArcKey = {_sql_string(scenario.arc_key)}",
            issues=issues,
            issue_path="verify.arc_state",
        )
        reward_rows = self._char_rows(
            "SELECT CharacterGUID, RewardKind, TemplateID, SourceArcKey, SourceQuestID, IsEquippedGate "
            "FROM wm_character_reward_instance "
            f"WHERE CharacterGUID = {int(scenario.player_guid)} "
            f"AND RewardKind = 'item' AND TemplateID = {item_entry} "
            f"AND SourceArcKey = {_sql_string(scenario.arc_key)} "
            "ORDER BY GrantedAt DESC LIMIT 5",
            issues=issues,
            issue_path="verify.reward_instance",
        )
        quest_ids = sorted(
            {
                int(row.get("SourceQuestID"))
                for row in reward_rows
                if row.get("SourceQuestID") not in (None, "", "0")
            }
        )
        quest_rows: list[dict[str, Any]] = []
        slot_rows: list[dict[str, Any]] = []
        publish_rows: list[dict[str, Any]] = []
        if quest_ids:
            id_list = ", ".join(str(quest_id) for quest_id in quest_ids)
            quest_rows = self._world_rows(
                f"SELECT ID, LogTitle, RewardItem1, RewardAmount1 FROM quest_template WHERE ID IN ({id_list})",
                issues=issues,
                issue_path="verify.quest_template",
            )
            slot_rows = self._world_rows(
                "SELECT EntityType, ReservedID, SlotStatus, ArcKey, CharacterGUID, SourceQuestID, NotesJSON "
                f"FROM wm_reserved_slot WHERE EntityType = 'quest' AND ReservedID IN ({id_list})",
                issues=issues,
                issue_path="verify.reserved_slot",
            )
            publish_rows = self._world_rows(
                "SELECT id, artifact_type, artifact_entry, action, status, notes "
                f"FROM wm_publish_log WHERE artifact_type = 'quest' AND artifact_entry IN ({id_list}) "
                "ORDER BY id DESC LIMIT 10",
                issues=issues,
                issue_path="verify.publish_log",
            )
        item_rows = self._world_rows(
            f"SELECT entry, name FROM item_template WHERE entry = {item_entry}",
            issues=issues,
            issue_path="verify.item_template",
        )
        if not arc_rows:
            issues.append(ArcFactoryIssue(path="verify.arc_state", message="No active arc state row was found."))
        if not reward_rows:
            issues.append(ArcFactoryIssue(path="verify.reward_instance", message="No reward instance row was found."))
        if reward_rows and not quest_rows:
            issues.append(ArcFactoryIssue(path="verify.quest_template", message="Reward source quest row was not found."))
        if reward_rows and not slot_rows:
            issues.append(ArcFactoryIssue(path="verify.reserved_slot", message="Reward source quest slot row was not found."))
        for quest_id in quest_ids:
            matching_slots = [row for row in slot_rows if int(row.get("ReservedID") or 0) == int(quest_id)]
            if not matching_slots:
                continue
            slot = matching_slots[0]
            if str(slot.get("SlotStatus") or "") != "active":
                issues.append(
                    ArcFactoryIssue(
                        path="verify.reserved_slot.status",
                        message=f"Source quest slot {quest_id} is `{slot.get('SlotStatus')}`, expected `active`.",
                    )
                )
            if str(slot.get("ArcKey") or "") != scenario.arc_key:
                issues.append(
                    ArcFactoryIssue(
                        path="verify.reserved_slot.arc_key",
                        message=f"Source quest slot {quest_id} is not tagged with arc `{scenario.arc_key}`.",
                    )
                )
            if int(slot.get("CharacterGUID") or 0) != int(scenario.player_guid):
                issues.append(
                    ArcFactoryIssue(
                        path="verify.reserved_slot.character_guid",
                        message=f"Source quest slot {quest_id} is not scoped to player {scenario.player_guid}.",
                    )
                )
        if not item_rows:
            issues.append(ArcFactoryIssue(path="verify.item_template", message=f"Reward item {item_entry} was not found."))
        return {
            "arc_state_rows": arc_rows,
            "reward_instance_rows": reward_rows,
            "source_quest_ids": quest_ids,
            "quest_template_rows": quest_rows,
            "reserved_slot_rows": slot_rows,
            "publish_log_rows": publish_rows,
            "item_template_rows": item_rows,
        }

    def _existing_arc_source_quest_id(self, *, scenario: PersonalArcScenario) -> int | None:
        try:
            rows = self.client.query(
                host=self.settings.char_db_host,
                port=self.settings.char_db_port,
                user=self.settings.char_db_user,
                password=self.settings.char_db_password,
                database=self.settings.char_db_name,
                sql=(
                    "SELECT SourceQuestID "
                    "FROM wm_character_reward_instance "
                    f"WHERE CharacterGUID = {int(scenario.player_guid)} "
                    "AND RewardKind = 'item' "
                    f"AND TemplateID = {int(scenario.reward['item_entry'])} "
                    f"AND SourceArcKey = {_sql_string(scenario.arc_key)} "
                    "AND SourceQuestID IS NOT NULL "
                    "ORDER BY GrantedAt DESC LIMIT 1"
                ),
            )
        except MysqlCliError:
            return None
        if not rows or rows[0].get("SourceQuestID") in (None, "", "0"):
            return None
        return int(rows[0]["SourceQuestID"])

    def _world_rows(self, sql: str, *, issues: list[ArcFactoryIssue], issue_path: str) -> list[dict[str, Any]]:
        try:
            return self.client.query(
                host=self.settings.world_db_host,
                port=self.settings.world_db_port,
                user=self.settings.world_db_user,
                password=self.settings.world_db_password,
                database=self.settings.world_db_name,
                sql=sql,
            )
        except MysqlCliError as exc:
            issues.append(ArcFactoryIssue(path=issue_path, message=_safe_error(exc)))
            return []

    def _char_rows(self, sql: str, *, issues: list[ArcFactoryIssue], issue_path: str) -> list[dict[str, Any]]:
        try:
            return self.client.query(
                host=self.settings.char_db_host,
                port=self.settings.char_db_port,
                user=self.settings.char_db_user,
                password=self.settings.char_db_password,
                database=self.settings.char_db_name,
                sql=sql,
            )
        except MysqlCliError as exc:
            issues.append(ArcFactoryIssue(path=issue_path, message=_safe_error(exc)))
            return []


def load_personal_arc_scenario(path: str | Path, *, player_guid: int | None = None) -> PersonalArcScenario:
    scenario_path = Path(path)
    raw = json.loads(scenario_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Arc factory scenario JSON must be an object.")
    _validate_keys(raw, allowed=_TOP_LEVEL_KEYS, path="")
    _reject_forbidden_keys(raw, path="")
    if raw.get("schema_version") != SCENARIO_VERSION:
        raise ValueError(f"Unsupported schema_version `{raw.get('schema_version')}`; expected `{SCENARIO_VERSION}`.")
    for key in ("arc_key", "player_guid", "title", "summary", "beats", "target", "turn_in_npc", "quest", "reward"):
        if raw.get(key) in (None, ""):
            raise ValueError(f"Scenario field `{key}` is required.")

    beats = _list_of_dicts(raw.get("beats"), "beats")
    if not 2 <= len(beats) <= 3:
        raise ValueError("Arc Factory V1 requires two or three beats.")
    for index, beat in enumerate(beats):
        _validate_keys(beat, allowed=_BEAT_KEYS, path=f"beats[{index}]")
        for key in ("beat_key", "label", "kind", "description"):
            if beat.get(key) in (None, ""):
                raise ValueError(f"beats[{index}].{key} is required.")

    target = _dict_value(raw.get("target"), "target")
    turn_in = _dict_value(raw.get("turn_in_npc"), "turn_in_npc")
    quest = _dict_value(raw.get("quest"), "quest")
    reward = _dict_value(raw.get("reward"), "reward")
    journey = _dict_value(raw.get("journey_updates"), "journey_updates")
    runtime_sync = _dict_value(raw.get("runtime_sync"), "runtime_sync")
    _validate_keys(target, allowed=_TARGET_KEYS, path="target")
    _validate_keys(turn_in, allowed=_NPC_KEYS, path="turn_in_npc")
    _validate_keys(quest, allowed=_QUEST_KEYS, path="quest")
    _validate_keys(reward, allowed=_REWARD_KEYS, path="reward")
    _validate_keys(journey, allowed=_JOURNEY_KEYS, path="journey_updates")
    _validate_keys(runtime_sync, allowed=_RUNTIME_SYNC_KEYS, path="runtime_sync")
    for index, note in enumerate(_list_of_dicts(journey.get("conversation_steering") or [], "journey_updates.conversation_steering")):
        _validate_keys(note, allowed=_STEERING_KEYS, path=f"journey_updates.conversation_steering[{index}]")
    for index, prompt in enumerate(_list_of_dicts(journey.get("prompt_queue") or [], "journey_updates.prompt_queue")):
        _validate_keys(prompt, allowed=_PROMPT_KEYS, path=f"journey_updates.prompt_queue[{index}]")

    if reward.get("kind") != "managed_item":
        raise ValueError("Arc Factory V1 scenario reward.kind must be `managed_item`.")
    for key in ("item_draft_path", "item_entry"):
        if reward.get(key) in (None, ""):
            raise ValueError(f"reward.{key} is required.")
    reward = dict(reward)
    reward["item_draft_path"] = _resolve_repo_path(reward["item_draft_path"])
    reward["item_entry"] = int(reward["item_entry"])
    reward["item_count"] = int(reward.get("item_count") or 1)
    reward["reward_item_mode"] = str(reward.get("reward_item_mode") or "fixed")
    reward["is_equipped_gate"] = _bool(reward.get("is_equipped_gate"), default=False)

    resolved_player_guid = int(player_guid if player_guid is not None else raw["player_guid"])
    return PersonalArcScenario(
        schema_version=str(raw["schema_version"]),
        arc_key=str(raw["arc_key"]),
        player_guid=resolved_player_guid,
        title=str(raw["title"]),
        summary=str(raw["summary"]),
        beats=[dict(beat) for beat in beats],
        target={
            **target,
            "creature_entry": int(target["creature_entry"]),
            "kill_count": int(target.get("kill_count") or 4),
        },
        turn_in_npc={**turn_in, "entry": int(turn_in["entry"])},
        quest=dict(quest),
        reward=reward,
        journey_updates=journey,
        runtime_sync=runtime_sync,
        notes=[str(note) for note in raw.get("notes", [])],
    )


def _render_summary(result: ArcFactoryResult) -> str:
    lines = [
        f"mode: {result.mode}",
        f"arc_key: {result.arc_key}",
        f"player_guid: {result.player_guid}",
        f"outcome: {result.outcome}",
        f"ok: {str(result.ok).lower()}",
        f"applied: {str(result.applied).lower()}",
        f"restart_recommended: {str(result.restart_recommended).lower()}",
    ]
    if result.preview_quest_id is not None:
        lines.append(f"preview_quest_id: {result.preview_quest_id}")
    if result.allocated_quest_id is not None:
        lines.append(f"allocated_quest_id: {result.allocated_quest_id}")
    if result.eligibility is not None:
        lines.extend(
            [
                "",
                f"eligibility.ready_for_arc_factory: {str(bool(result.eligibility.get('ready_for_arc_factory'))).lower()}",
                f"eligibility.active_arcs: {', '.join(result.eligibility.get('active_arc_keys') or []) or '(none)'}",
            ]
        )
    if result.item_publish is not None:
        lines.extend(
            [
                "",
                f"item_publish.applied: {str(bool(result.item_publish.get('applied'))).lower()}",
                f"item_publish.preflight_ok: {str(bool((result.item_publish.get('preflight') or {}).get('ok'))).lower()}",
            ]
        )
    if result.quest_publish is not None:
        lines.extend(
            [
                "",
                f"quest_publish.applied: {str(bool(result.quest_publish.get('applied'))).lower()}",
                f"quest_publish.preflight_ok: {str(bool((result.quest_publish.get('preflight') or {}).get('ok'))).lower()}",
            ]
        )
    if result.journey is not None:
        lines.extend(
            [
                "",
                f"journey.ok: {str(bool(result.journey.get('ok'))).lower()}",
                f"journey.operations: {result.journey.get('operation_count')}",
            ]
        )
    lines.extend(["", "issues:"])
    if not result.issues:
        lines.append("- none")
    else:
        for issue in result.issues:
            lines.append(f"- {issue.path} | {issue.severity} | {issue.message}")
    lines.extend(["", "notes:"])
    if not result.notes:
        lines.append("- none")
    else:
        lines.extend(f"- {note}" for note in result.notes)
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.arcs.factory")
    parser.add_argument("--scenario-json", type=Path, required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply", "verify"], default="dry-run")
    parser.add_argument("--player-guid", type=int)
    parser.add_argument("--runtime-sync", choices=["scenario", "auto", "off", "soap"], default="scenario")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--write-artifact", action="store_true")
    parser.add_argument("--artifact-dir", type=Path, default=Path("artifacts/arc_reward_factory"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    scenario = load_personal_arc_scenario(args.scenario_json, player_guid=args.player_guid)
    settings = Settings.from_env()
    client = MysqlCliClient()
    service = ArcRewardFactory(client=client, settings=settings)
    result = service.run(scenario=scenario, mode=str(args.mode), runtime_sync_mode=str(args.runtime_sync))
    raw = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
    output_json = args.output_json
    if output_json is None and args.write_artifact:
        output_json = args.artifact_dir.joinpath(f"{scenario.arc_key}_{str(args.mode).replace('-', '_')}.json")
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(raw, encoding="utf-8")
    if args.summary or output_json is not None:
        print(_render_summary(result))
        if output_json is not None:
            print("")
            print(f"output_json: {output_json}")
    else:
        print(raw)
    return 0 if result.ok else 2


def _base_result(
    *,
    scenario: PersonalArcScenario,
    mode: str,
    outcome: str,
    eligibility: dict[str, Any] | None,
    issues: list[ArcFactoryIssue],
) -> ArcFactoryResult:
    return ArcFactoryResult(
        mode=mode,
        arc_key=scenario.arc_key,
        player_guid=scenario.player_guid,
        outcome=outcome,
        ok=not _has_error(issues),
        scenario=scenario.to_dict(),
        eligibility=eligibility,
        issues=issues,
    )


def _publish_ok(publish: dict[str, Any] | None) -> bool:
    if not isinstance(publish, dict):
        return False
    return bool((publish.get("validation") or {}).get("ok", False)) and bool((publish.get("preflight") or {}).get("ok", False))


def _publish_applied(publish: dict[str, Any] | None) -> bool:
    return bool(isinstance(publish, dict) and publish.get("applied") and _publish_ok(publish))


def _publish_issues(publish: dict[str, Any] | None, *, prefix: str) -> list[ArcFactoryIssue]:
    issues: list[ArcFactoryIssue] = []
    if not isinstance(publish, dict):
        return issues
    for section in ("validation", "preflight"):
        payload = publish.get(section) or {}
        for issue in payload.get("issues", []) or []:
            if not isinstance(issue, dict):
                continue
            issues.append(
                ArcFactoryIssue(
                    path=f"{prefix}.{section}.{issue.get('path')}",
                    message=str(issue.get("message") or ""),
                    severity=str(issue.get("severity") or "error"),
                )
            )
    return issues


def _eligibility_ready(eligibility: dict[str, Any] | None) -> bool:
    return bool(isinstance(eligibility, dict) and eligibility.get("ready_for_arc_factory"))


def _runtime_sync_mode(*, scenario: PersonalArcScenario, runtime_sync_mode: str) -> str:
    if runtime_sync_mode != "scenario":
        return runtime_sync_mode
    return str(scenario.runtime_sync.get("mode") or "auto")


def _has_error(issues: list[ArcFactoryIssue]) -> bool:
    return any(issue.severity == "error" for issue in issues)


def _bridge_lab_notes(*, settings: Settings, player_guid: int) -> list[str]:
    if int(player_guid) == 5406 and (int(settings.world_db_port) != 33307 or int(settings.char_db_port) != 33307):
        return ["BridgeLab proof for Jecia expects WM_WORLD_DB_PORT=33307 and WM_CHAR_DB_PORT=33307."]
    return []


def _resolve_repo_path(value: object) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parents[3].joinpath(path)


def _validate_keys(value: dict[str, Any], *, allowed: set[str], path: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        prefix = f"{path}." if path else ""
        raise ValueError(f"Unsupported scenario field(s): {', '.join(prefix + key for key in unknown)}")


def _reject_forbidden_keys(value: Any, *, path: str) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key).lower()
            if key_text in _FORBIDDEN_KEYS:
                raise ValueError(f"Forbidden freeform mutation-style scenario field: {path + '.' if path else ''}{key}")
            _reject_forbidden_keys(nested, path=f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_forbidden_keys(nested, path=f"{path}[{index}]")


def _dict_value(value: object, field_name: str) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"Scenario field `{field_name}` must be an object.")
    return dict(value)


def _list_of_dicts(value: object, field_name: str) -> list[dict[str, Any]]:
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise ValueError(f"Scenario field `{field_name}` must be an array.")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"{field_name}[{index}] must be an object.")
        result.append(dict(item))
    return result


def _text_or_default(value: object, default: str) -> str:
    if value in (None, ""):
        return str(default)
    return str(value)


def _int_or_none(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _bool(value: object, *, default: bool) -> bool:
    if value in (None, ""):
        return bool(default)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def _generated_arc_template_defaults(raw_defaults: dict[str, Any]) -> dict[str, Any]:
    defaults = dict(raw_defaults or {})
    sanitized: dict[str, Any] = {}
    for key in ("QuestType", "QuestInfoID", "QuestSortID", "ZoneOrSort", "SuggestedPlayers"):
        if defaults.get(key) not in (None, ""):
            sanitized[key] = defaults[key]
    sanitized["Flags"] = _GENERATED_ARC_QUEST_FLAGS
    sanitized["QuestFlags"] = _GENERATED_ARC_QUEST_FLAGS
    sanitized["SpecialFlags"] = int(defaults.get("SpecialFlags") or 0) | 1
    return sanitized


def _sql_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def _safe_error(exc: Exception) -> str:
    message = str(exc).strip()
    if not message:
        return type(exc).__name__
    return f"{type(exc).__name__}: {message}"


if __name__ == "__main__":
    sys.exit(main())
