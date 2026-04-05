DELETE FROM wm_character_prompt_queue WHERE CharacterGUID = 42;
DELETE FROM wm_character_reward_instance WHERE CharacterGUID = 42;
DELETE FROM wm_character_unlock WHERE CharacterGUID = 42;
DELETE FROM wm_character_arc_state WHERE CharacterGUID = 42;
DELETE FROM wm_character_profile WHERE CharacterGUID = 42;

INSERT INTO wm_character_profile (
    CharacterGUID,
    CharacterName,
    WMPersona,
    Tone,
    PreferredThemesJSON,
    AvoidedThemesJSON
) VALUES (
    42,
    'Aldren',
    'ironforge_bound',
    'grim_but_wry',
    '["forbidden lore", "ironforge politics", "arcane experimentation"]',
    '["holy zealotry"]'
);

INSERT INTO wm_character_arc_state (
    CharacterGUID,
    ArcKey,
    StageKey,
    Status,
    BranchKey,
    Summary
) VALUES (
    42,
    'ironforge_arcane_incident',
    'intel_before_infiltration',
    'active',
    'stealth_or_social',
    'The character has drawn the attention of Ironforge scholars and now must gather intel from a hostile stronghold.'
);

INSERT INTO wm_character_unlock (
    CharacterGUID,
    UnlockKind,
    UnlockID,
    SourceArcKey,
    SourceQuestID,
    GrantMethod,
    BotEligible
) VALUES (
    42,
    'spell',
    900001,
    'ironforge_arcane_incident',
    910001,
    'gm_command',
    0
);

INSERT INTO wm_character_reward_instance (
    CharacterGUID,
    RewardKind,
    TemplateID,
    SourceArcKey,
    SourceQuestID,
    IsEquippedGate
) VALUES (
    42,
    'item',
    910101,
    'ironforge_arcane_incident',
    910002,
    1
);

INSERT INTO wm_character_prompt_queue (
    CharacterGUID,
    PromptKind,
    Body,
    IsConsumed
) VALUES (
    42,
    'branch_choice',
    'You need intel from the enemy stronghold. Do you want to infiltrate quietly, bribe someone inside, or stage a distraction?',
    0
);
