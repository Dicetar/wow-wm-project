from __future__ import annotations

from wm.quests.models import BountyQuestDraft, ValidationIssue, ValidationResult


def validate_bounty_quest_draft(draft: BountyQuestDraft) -> ValidationResult:
    issues: list[ValidationIssue] = []

    if draft.quest_id <= 0:
        issues.append(ValidationIssue(path="quest_id", message="Quest ID must be positive."))
    elif draft.quest_id < 900000:
        issues.append(
            ValidationIssue(
                path="quest_id",
                message="Quest ID is outside the recommended WM-managed reserved range (900000+).",
                severity="warning",
            )
        )

    if not draft.title.strip():
        issues.append(ValidationIssue(path="title", message="Title must not be empty."))
    if len(draft.title) > 255:
        issues.append(ValidationIssue(path="title", message="Title is too long for a safe quest title."))

    if not draft.quest_description.strip():
        issues.append(ValidationIssue(path="quest_description", message="Quest description must not be empty."))
    if not draft.objective_text.strip():
        issues.append(ValidationIssue(path="objective_text", message="Objective text must not be empty."))
    if not draft.offer_reward_text.strip():
        issues.append(ValidationIssue(path="offer_reward_text", message="Offer reward text must not be empty."))
    if not draft.request_items_text.strip():
        issues.append(ValidationIssue(path="request_items_text", message="Request items text must not be empty."))

    if draft.quest_level < 1 or draft.quest_level > 80:
        issues.append(ValidationIssue(path="quest_level", message="Quest level must be between 1 and 80."))
    if draft.min_level < 1 or draft.min_level > 80:
        issues.append(ValidationIssue(path="min_level", message="Minimum level must be between 1 and 80."))
    if draft.min_level > draft.quest_level:
        issues.append(ValidationIssue(path="min_level", message="Minimum level cannot exceed quest level."))

    if draft.questgiver_entry <= 0:
        issues.append(ValidationIssue(path="questgiver_entry", message="Quest giver entry must be positive."))
    if draft.start_npc_entry is not None and draft.start_npc_entry <= 0:
        issues.append(ValidationIssue(path="start_npc_entry", message="Start NPC entry must be positive when set."))
    if draft.end_npc_entry is not None and draft.end_npc_entry <= 0:
        issues.append(ValidationIssue(path="end_npc_entry", message="End NPC entry must be positive when set."))
    if draft.grant_mode not in {"npc_start", "direct_quest_add"}:
        issues.append(ValidationIssue(path="grant_mode", message="Grant mode must be `npc_start` or `direct_quest_add`."))
    if draft.grant_mode == "npc_start" and draft.start_npc_entry is None:
        issues.append(ValidationIssue(path="start_npc_entry", message="NPC-start quests require a starter NPC entry."))
    if draft.end_npc_entry is None:
        issues.append(ValidationIssue(path="end_npc_entry", message="Bounty quests require a turn-in NPC entry."))

    if draft.objective.target_entry <= 0:
        issues.append(ValidationIssue(path="objective.target_entry", message="Target entry must be positive."))
    if not draft.objective.target_name.strip():
        issues.append(ValidationIssue(path="objective.target_name", message="Target name must not be empty."))
    if draft.objective.kill_count < 1 or draft.objective.kill_count > 25:
        issues.append(ValidationIssue(path="objective.kill_count", message="Kill count must be between 1 and 25."))

    if draft.reward.money_copper < 0:
        issues.append(ValidationIssue(path="reward.money_copper", message="Reward money cannot be negative."))
    if draft.reward.money_copper > 1000000:
        issues.append(
            ValidationIssue(
                path="reward.money_copper",
                message="Reward money is above the current safety cap (1000000 copper / 100 gold).",
            )
        )

    if draft.reward.reward_item_entry is not None and draft.reward.reward_item_entry <= 0:
        issues.append(ValidationIssue(path="reward.reward_item_entry", message="Reward item entry must be positive."))
    if draft.reward.reward_item_entry is None and draft.reward.reward_item_name:
        issues.append(
            ValidationIssue(
                path="reward.reward_item_name",
                message="Reward item name should only be set when a reward item entry is also set.",
                severity="warning",
            )
        )
    if draft.reward.reward_item_count < 1 or draft.reward.reward_item_count > 20:
        issues.append(
            ValidationIssue(
                path="reward.reward_item_count",
                message="Reward item count must be between 1 and 20.",
            )
        )

    return ValidationResult(issues=issues)
