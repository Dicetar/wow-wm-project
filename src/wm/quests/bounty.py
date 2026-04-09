from __future__ import annotations

from wm.refs import CreatureRef
from wm.refs import ItemRef
from wm.refs import NpcRef
from wm.refs import QuestRef
from wm.quests.models import BountyQuestDraft, BountyQuestObjective, BountyQuestReward
from wm.targets.resolver import TargetProfile


def build_bounty_quest_draft(
    *,
    quest_id: int,
    questgiver_entry: int,
    questgiver_name: str,
    target_profile: TargetProfile,
    kill_count: int = 8,
    quest_level: int | None = None,
    min_level: int | None = None,
    reward_money_copper: int = 1200,
    reward_item_entry: int | None = None,
    reward_item_name: str | None = None,
    reward_item_count: int = 1,
    start_npc_entry: int | None = None,
    end_npc_entry: int | None = None,
    grant_mode: str = "npc_start",
    template_defaults: dict[str, object] | None = None,
) -> BountyQuestDraft:
    normalized_kill_count = max(1, int(kill_count))
    resolved_quest_level = int(quest_level if quest_level is not None else max(target_profile.level_max, 1))
    resolved_min_level = int(min_level if min_level is not None else max(resolved_quest_level - 2, 1))
    target_name = target_profile.name.strip() or f"Target {target_profile.entry}"

    title = f"Bounty: {target_name}"
    quest_description = (
        f"{questgiver_name} has posted a bounty against {target_name}. "
        f"Reduce their numbers and report back when the work is done."
    )
    objective_text = f"Slay {normalized_kill_count} {target_name}."
    offer_reward_text = (
        f"Well done. {target_name} will trouble this area less for a while. "
        f"Take this payment and stay ready."
    )
    request_items_text = f"Defeat {normalized_kill_count} {target_name}, then return to {questgiver_name}."

    tags = [
        "wm_generated",
        "bounty",
        target_profile.mechanical_type.lower(),
    ]
    if target_profile.family:
        tags.append(target_profile.family.lower())

    return BountyQuestDraft(
        quest_id=int(quest_id),
        quest_level=resolved_quest_level,
        min_level=resolved_min_level,
        questgiver_entry=int(questgiver_entry),
        questgiver_name=questgiver_name,
        quest=QuestRef(id=int(quest_id), title=title),
        questgiver=NpcRef(entry=int(questgiver_entry), name=questgiver_name),
        title=title,
        quest_description=quest_description,
        objective_text=objective_text,
        offer_reward_text=offer_reward_text,
        request_items_text=request_items_text,
        objective=BountyQuestObjective(
            target_entry=int(target_profile.entry),
            target_name=target_name,
            kill_count=normalized_kill_count,
            target=CreatureRef(entry=int(target_profile.entry), name=target_name),
        ),
        reward=BountyQuestReward(
            money_copper=int(reward_money_copper),
            reward_item_entry=int(reward_item_entry) if reward_item_entry is not None else None,
            reward_item_name=reward_item_name,
            reward_item_count=int(reward_item_count),
            reward_item=(
                ItemRef(entry=int(reward_item_entry), name=reward_item_name)
                if reward_item_entry is not None
                else None
            ),
        ),
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
        template_defaults={str(k): v for k, v in (template_defaults or {}).items()},
    )
