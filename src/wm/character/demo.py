from __future__ import annotations

from wm.character.models import ArcState, CharacterProfile, CharacterUnlock, PromptQueueEntry, RewardInstance


def main() -> None:
    profile = CharacterProfile(
        character_guid=42,
        character_name="Aldren",
        wm_persona="ironforge_bound",
        tone="grim_but_wry",
        preferred_themes=["forbidden lore", "ironforge politics", "arcane experimentation"],
        avoided_themes=["holy zealotry"],
    )
    arc = ArcState(
        character_guid=42,
        arc_key="ironforge_arcane_incident",
        stage_key="intel_before_infiltration",
        status="active",
        branch_key="stealth_or_social",
        summary="The character has drawn the attention of Ironforge scholars and now must gather intel from a hostile stronghold.",
    )
    unlock = CharacterUnlock(
        character_guid=42,
        unlock_kind="spell",
        unlock_id=900001,
        source_arc_key="ironforge_arcane_incident",
        source_quest_id=910001,
        grant_method="gm_command",
        bot_eligible=False,
    )
    reward = RewardInstance(
        character_guid=42,
        reward_kind="item",
        template_id=910101,
        source_arc_key="ironforge_arcane_incident",
        source_quest_id=910002,
        is_equipped_gate=True,
    )
    prompt = PromptQueueEntry(
        character_guid=42,
        prompt_kind="branch_choice",
        body="You need intel from the enemy stronghold. Do you want to infiltrate quietly, bribe someone inside, or stage a distraction?",
    )

    print("=== CHARACTER PROFILE ===")
    print(profile)
    print()
    print("=== ARC STATE ===")
    print(arc)
    print()
    print("=== UNLOCK ===")
    print(unlock)
    print()
    print("=== REWARD INSTANCE ===")
    print(reward)
    print()
    print("=== PROMPT QUEUE ENTRY ===")
    print(prompt)


if __name__ == "__main__":
    main()
