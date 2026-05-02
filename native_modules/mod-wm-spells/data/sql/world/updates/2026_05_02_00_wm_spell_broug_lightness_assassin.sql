-- Broug Lightness Assassin V1.
-- Fresh visible IDs only. The guard/parry kit remains a completed foundation, not the center of this arc.

SET @wm_broug_cloud_step_shell_spell_id := 946202;
SET @wm_broug_marked_meridian_shell_spell_id := 946203;
SET @wm_broug_killing_intent_shell_spell_id := 946620;
SET @wm_broug_silent_meridian_shell_spell_id := 946803;
SET @wm_broug_steps_quest_id := 910182;
SET @wm_broug_no_footfall_quest_id := 910183;
SET @wm_broug_cloud_step_credit_entry := 920106;
-- Verified 2026-05-02 in BridgeLab: level 20-21, faction template 87 is hostile to Alliance players
-- (FactionGroup 8, EnemyGroup 1), with 52 map 0 spawns.
SET @wm_broug_syndicate_watchman_entry := 2261;
SET @wm_broug_questgiver_entry := 332;
SET @wm_broug_player_guid := 5405;

CREATE TABLE IF NOT EXISTS wm_broug_lightness_counter (
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
        @wm_broug_cloud_step_shell_spell_id,
        'broug_cloud_step_v1',
        'unit_target_effect',
        'Cloud Step',
        'planned',
        'wm_spell_shell_bank.v2',
        'wm.spell_shell:broug_cloud_step_v1',
        '{"arc_key":"broug_lightness_assassin_v1","notes":["Broug-scoped movement-charge shell. Native runtime owns target validation, landing, energy, cooldown, Killing Intent, and Marked Meridian."]}'
    ),
    (
        @wm_broug_marked_meridian_shell_spell_id,
        'broug_marked_meridian_v1',
        'unit_target_effect',
        'Marked Meridian',
        'planned',
        'wm_spell_shell_bank.v2',
        'wm.spell_shell:broug_marked_meridian_v1',
        '{"arc_key":"broug_lightness_assassin_v1","notes":["Visible target mark consumed by Broug lightness followup hits. Vulnerable stacks are not consumed or modified by this V1 marker."]}'
    ),
    (
        @wm_broug_killing_intent_shell_spell_id,
        'broug_killing_intent_v1',
        'self_aura',
        'Killing Intent',
        'planned',
        'wm_spell_shell_bank.v2',
        'wm.spell_shell:broug_killing_intent_v1',
        '{"arc_key":"broug_lightness_assassin_v1","notes":["Visible self marker for Cloud Step followup timing. Uses 946620 to avoid the parallel Energy Surge Potion claim on 946606/910014."]}'
    ),
    (
        @wm_broug_silent_meridian_shell_spell_id,
        'broug_silent_meridian_v1',
        'passive_aura',
        'Silent Meridian Manual',
        'planned',
        'wm_spell_shell_bank.v2',
        'wm.spell_shell:broug_silent_meridian_v1',
        '{"arc_key":"broug_lightness_assassin_v1","notes":["Broug-scoped passive reward. Native runtime owns kill-window energy return and Cloud Step cooldown reduction."]}'
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
        @wm_broug_cloud_step_shell_spell_id,
        'broug_cloud_step_v1',
        JSON_OBJECT(
            'min_range_yards', 0.0,
            'max_range_yards', 25.0,
            'landing_distance_yards', 1.8,
            'cooldown_ms', 12000,
            'energy_cost', 20,
            'killing_intent_spell_id', @wm_broug_killing_intent_shell_spell_id,
            'killing_intent_duration_ms', 10000,
            'marked_meridian_spell_id', @wm_broug_marked_meridian_shell_spell_id,
            'marked_meridian_duration_ms', 12000,
            'damage_bonus_pct', 35,
            'departure_visual_spell_id', 24222,
            'arrival_visual_spell_id', 24222,
            'counter_key', 'cloud_step_strike',
            'credit_creature_entry', @wm_broug_cloud_step_credit_entry
        ),
        'active'
    ),
    (
        @wm_broug_marked_meridian_shell_spell_id,
        'broug_marked_meridian_v1',
        JSON_OBJECT(
            'source_shell_id', @wm_broug_cloud_step_shell_spell_id,
            'damage_bonus_pct', 35,
            'duration_ms', 12000,
            'vulnerable_stack_interaction', 'none'
        ),
        'active'
    ),
    (
        @wm_broug_killing_intent_shell_spell_id,
        'broug_killing_intent_v1',
        JSON_OBJECT(
            'source_shell_id', @wm_broug_cloud_step_shell_spell_id,
            'duration_ms', 10000
        ),
        'active'
    ),
    (
        @wm_broug_silent_meridian_shell_spell_id,
        'broug_silent_meridian_v1',
        JSON_OBJECT(
            'kill_window_ms', 10000,
            'energy_restore', 10,
            'cooldown_reduction_ms', 6000,
            'counter_key', 'silent_meridian_kill'
        ),
        'active'
    )
ON DUPLICATE KEY UPDATE
    BehaviorKind = VALUES(BehaviorKind),
    ConfigJSON = VALUES(ConfigJSON),
    Status = VALUES(Status),
    UpdatedAt = CURRENT_TIMESTAMP;

DELETE FROM spell_script_names
WHERE spell_id = @wm_broug_cloud_step_shell_spell_id
  AND ScriptName = 'spell_wm_shell_dispatch';

INSERT INTO spell_script_names (spell_id, ScriptName)
VALUES (@wm_broug_cloud_step_shell_spell_id, 'spell_wm_shell_dispatch');

INSERT INTO spell_cooldown_overrides
    (Id, RecoveryTime, CategoryRecoveryTime, StartRecoveryTime, StartRecoveryCategory, Comment)
VALUES
    (@wm_broug_cloud_step_shell_spell_id, 12000, 1000, 1000, 0, 'WM Broug Cloud Step native movement-charge shell')
ON DUPLICATE KEY UPDATE
    RecoveryTime = VALUES(RecoveryTime),
    CategoryRecoveryTime = VALUES(CategoryRecoveryTime),
    StartRecoveryTime = VALUES(StartRecoveryTime),
    StartRecoveryCategory = VALUES(StartRecoveryCategory),
    Comment = VALUES(Comment);

INSERT INTO creature_template
    (entry, name, subname, minlevel, maxlevel, faction, npcflag, unit_class, type, VerifiedBuild)
VALUES
    (@wm_broug_cloud_step_credit_entry, 'WM Broug Cloud Step Credit', 'Hidden quest credit only', 1, 1, 35, 0, 1, 10, 12340)
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

DELETE FROM creature_queststarter WHERE quest IN (@wm_broug_steps_quest_id, @wm_broug_no_footfall_quest_id);
DELETE FROM creature_questender WHERE quest IN (@wm_broug_steps_quest_id, @wm_broug_no_footfall_quest_id);
DELETE FROM quest_offer_reward WHERE ID IN (@wm_broug_steps_quest_id, @wm_broug_no_footfall_quest_id);
DELETE FROM quest_request_items WHERE ID IN (@wm_broug_steps_quest_id, @wm_broug_no_footfall_quest_id);
DELETE FROM quest_template_addon WHERE ID IN (@wm_broug_steps_quest_id, @wm_broug_no_footfall_quest_id);
DELETE FROM quest_template WHERE ID IN (@wm_broug_steps_quest_id, @wm_broug_no_footfall_quest_id);

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
        RewardDisplaySpell,
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
        @wm_broug_steps_quest_id,
        2,
        20,
        20,
        0,
        0,
        @wm_broug_no_footfall_quest_id,
        0,
        0,
        0,
        @wm_broug_cloud_step_shell_spell_id,
        8,
        0,
        'Broug: Steps Without Dust',
        'Defeat 8 Syndicate Watchmen while Shaw watches your footwork.',
        'The guard has already taught your hands to survive. Now make your feet disappear. Cut down Syndicate Watchmen without leaving the same line twice.',
        'Return to Master Mathias Shaw after the Syndicate Watchmen are dealt with.',
        @wm_broug_syndicate_watchman_entry,
        8,
        'Syndicate Watchmen defeated',
        12340
    ),
    (
        @wm_broug_no_footfall_quest_id,
        2,
        20,
        20,
        0,
        0,
        0,
        0,
        0,
        0,
        @wm_broug_silent_meridian_shell_spell_id,
        8,
        0,
        'Broug: No Footfall Twice',
        'Land 20 empowered hits by consuming Marked Meridian after Cloud Step.',
        'A step is only worth taking if the strike arrives before the dust remembers you. Use Cloud Step, mark your target, and land empowered followups.',
        'Return after twenty Cloud Step followup strikes.',
        @wm_broug_cloud_step_credit_entry,
        20,
        'Cloud Step empowered strikes',
        12340
    );

INSERT INTO quest_template_addon
    (ID, PrevQuestID, NextQuestID, SpecialFlags)
VALUES
    (@wm_broug_steps_quest_id, 0, @wm_broug_no_footfall_quest_id, 0),
    (@wm_broug_no_footfall_quest_id, @wm_broug_steps_quest_id, 0, 0)
ON DUPLICATE KEY UPDATE
    PrevQuestID = VALUES(PrevQuestID),
    NextQuestID = VALUES(NextQuestID),
    SpecialFlags = VALUES(SpecialFlags);

INSERT INTO quest_request_items (ID, CompletionText, VerifiedBuild)
VALUES
    (@wm_broug_steps_quest_id, 'You have stopped repeating your footing. The next lesson is a cut between heartbeats.', 12340),
    (@wm_broug_no_footfall_quest_id, 'Twenty strikes, no second footfall. The manual is yours.', 12340)
ON DUPLICATE KEY UPDATE
    CompletionText = VALUES(CompletionText),
    VerifiedBuild = VALUES(VerifiedBuild);

INSERT INTO quest_offer_reward (ID, RewardText, VerifiedBuild)
VALUES
    (@wm_broug_steps_quest_id, 'You learn Cloud Step.', 12340),
    (@wm_broug_no_footfall_quest_id, 'You learn Silent Meridian Manual.', 12340)
ON DUPLICATE KEY UPDATE
    RewardText = VALUES(RewardText),
    VerifiedBuild = VALUES(VerifiedBuild);

INSERT INTO creature_queststarter (id, quest)
VALUES
    (@wm_broug_questgiver_entry, @wm_broug_steps_quest_id),
    (@wm_broug_questgiver_entry, @wm_broug_no_footfall_quest_id);

INSERT INTO creature_questender (id, quest)
VALUES
    (@wm_broug_questgiver_entry, @wm_broug_steps_quest_id),
    (@wm_broug_questgiver_entry, @wm_broug_no_footfall_quest_id);

INSERT INTO wm_reserved_slot
    (EntityType, ReservedID, SlotStatus, ArcKey, CharacterGUID, SourceQuestID, NotesJSON)
VALUES
    ('spell', @wm_broug_cloud_step_shell_spell_id, 'active', 'broug_lightness_assassin_v1', @wm_broug_player_guid, @wm_broug_steps_quest_id, '{"key":"broug_cloud_step_v1"}'),
    ('spell', @wm_broug_marked_meridian_shell_spell_id, 'active', 'broug_lightness_assassin_v1', @wm_broug_player_guid, @wm_broug_steps_quest_id, '{"key":"broug_marked_meridian_v1"}'),
    ('spell', @wm_broug_killing_intent_shell_spell_id, 'active', 'broug_lightness_assassin_v1', @wm_broug_player_guid, @wm_broug_steps_quest_id, '{"key":"broug_killing_intent_v1","avoids_parallel_claim":946606}'),
    ('spell', @wm_broug_silent_meridian_shell_spell_id, 'active', 'broug_lightness_assassin_v1', @wm_broug_player_guid, @wm_broug_no_footfall_quest_id, '{"key":"broug_silent_meridian_v1"}'),
    ('quest', @wm_broug_steps_quest_id, 'active', 'broug_lightness_assassin_v1', @wm_broug_player_guid, NULL, '{"key":"broug_steps_without_dust"}'),
    ('quest', @wm_broug_no_footfall_quest_id, 'active', 'broug_lightness_assassin_v1', @wm_broug_player_guid, @wm_broug_steps_quest_id, '{"key":"broug_no_footfall_twice"}'),
    ('creature_template', @wm_broug_cloud_step_credit_entry, 'active', 'broug_lightness_assassin_v1', @wm_broug_player_guid, @wm_broug_no_footfall_quest_id, '{"key":"broug_cloud_step_credit"}')
ON DUPLICATE KEY UPDATE
    SlotStatus = VALUES(SlotStatus),
    ArcKey = VALUES(ArcKey),
    CharacterGUID = VALUES(CharacterGUID),
    SourceQuestID = VALUES(SourceQuestID),
    NotesJSON = VALUES(NotesJSON);

SELECT
    'broug_lightness_behavior' AS metric,
    ShellSpellID AS shell_spell_id,
    BehaviorKind AS value,
    Status AS status
FROM wm_spell_behavior
WHERE ShellSpellID IN (
    @wm_broug_cloud_step_shell_spell_id,
    @wm_broug_marked_meridian_shell_spell_id,
    @wm_broug_killing_intent_shell_spell_id,
    @wm_broug_silent_meridian_shell_spell_id
)
ORDER BY ShellSpellID;
