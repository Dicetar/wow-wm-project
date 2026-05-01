-- Broug guard linked progression rewards.
-- Fresh visible IDs only. This file seeds the shells, hidden credit entries, and quest templates;
-- it does not grant the reward shells globally or through class/playerbot defaults.

SET @wm_broug_deflect_shell_spell_id := 946603;
SET @wm_broug_auto_retaliation_shell_spell_id := 946802;
SET @wm_broug_parry_quest_id := 910180;
SET @wm_broug_deflect_quest_id := 910181;
SET @wm_broug_parry_credit_entry := 920104;
SET @wm_broug_deflect_credit_entry := 920105;
SET @wm_broug_questgiver_entry := 197;
SET @wm_broug_player_guid := 5405;

CREATE TABLE IF NOT EXISTS wm_broug_guard_counter (
    PlayerGUID INT UNSIGNED NOT NULL,
    CounterKey VARCHAR(64) NOT NULL,
    CounterValue BIGINT UNSIGNED NOT NULL DEFAULT 0,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (PlayerGUID, CounterKey)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO wm_spell_shell
    (ShellSpellID, ShellKey, FamilyID, Label, State, ClientPatchVersion, OwnershipKey, ProvenanceJSON)
VALUES
    (
        @wm_broug_deflect_shell_spell_id,
        'broug_deflect_v1',
        'self_aura',
        'Deflect',
        'planned',
        'wm_spell_shell_bank.v2',
        'wm.spell_shell:broug_deflect_v1',
        '{"notes":["Broug-scoped active shell. Runtime owns Deflect window, stun, reflected damage, and quest credit."]}'
    ),
    (
        @wm_broug_auto_retaliation_shell_spell_id,
        'broug_auto_retaliation_v1',
        'passive_aura',
        'Riposte Instinct',
        'planned',
        'wm_spell_shell_bank.v2',
        'wm.spell_shell:broug_auto_retaliation_v1',
        '{"notes":["Broug-scoped passive shell. Runtime owns automatic strike-back after Impossible Guard parries."]}'
    )
ON DUPLICATE KEY UPDATE
    ShellKey = VALUES(ShellKey),
    FamilyID = VALUES(FamilyID),
    Label = VALUES(Label),
    State = VALUES(State),
    ClientPatchVersion = VALUES(ClientPatchVersion),
    OwnershipKey = VALUES(OwnershipKey),
    ProvenanceJSON = VALUES(ProvenanceJSON),
    UpdatedAt = CURRENT_TIMESTAMP;

INSERT INTO wm_spell_behavior (ShellSpellID, BehaviorKind, ConfigJSON, Status)
VALUES
    (
        @wm_broug_deflect_shell_spell_id,
        'broug_deflect_v1',
        JSON_OBJECT(
            'window_ms', 350,
            'cooldown_ms', 500,
            'energy_cost', 5,
            'stun_ms', 1000,
            'base_damage', 1,
            'weapon_damage_pct', 120,
            'attack_power_pct', 80,
            'visual_spell_id', @wm_broug_deflect_shell_spell_id,
            'counter_key', 'deflect_success'
        ),
        'active'
    ),
    (
        @wm_broug_auto_retaliation_shell_spell_id,
        'broug_auto_retaliation_v1',
        JSON_OBJECT(
            'cooldown_ms', 250,
            'base_damage', 1,
            'weapon_damage_pct', 80,
            'attack_power_pct', 35,
            'visual_spell_id', 78,
            'counter_key', 'auto_retaliation'
        ),
        'active'
    )
ON DUPLICATE KEY UPDATE
    BehaviorKind = VALUES(BehaviorKind),
    ConfigJSON = VALUES(ConfigJSON),
    Status = VALUES(Status),
    UpdatedAt = CURRENT_TIMESTAMP;

DELETE FROM spell_script_names
WHERE spell_id = @wm_broug_deflect_shell_spell_id
  AND ScriptName = 'spell_wm_shell_dispatch';

INSERT INTO spell_script_names (spell_id, ScriptName)
VALUES (@wm_broug_deflect_shell_spell_id, 'spell_wm_shell_dispatch');

INSERT INTO spell_cooldown_overrides
    (Id, RecoveryTime, CategoryRecoveryTime, StartRecoveryTime, StartRecoveryCategory, Comment)
VALUES
    (@wm_broug_deflect_shell_spell_id, 500, 0, 0, 0, 'WM Broug Deflect native cooldown/no-GCD shell')
ON DUPLICATE KEY UPDATE
    RecoveryTime = VALUES(RecoveryTime),
    CategoryRecoveryTime = VALUES(CategoryRecoveryTime),
    StartRecoveryTime = VALUES(StartRecoveryTime),
    StartRecoveryCategory = VALUES(StartRecoveryCategory),
    Comment = VALUES(Comment);

INSERT INTO creature_template
    (entry, name, subname, minlevel, maxlevel, faction, npcflag, unit_class, type, VerifiedBuild)
VALUES
    (@wm_broug_parry_credit_entry, 'WM Broug Parry Credit', 'Hidden quest credit only', 1, 1, 35, 0, 1, 10, 12340),
    (@wm_broug_deflect_credit_entry, 'WM Broug Deflect Credit', 'Hidden quest credit only', 1, 1, 35, 0, 1, 10, 12340)
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    subname = VALUES(subname),
    minlevel = VALUES(minlevel),
    maxlevel = VALUES(maxlevel),
    faction = VALUES(faction),
    npcflag = VALUES(npcflag),
    unit_class = VALUES(unit_class),
    type = VALUES(type),
    VerifiedBuild = VALUES(VerifiedBuild);

DELETE FROM creature_queststarter WHERE quest IN (@wm_broug_parry_quest_id, @wm_broug_deflect_quest_id);
DELETE FROM creature_questender WHERE quest IN (@wm_broug_parry_quest_id, @wm_broug_deflect_quest_id);
DELETE FROM quest_offer_reward WHERE ID IN (@wm_broug_parry_quest_id, @wm_broug_deflect_quest_id);
DELETE FROM quest_request_items WHERE ID IN (@wm_broug_parry_quest_id, @wm_broug_deflect_quest_id);
DELETE FROM quest_template_addon WHERE ID IN (@wm_broug_parry_quest_id, @wm_broug_deflect_quest_id);
DELETE FROM quest_template WHERE ID IN (@wm_broug_parry_quest_id, @wm_broug_deflect_quest_id);

INSERT INTO quest_template
    (
        ID,
        QuestType,
        QuestLevel,
        MinLevel,
        QuestSortID,
        QuestInfoID,
        RewardNextQuest,
        RewardXPDifficulty,
        RewardMoney,
        RewardMoneyDifficulty,
        Flags,
        AllowableRaces,
        LogTitle,
        LogDescription,
        QuestDescription,
        QuestCompletionLog,
        RequiredNpcOrGo1,
        RequiredNpcOrGoCount1,
        ObjectiveText1,
        VerifiedBuild
    )
VALUES
    (
        @wm_broug_parry_quest_id,
        2,
        4,
        1,
        0,
        0,
        @wm_broug_deflect_quest_id,
        0,
        0,
        0,
        8,
        0,
        'Broug: One Thousand Impossible Guards',
        'Parry 1000 hostile damage events with Impossible Guard.',
        'Your guard is not a stance yet. Make it a reflex. Turn aside a thousand hostile blows, spells, or effects.',
        'Return after Impossible Guard has answered a thousand times.',
        @wm_broug_parry_credit_entry,
        1000,
        'Impossible Guard parries',
        12340
    ),
    (
        @wm_broug_deflect_quest_id,
        2,
        4,
        1,
        0,
        0,
        0,
        0,
        0,
        0,
        8,
        0,
        'Broug: One Thousand Deflections',
        'Catch 1000 hostile damage events inside Deflect windows.',
        'A timed guard is only real when it becomes instinct. Deflect a thousand hostile hits.',
        'Return after Deflect has caught a thousand attacks.',
        @wm_broug_deflect_credit_entry,
        1000,
        'Successful Deflects',
        12340
    );

INSERT INTO quest_template_addon
    (ID, PrevQuestID, NextQuestID, SpecialFlags)
VALUES
    (@wm_broug_parry_quest_id, 0, @wm_broug_deflect_quest_id, 0),
    (@wm_broug_deflect_quest_id, @wm_broug_parry_quest_id, 0, 0)
ON DUPLICATE KEY UPDATE
    PrevQuestID = VALUES(PrevQuestID),
    NextQuestID = VALUES(NextQuestID),
    SpecialFlags = VALUES(SpecialFlags);

INSERT INTO quest_request_items (ID, CompletionText, VerifiedBuild)
VALUES
    (@wm_broug_parry_quest_id, 'A thousand answers. That is enough to make the next one deliberate.', 12340),
    (@wm_broug_deflect_quest_id, 'Now the counterstroke belongs to your bones.', 12340)
ON DUPLICATE KEY UPDATE
    CompletionText = VALUES(CompletionText),
    VerifiedBuild = VALUES(VerifiedBuild);

INSERT INTO quest_offer_reward (ID, RewardText, VerifiedBuild)
VALUES
    (@wm_broug_parry_quest_id, 'You learn Deflect.', 12340),
    (@wm_broug_deflect_quest_id, 'You learn Riposte Instinct.', 12340)
ON DUPLICATE KEY UPDATE
    RewardText = VALUES(RewardText),
    VerifiedBuild = VALUES(VerifiedBuild);

INSERT INTO creature_queststarter (id, quest)
VALUES
    (@wm_broug_questgiver_entry, @wm_broug_parry_quest_id),
    (@wm_broug_questgiver_entry, @wm_broug_deflect_quest_id);

INSERT INTO creature_questender (id, quest)
VALUES
    (@wm_broug_questgiver_entry, @wm_broug_parry_quest_id),
    (@wm_broug_questgiver_entry, @wm_broug_deflect_quest_id);

INSERT INTO wm_reserved_slot
    (EntityType, ReservedID, SlotStatus, ArcKey, CharacterGUID, SourceQuestID, NotesJSON)
VALUES
    ('spell', @wm_broug_deflect_shell_spell_id, 'active', 'broug_guard_progression_v1', @wm_broug_player_guid, @wm_broug_parry_quest_id, '{"key":"broug_deflect_v1"}'),
    ('spell', @wm_broug_auto_retaliation_shell_spell_id, 'active', 'broug_guard_progression_v1', @wm_broug_player_guid, @wm_broug_deflect_quest_id, '{"key":"broug_auto_retaliation_v1"}'),
    ('quest', @wm_broug_parry_quest_id, 'active', 'broug_guard_progression_v1', @wm_broug_player_guid, NULL, '{"key":"broug_one_thousand_impossible_guards"}'),
    ('quest', @wm_broug_deflect_quest_id, 'active', 'broug_guard_progression_v1', @wm_broug_player_guid, @wm_broug_parry_quest_id, '{"key":"broug_one_thousand_deflections"}'),
    ('creature_template', @wm_broug_parry_credit_entry, 'active', 'broug_guard_progression_v1', @wm_broug_player_guid, @wm_broug_parry_quest_id, '{"key":"broug_parry_credit"}'),
    ('creature_template', @wm_broug_deflect_credit_entry, 'active', 'broug_guard_progression_v1', @wm_broug_player_guid, @wm_broug_deflect_quest_id, '{"key":"broug_deflect_credit"}')
ON DUPLICATE KEY UPDATE
    SlotStatus = VALUES(SlotStatus),
    ArcKey = VALUES(ArcKey),
    CharacterGUID = VALUES(CharacterGUID),
    SourceQuestID = VALUES(SourceQuestID),
    NotesJSON = VALUES(NotesJSON);

SELECT
    'broug_guard_reward_behavior' AS metric,
    ShellSpellID AS shell_spell_id,
    BehaviorKind AS value
FROM wm_spell_behavior
WHERE ShellSpellID IN (@wm_broug_deflect_shell_spell_id, @wm_broug_auto_retaliation_shell_spell_id)
ORDER BY ShellSpellID;

SELECT
    'broug_guard_reward_quests' AS metric,
    ID AS quest_id,
    LogTitle AS value
FROM quest_template
WHERE ID IN (@wm_broug_parry_quest_id, @wm_broug_deflect_quest_id)
ORDER BY ID;
