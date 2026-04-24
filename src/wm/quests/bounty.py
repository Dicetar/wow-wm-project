from __future__ import annotations

from wm.refs import CreatureRef
from wm.refs import ItemRef
from wm.refs import NpcRef
from wm.refs import QuestRef
from wm.quests.models import BountyQuestDraft, BountyQuestObjective, BountyQuestReputationReward, BountyQuestReward
from wm.targets.resolver import TargetProfile

DEFAULT_BOUNTY_SUPPLY_ITEM_ENTRY = 6827
DEFAULT_BOUNTY_SUPPLY_ITEM_NAME = "Box of Supplies"
DEFAULT_BOUNTY_MIN_MONEY_COPPER = 175


def build_bounty_quest_draft(
    *,
    quest_id: int,
    questgiver_entry: int,
    questgiver_name: str,
    target_profile: TargetProfile,
    target_name: str | None = None,
    title: str | None = None,
    kill_count: int = 8,
    quest_level: int | None = None,
    min_level: int | None = None,
    reward_money_copper: int | None = None,
    reward_item_entry: int | None = None,
    reward_item_name: str | None = None,
    reward_item_count: int = 1,
    reward_xp_difficulty: int | None = None,
    reward_spell_id: int | None = None,
    reward_spell_display_id: int | None = None,
    reward_reputations: list[BountyQuestReputationReward | dict[str, int]] | None = None,
    default_supply_item_entry: int | None = DEFAULT_BOUNTY_SUPPLY_ITEM_ENTRY,
    default_supply_item_name: str | None = DEFAULT_BOUNTY_SUPPLY_ITEM_NAME,
    start_npc_entry: int | None = None,
    end_npc_entry: int | None = None,
    grant_mode: str = "npc_start",
    template_defaults: dict[str, object] | None = None,
) -> BountyQuestDraft:
    normalized_kill_count = max(1, int(kill_count))
    resolved_quest_level = int(quest_level if quest_level is not None else max(target_profile.level_max, 1))
    resolved_min_level = int(min_level if min_level is not None else max(resolved_quest_level - 2, 1))
    resolved_target_name = (
        str(target_name).strip()
        if target_name not in (None, "")
        else target_profile.name.strip() or f"Target {target_profile.entry}"
    )

    resolved_title = str(title).strip() if title not in (None, "") else f"Bounty: {resolved_target_name}"
    quest_description = (
        f"{questgiver_name} has posted a bounty against {resolved_target_name}. "
        f"Reduce their numbers and report back when the work is done."
    )
    objective_text = f"Slay {normalized_kill_count} {resolved_target_name}."
    offer_reward_text = (
        f"Well done. {resolved_target_name} will trouble this area less for a while. "
        f"Take this payment and stay ready."
    )
    request_items_text = f"Defeat {normalized_kill_count} {resolved_target_name}, then return to {questgiver_name}."

    tags = [
        "wm_generated",
        "bounty",
        target_profile.mechanical_type.lower(),
    ]
    if target_profile.family:
        tags.append(target_profile.family.lower())

    resolved_template_defaults = {str(k): v for k, v in (template_defaults or {}).items()}
    resolved_template_defaults["SpecialFlags"] = _merge_int_flag(
        resolved_template_defaults.get("SpecialFlags"),
        1,
    )
    resolved_reward = build_default_bounty_reward(
        quest_level=resolved_quest_level,
        reward_money_copper=reward_money_copper,
        reward_item_entry=reward_item_entry,
        reward_item_name=reward_item_name,
        reward_item_count=reward_item_count,
        reward_xp_difficulty=reward_xp_difficulty,
        reward_spell_id=reward_spell_id,
        reward_spell_display_id=reward_spell_display_id,
        reward_reputations=reward_reputations,
        default_supply_item_entry=default_supply_item_entry,
        default_supply_item_name=default_supply_item_name,
    )

    return BountyQuestDraft(
        quest_id=int(quest_id),
        quest_level=resolved_quest_level,
        min_level=resolved_min_level,
        questgiver_entry=int(questgiver_entry),
        questgiver_name=questgiver_name,
        quest=QuestRef(id=int(quest_id), title=resolved_title),
        questgiver=NpcRef(entry=int(questgiver_entry), name=questgiver_name),
        title=resolved_title,
        quest_description=quest_description,
        objective_text=objective_text,
        offer_reward_text=offer_reward_text,
        request_items_text=request_items_text,
        objective=BountyQuestObjective(
            target_entry=int(target_profile.entry),
            target_name=resolved_target_name,
            kill_count=normalized_kill_count,
            target=CreatureRef(entry=int(target_profile.entry), name=resolved_target_name),
        ),
        reward=resolved_reward,
        start_npc_entry=(
            int(start_npc_entry)
            if start_npc_entry is not None
            else (None if grant_mode == "direct_quest_add" else int(questgiver_entry))
        ),
        end_npc_entry=(int(end_npc_entry) if end_npc_entry is not None else int(questgiver_entry)),
        starter_npc=(
            NpcRef(entry=int(start_npc_entry), name=questgiver_name)
            if start_npc_entry is not None
            else (None if grant_mode == "direct_quest_add" else NpcRef(entry=int(questgiver_entry), name=questgiver_name))
        ),
        ender_npc=NpcRef(
            entry=(int(end_npc_entry) if end_npc_entry is not None else int(questgiver_entry)),
            name=questgiver_name,
        ),
        grant_mode=str(grant_mode),
        tags=tags,
        template_defaults=resolved_template_defaults,
    )


def build_default_bounty_reward(
    *,
    quest_level: int,
    reward_money_copper: int | None = None,
    reward_item_entry: int | None = None,
    reward_item_name: str | None = None,
    reward_item_count: int = 1,
    reward_xp_difficulty: int | None = None,
    reward_spell_id: int | None = None,
    reward_spell_display_id: int | None = None,
    reward_reputations: list[BountyQuestReputationReward | dict[str, int]] | None = None,
    default_supply_item_entry: int | None = DEFAULT_BOUNTY_SUPPLY_ITEM_ENTRY,
    default_supply_item_name: str | None = DEFAULT_BOUNTY_SUPPLY_ITEM_NAME,
) -> BountyQuestReward:
    resolved_level = max(1, int(quest_level))
    using_default_supply_item = reward_item_entry in (None, "") and default_supply_item_entry not in (None, "")
    resolved_item_entry = (
        int(reward_item_entry)
        if reward_item_entry not in (None, "")
        else int(default_supply_item_entry)
        if default_supply_item_entry not in (None, "")
        else None
    )
    resolved_item_name = (
        str(reward_item_name)
        if reward_item_name not in (None, "")
        else str(default_supply_item_name)
        if using_default_supply_item and default_supply_item_name not in (None, "")
        else None
    )
    resolved_item_count = max(1, int(reward_item_count or 1))
    resolved_reward_xp_difficulty = (
        int(reward_xp_difficulty)
        if reward_xp_difficulty not in (None, "")
        else default_bounty_reward_xp_difficulty(quest_level=resolved_level)
    )

    return BountyQuestReward(
        money_copper=(
            int(reward_money_copper)
            if reward_money_copper not in (None, "")
            else default_bounty_reward_money_copper(quest_level=resolved_level)
        ),
        reward_item_entry=resolved_item_entry,
        reward_item_name=resolved_item_name,
        reward_item_count=resolved_item_count,
        reward_xp_difficulty=resolved_reward_xp_difficulty,
        reward_spell_id=int(reward_spell_id) if reward_spell_id is not None else None,
        reward_spell_display_id=int(reward_spell_display_id) if reward_spell_display_id is not None else None,
        reward_reputations=[
            reward
            if isinstance(reward, BountyQuestReputationReward)
            else BountyQuestReputationReward(
                faction_id=int(reward["faction_id"]),
                value=int(reward["value"]),
            )
            for reward in (reward_reputations or [])
        ],
        reward_item=(
            ItemRef(entry=resolved_item_entry, name=resolved_item_name)
            if resolved_item_entry is not None
            else None
        ),
    )


def default_bounty_reward_money_copper(*, quest_level: int) -> int:
    # BridgeLab stock quest rows track close to 4 * level^2 for positive-money averages.
    resolved_level = max(1, int(quest_level))
    return max(DEFAULT_BOUNTY_MIN_MONEY_COPPER, 4 * resolved_level * resolved_level)


def default_bounty_reward_xp_difficulty(*, quest_level: int) -> int:
    resolved_level = max(1, int(quest_level))
    return 5 if resolved_level >= 25 else 4


def _merge_int_flag(value: object, flag: int) -> int:
    try:
        return int(value or 0) | int(flag)
    except (TypeError, ValueError):
        return int(flag)
