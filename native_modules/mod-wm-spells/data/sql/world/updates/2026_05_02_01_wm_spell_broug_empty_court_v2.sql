-- Broug Empty Court V2: First Peak.
-- Stock-world anchors plus custom Wei Jin trials. No new parry behavior and no Vulnerable stack mutation.

SET @wm_broug_player_guid := 5405;
SET @wm_broug_weight_quest_id := 910184;
SET @wm_broug_stilling_quest_id := 910185;
SET @wm_broug_ninety_eight_quest_id := 910186;
SET @wm_broug_room_quest_id := 910187;
SET @wm_broug_domain_unsealed_quest_id := 910188;
SET @wm_broug_gryan_stoutmantle_entry := 234;
SET @wm_broug_defias_knuckleduster_entry := 449;
SET @wm_broug_defias_trapper_entry := 504;
SET @wm_broug_wei_jin_entry := 915500;
SET @wm_broug_ash_hushed_wolf_entry := 915510;
SET @wm_broug_ash_hushed_boar_entry := 915511;
SET @wm_broug_ash_hushed_bear_entry := 915512;
SET @wm_broug_hal_morrow_entry := 915520;
SET @wm_broug_silent_hall_first_entry := 915530;
SET @wm_broug_silent_hall_last_entry := 915539;
SET @wm_broug_court_remnant_entry := 915540;
SET @wm_broug_ash_worn_track_go := 195500;
SET @wm_broug_bolted_cellar_hatch_go := 195501;
SET @wm_broug_stillness_credit_entry := 920107;
SET @wm_broug_bounty_credit_entry := 920108;
SET @wm_broug_room_credit_entry := 920109;
SET @wm_broug_oath_credit_entry := 920110;
SET @wm_broug_suppressed_shell_spell_id := 946204;
SET @wm_broug_qi_reversal_shell_spell_id := 946621;
SET @wm_broug_purged_state_shell_spell_id := 946622;
SET @wm_broug_killing_intent_domain_shell_spell_id := 946804;
SET @wm_broug_predators_strike_shell_spell_id := 946805;
SET @wm_broug_vitality_drain_shell_spell_id := 946806;
SET @wm_broug_killing_intent_shell_spell_id := 946620;

CREATE TABLE IF NOT EXISTS wm_broug_empty_court_counter (
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
        @wm_broug_suppressed_shell_spell_id,
        'broug_suppressed_v1',
        'unit_target_effect',
        'Suppressed',
        'planned',
        'wm_spell_shell_bank.v2',
        'wm.spell_shell:broug_suppressed_v1',
        '{"arc_key":"broug_empty_court_v2","notes":["Visible enemy pressure state from Killing Intent: Domain pulses. Native runtime owns boss-safe damage pressure."]}'
    ),
    (
        @wm_broug_qi_reversal_shell_spell_id,
        'broug_qi_reversal_v1',
        'self_aura',
        'Qi Reversal',
        'planned',
        'wm_spell_shell_bank.v2',
        'wm.spell_shell:broug_qi_reversal_v1',
        '{"arc_key":"broug_empty_court_v2","notes":["Active Broug-only cleanse shell. Native runtime removes harmful Magic, Poison, and Disease auras and applies Purged State."]}'
    ),
    (
        @wm_broug_purged_state_shell_spell_id,
        'broug_purged_state_v1',
        'self_aura',
        'Purged State',
        'planned',
        'wm_spell_shell_bank.v2',
        'wm.spell_shell:broug_purged_state_v1',
        '{"arc_key":"broug_empty_court_v2","notes":["Visible self state after Qi Reversal. Native runtime tracks two reapplication blocks for cleansed aura types."]}'
    ),
    (
        @wm_broug_killing_intent_domain_shell_spell_id,
        'broug_killing_intent_domain_v1',
        'passive_aura',
        'Killing Intent: Domain',
        'planned',
        'wm_spell_shell_bank.v2',
        'wm.spell_shell:broug_killing_intent_domain_v1',
        '{"arc_key":"broug_empty_court_v2","notes":["Passive reward that upgrades Cloud Step Killing Intent to a 15-second Domain window with repeated Suppressed pulses."]}'
    ),
    (
        @wm_broug_predators_strike_shell_spell_id,
        'broug_predators_strike_v1',
        'passive_aura',
        'Predator''s Strike',
        'planned',
        'wm_spell_shell_bank.v2',
        'wm.spell_shell:broug_predators_strike_v1',
        '{"arc_key":"broug_empty_court_v2","notes":["Passive reward. Native runtime heals Broug from actual damage dealt when Marked Meridian is consumed."]}'
    ),
    (
        @wm_broug_vitality_drain_shell_spell_id,
        'broug_vitality_drain_v1',
        'passive_aura',
        'Vitality Drain',
        'planned',
        'wm_spell_shell_bank.v2',
        'wm.spell_shell:broug_vitality_drain_v1',
        '{"arc_key":"broug_empty_court_v2","notes":["Passive reward. Native runtime heals on Broug killing blows, with a larger Silent Meridian kill-window payoff."]}'
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
        @wm_broug_suppressed_shell_spell_id,
        'broug_suppressed_v1',
        JSON_OBJECT(
            'duration_ms', 12000,
            'boss_safe', true,
            'stock_refs', JSON_ARRAY('Thunder Clap', 'Curse of Tongues', 'Deadly Throw')
        ),
        'active'
    ),
    (
        @wm_broug_qi_reversal_shell_spell_id,
        'broug_qi_reversal_v1',
        JSON_OBJECT(
            'purged_state_spell_id', @wm_broug_purged_state_shell_spell_id,
            'max_magic', 3,
            'max_poison', 2,
            'max_disease', 1,
            'purged_duration_ms', 30000,
            'purged_charges', 2,
            'counter_key', 'qi_reversal_cleanse',
            'stock_refs', JSON_ARRAY('Stoneform', 'Cloak of Shadows')
        ),
        'active'
    ),
    (
        @wm_broug_purged_state_shell_spell_id,
        'broug_purged_state_v1',
        JSON_OBJECT(
            'duration_ms', 30000,
            'charges', 2
        ),
        'active'
    ),
    (
        @wm_broug_killing_intent_domain_shell_spell_id,
        'broug_killing_intent_domain_v1',
        JSON_OBJECT(
            'killing_intent_spell_id', @wm_broug_killing_intent_shell_spell_id,
            'suppressed_spell_id', @wm_broug_suppressed_shell_spell_id,
            'base_killing_intent_duration_ms', 15000,
            'pulse_interval_ms', 2000,
            'suppressed_duration_ms', 12000,
            'death_extension_ms', 5000,
            'radius_yards', 8.0,
            'suppressed_damage_pressure_pct', 10,
            'pulse_counter_key', 'domain_pulse',
            'death_extend_counter_key', 'suppressed_death_extend',
            'player_facing_cap', 'none',
            'cleanup_policy', 'logout_death_map_unload_aura_loss'
        ),
        'active'
    ),
    (
        @wm_broug_predators_strike_shell_spell_id,
        'broug_predators_strike_v1',
        JSON_OBJECT(
            'heal_pct_of_damage', 25,
            'counter_key', 'predator_heal',
            'stock_ref', 'Death Strike'
        ),
        'active'
    ),
    (
        @wm_broug_vitality_drain_shell_spell_id,
        'broug_vitality_drain_v1',
        JSON_OBJECT(
            'kill_heal_pct_max_health', 5,
            'silent_window_kill_heal_pct_max_health', 15,
            'silent_window_energy_bonus', 10,
            'counter_key', 'vitality_kill',
            'stock_ref', 'Victory Rush'
        ),
        'active'
    )
ON DUPLICATE KEY UPDATE
    BehaviorKind = VALUES(BehaviorKind),
    ConfigJSON = VALUES(ConfigJSON),
    Status = VALUES(Status),
    UpdatedAt = CURRENT_TIMESTAMP;

DELETE FROM spell_script_names
WHERE spell_id = @wm_broug_qi_reversal_shell_spell_id
  AND ScriptName = 'spell_wm_shell_dispatch';

INSERT INTO spell_script_names (spell_id, ScriptName)
VALUES (@wm_broug_qi_reversal_shell_spell_id, 'spell_wm_shell_dispatch');

INSERT INTO spell_cooldown_overrides
    (Id, RecoveryTime, CategoryRecoveryTime, StartRecoveryTime, StartRecoveryCategory, Comment)
VALUES
    (@wm_broug_qi_reversal_shell_spell_id, 45000, 1000, 1000, 0, 'WM Broug Qi Reversal active cleanse shell')
ON DUPLICATE KEY UPDATE
    RecoveryTime = VALUES(RecoveryTime),
    CategoryRecoveryTime = VALUES(CategoryRecoveryTime),
    StartRecoveryTime = VALUES(StartRecoveryTime),
    StartRecoveryCategory = VALUES(StartRecoveryCategory),
    Comment = VALUES(Comment);

INSERT INTO creature_template
    (entry, name, subname, minlevel, maxlevel, faction, npcflag, unit_class, type, KillCredit1, VerifiedBuild)
VALUES
    (@wm_broug_wei_jin_entry, 'Wei Jin, Last of the Empty Court', 'Empty Court Mentor', 20, 20, 35, 3, 1, 7, 0, 12340),
    (@wm_broug_ash_hushed_wolf_entry, 'Ash-Hushed Wolf', 'Stillness Trial', 20, 20, 14, 0, 1, 1, @wm_broug_stillness_credit_entry, 12340),
    (@wm_broug_ash_hushed_boar_entry, 'Ash-Hushed Boar', 'Stillness Trial', 20, 20, 14, 0, 1, 1, @wm_broug_stillness_credit_entry, 12340),
    (@wm_broug_ash_hushed_bear_entry, 'Ash-Hushed Bear', 'Stillness Trial', 20, 20, 14, 0, 1, 1, @wm_broug_stillness_credit_entry, 12340),
    (@wm_broug_hal_morrow_entry, 'Hal Morrow', 'Defias Bounty Captain', 20, 20, 14, 0, 1, 7, 0, 12340),
    (@wm_broug_court_remnant_entry, 'Court Remnant', 'Empty Court Echo', 21, 21, 14, 0, 1, 10, @wm_broug_oath_credit_entry, 12340),
    (@wm_broug_stillness_credit_entry, 'WM Broug Stillness Trial Credit', 'Hidden quest credit only', 1, 1, 35, 0, 1, 10, 0, 12340),
    (@wm_broug_bounty_credit_entry, 'WM Broug Bounty Credit', 'Hidden reserved credit only', 1, 1, 35, 0, 1, 10, 0, 12340),
    (@wm_broug_room_credit_entry, 'WM Broug Silent Hall Credit', 'Hidden quest credit only', 1, 1, 35, 0, 1, 10, 0, 12340),
    (@wm_broug_oath_credit_entry, 'WM Broug Oath Duel Credit', 'Hidden quest credit only', 1, 1, 35, 0, 1, 10, 0, 12340)
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    subname = VALUES(subname),
    minlevel = VALUES(minlevel),
    maxlevel = VALUES(maxlevel),
    faction = VALUES(faction),
    npcflag = VALUES(npcflag),
    unit_class = VALUES(unit_class),
    type = VALUES(type),
    KillCredit1 = VALUES(KillCredit1),
    VerifiedBuild = VALUES(VerifiedBuild);

INSERT INTO creature_template
    (entry, name, subname, minlevel, maxlevel, faction, npcflag, unit_class, type, KillCredit1, VerifiedBuild)
SELECT
    seq.entry,
    CONCAT('Moonbrook Silent Hall Actor ', seq.entry - @wm_broug_silent_hall_first_entry + 1),
    'Empty Court Trial',
    20,
    20,
    14,
    0,
    1,
    7,
    @wm_broug_room_credit_entry,
    12340
FROM (
    SELECT 915530 AS entry UNION ALL SELECT 915531 UNION ALL SELECT 915532 UNION ALL SELECT 915533 UNION ALL SELECT 915534
    UNION ALL SELECT 915535 UNION ALL SELECT 915536 UNION ALL SELECT 915537 UNION ALL SELECT 915538 UNION ALL SELECT 915539
) AS seq
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    subname = VALUES(subname),
    minlevel = VALUES(minlevel),
    maxlevel = VALUES(maxlevel),
    faction = VALUES(faction),
    npcflag = VALUES(npcflag),
    unit_class = VALUES(unit_class),
    type = VALUES(type),
    KillCredit1 = VALUES(KillCredit1),
    VerifiedBuild = VALUES(VerifiedBuild);

INSERT INTO creature_template_model
    (CreatureID, Idx, CreatureDisplayID, DisplayScale, Probability, VerifiedBuild)
VALUES
    (@wm_broug_wei_jin_entry, 0, 1736, 1.0, 1.0, 12340),
    (@wm_broug_ash_hushed_wolf_entry, 0, 11415, 1.0, 1.0, 12340),
    (@wm_broug_ash_hushed_boar_entry, 0, 3035, 1.0, 1.0, 12340),
    (@wm_broug_ash_hushed_bear_entry, 0, 1006, 1.0, 1.0, 12340),
    (@wm_broug_hal_morrow_entry, 0, 2344, 1.0, 1.0, 12340),
    (915530, 0, 2344, 1.0, 1.0, 12340),
    (915531, 0, 2331, 1.0, 1.0, 12340),
    (915532, 0, 2345, 1.0, 1.0, 12340),
    (915533, 0, 2332, 1.0, 1.0, 12340),
    (915534, 0, 2344, 1.0, 1.0, 12340),
    (915535, 0, 2331, 1.0, 1.0, 12340),
    (915536, 0, 2345, 1.0, 1.0, 12340),
    (915537, 0, 2332, 1.0, 1.0, 12340),
    (915538, 0, 2344, 1.0, 1.0, 12340),
    (915539, 0, 2331, 1.0, 1.0, 12340),
    (@wm_broug_court_remnant_entry, 0, 1736, 1.0, 1.0, 12340),
    (@wm_broug_stillness_credit_entry, 0, 1736, 1.0, 1.0, 12340),
    (@wm_broug_bounty_credit_entry, 0, 1736, 1.0, 1.0, 12340),
    (@wm_broug_room_credit_entry, 0, 1736, 1.0, 1.0, 12340),
    (@wm_broug_oath_credit_entry, 0, 1736, 1.0, 1.0, 12340)
ON DUPLICATE KEY UPDATE
    CreatureDisplayID = VALUES(CreatureDisplayID),
    DisplayScale = VALUES(DisplayScale),
    Probability = VALUES(Probability),
    VerifiedBuild = VALUES(VerifiedBuild);

DELETE FROM creature
WHERE id1 IN (
    @wm_broug_wei_jin_entry,
    @wm_broug_ash_hushed_wolf_entry,
    @wm_broug_ash_hushed_boar_entry,
    @wm_broug_ash_hushed_bear_entry,
    @wm_broug_hal_morrow_entry,
    @wm_broug_court_remnant_entry
)
OR id1 BETWEEN @wm_broug_silent_hall_first_entry AND @wm_broug_silent_hall_last_entry;

INSERT INTO creature
    (guid, id1, id2, id3, map, zoneId, areaId, spawnMask, phaseMask, equipment_id, position_x, position_y, position_z, orientation, spawntimesecs, wander_distance, currentwaypoint, curhealth, curmana, MovementType, npcflag, unit_flags, dynamicflags, VerifiedBuild)
VALUES
    (1915500, @wm_broug_wei_jin_entry, 0, 0, 0, 40, 0, 1, 1, 0, -10810.0, 875.0, 36.0, 2.70, 300, 0, 0, 1400, 0, 0, 3, 0, 0, 12340),
    (1915510, @wm_broug_ash_hushed_wolf_entry, 0, 0, 0, 40, 0, 1, 1, 0, -10824.0, 862.0, 35.8, 0.10, 300, 3, 0, 1200, 0, 1, 0, 0, 0, 12340),
    (1915511, @wm_broug_ash_hushed_boar_entry, 0, 0, 0, 40, 0, 1, 1, 0, -10804.0, 858.0, 36.0, 1.10, 300, 3, 0, 1300, 0, 1, 0, 0, 0, 12340),
    (1915512, @wm_broug_ash_hushed_bear_entry, 0, 0, 0, 40, 0, 1, 1, 0, -10796.0, 884.0, 36.2, 3.80, 300, 2, 0, 1700, 0, 1, 0, 0, 0, 12340),
    (1915520, @wm_broug_hal_morrow_entry, 0, 0, 0, 40, 0, 1, 1, 0, -11042.0, 1503.0, 44.8, 4.60, 300, 2, 0, 1600, 0, 1, 0, 0, 0, 12340),
    (1915530, 915530, 0, 0, 0, 40, 0, 1, 1, 0, -11090.0, 1541.0, 45.8, 3.14, 300, 0, 0, 1300, 0, 0, 0, 0, 0, 12340),
    (1915531, 915531, 0, 0, 0, 40, 0, 1, 1, 0, -11094.0, 1535.0, 45.9, 3.14, 300, 0, 0, 1300, 0, 0, 0, 0, 0, 12340),
    (1915532, 915532, 0, 0, 0, 40, 0, 1, 1, 0, -11099.0, 1543.0, 46.0, 3.14, 300, 0, 0, 1300, 0, 0, 0, 0, 0, 12340),
    (1915533, 915533, 0, 0, 0, 40, 0, 1, 1, 0, -11104.0, 1538.0, 45.8, 3.14, 300, 0, 0, 1300, 0, 0, 0, 0, 0, 12340),
    (1915534, 915534, 0, 0, 0, 40, 0, 1, 1, 0, -11100.0, 1531.0, 45.7, 3.14, 300, 0, 0, 1300, 0, 0, 0, 0, 0, 12340),
    (1915535, 915535, 0, 0, 0, 40, 0, 1, 1, 0, -11088.0, 1531.0, 45.7, 3.14, 300, 0, 0, 1300, 0, 0, 0, 0, 0, 12340),
    (1915536, 915536, 0, 0, 0, 40, 0, 1, 1, 0, -11084.0, 1538.0, 45.8, 3.14, 300, 0, 0, 1300, 0, 0, 0, 0, 0, 12340),
    (1915537, 915537, 0, 0, 0, 40, 0, 1, 1, 0, -11091.0, 1548.0, 46.1, 3.14, 300, 0, 0, 1300, 0, 0, 0, 0, 0, 12340),
    (1915538, 915538, 0, 0, 0, 40, 0, 1, 1, 0, -11108.0, 1546.0, 46.0, 3.14, 300, 0, 0, 1300, 0, 0, 0, 0, 0, 12340),
    (1915539, 915539, 0, 0, 0, 40, 0, 1, 1, 0, -11110.0, 1534.0, 45.7, 3.14, 300, 0, 0, 1300, 0, 0, 0, 0, 0, 12340),
    (1915540, @wm_broug_court_remnant_entry, 0, 0, 0, 40, 0, 1, 1, 0, -10830.0, 902.0, 37.0, 4.00, 300, 2, 0, 1800, 0, 1, 0, 0, 0, 12340);

INSERT INTO gameobject_template
    (entry, type, displayId, name, IconName, castBarCaption, unk1, size, Data0, Data1, Data2, Data3, Data4, Data5, Data6, Data7, Data8, Data9, Data10, Data11, Data12, Data13, Data14, Data15, Data16, Data17, Data18, Data19, Data20, Data21, Data22, Data23, AIName, ScriptName, VerifiedBuild)
VALUES
    (@wm_broug_ash_worn_track_go, 10, 8298, 'Ash-Worn Track Circle', '', 'Inspecting', '', 0.75, 0, @wm_broug_weight_quest_id, 0, 3000, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '', '', 12340),
    (@wm_broug_bolted_cellar_hatch_go, 10, 8413, 'Bolted Cellar Hatch', '', 'Opening', '', 0.75, 0, @wm_broug_room_quest_id, 0, 3000, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '', '', 12340)
ON DUPLICATE KEY UPDATE
    type = VALUES(type),
    displayId = VALUES(displayId),
    name = VALUES(name),
    IconName = VALUES(IconName),
    castBarCaption = VALUES(castBarCaption),
    size = VALUES(size),
    VerifiedBuild = VALUES(VerifiedBuild);

DELETE FROM gameobject WHERE id IN (@wm_broug_ash_worn_track_go, @wm_broug_bolted_cellar_hatch_go);

INSERT INTO gameobject
    (guid, id, map, zoneId, areaId, spawnMask, phaseMask, position_x, position_y, position_z, orientation, rotation0, rotation1, rotation2, rotation3, spawntimesecs, animprogress, state, VerifiedBuild)
VALUES
    (1195500, @wm_broug_ash_worn_track_go, 0, 40, 0, 1, 1, -10752.0, 990.0, 48.0, 2.40, 0, 0, 0.932039, 0.362358, 300, 255, 1, 12340),
    (1195501, @wm_broug_bolted_cellar_hatch_go, 0, 40, 0, 1, 1, -11095.0, 1538.0, 46.0, 0.80, 0, 0, 0.389418, 0.921061, 300, 255, 1, 12340);

DELETE FROM creature_queststarter
WHERE quest IN (@wm_broug_weight_quest_id, @wm_broug_stilling_quest_id, @wm_broug_ninety_eight_quest_id, @wm_broug_room_quest_id, @wm_broug_domain_unsealed_quest_id);
DELETE FROM creature_questender
WHERE quest IN (@wm_broug_weight_quest_id, @wm_broug_stilling_quest_id, @wm_broug_ninety_eight_quest_id, @wm_broug_room_quest_id, @wm_broug_domain_unsealed_quest_id);
DELETE FROM quest_offer_reward
WHERE ID IN (@wm_broug_weight_quest_id, @wm_broug_stilling_quest_id, @wm_broug_ninety_eight_quest_id, @wm_broug_room_quest_id, @wm_broug_domain_unsealed_quest_id);
DELETE FROM quest_request_items
WHERE ID IN (@wm_broug_weight_quest_id, @wm_broug_stilling_quest_id, @wm_broug_ninety_eight_quest_id, @wm_broug_room_quest_id, @wm_broug_domain_unsealed_quest_id);
DELETE FROM quest_template_addon
WHERE ID IN (@wm_broug_weight_quest_id, @wm_broug_stilling_quest_id, @wm_broug_ninety_eight_quest_id, @wm_broug_room_quest_id, @wm_broug_domain_unsealed_quest_id);
DELETE FROM quest_template
WHERE ID IN (@wm_broug_weight_quest_id, @wm_broug_stilling_quest_id, @wm_broug_ninety_eight_quest_id, @wm_broug_room_quest_id, @wm_broug_domain_unsealed_quest_id);

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
        RequiredNpcOrGo2,
        RequiredNpcOrGoCount2,
        RequiredNpcOrGo3,
        RequiredNpcOrGoCount3,
        ObjectiveText1,
        ObjectiveText2,
        ObjectiveText3,
        VerifiedBuild
    )
VALUES
    (
        @wm_broug_weight_quest_id,
        2,
        20,
        20,
        0,
        0,
        @wm_broug_stilling_quest_id,
        0,
        0,
        0,
        0,
        8,
        0,
        'Broug: The Weight Before the Blade',
        'From Gryan, follow the road west/southwest out of Sentinel Hill. Click Ash-Worn Track Circle at -10752, 990, 48, then speak to Wei Jin at -10810, 875, 36.',
        'Gryan has seen a track circle burned into the road dust. It is too deliberate for Defias work. Follow it and find the man who left it.',
        'Speak with Wei Jin near the Dead Acre edge.',
        -@wm_broug_ash_worn_track_go,
        1,
        0,
        0,
        0,
        0,
        'Ash-Worn Track Circle inspected',
        '',
        '',
        12340
    ),
    (
        @wm_broug_stilling_quest_id,
        2,
        20,
        20,
        0,
        0,
        @wm_broug_ninety_eight_quest_id,
        0,
        0,
        0,
        @wm_broug_qi_reversal_shell_spell_id,
        8,
        0,
        'Broug: Stilling the Water',
        'At Wei Jin''s camp near -10810, 875, 36, kill the Ash-Hushed Wolf, Ash-Hushed Boar, and Ash-Hushed Bear. Each kill gives one stillness credit.',
        'Do not meet motion with panic. Survive the stillness trials and learn how poison, sickness, and false qi are turned back through the same meridian.',
        'Return to Wei Jin after the three stillness trials.',
        @wm_broug_stillness_credit_entry,
        3,
        0,
        0,
        0,
        0,
        'Stillness trials completed',
        '',
        '',
        12340
    ),
    (
        @wm_broug_ninety_eight_quest_id,
        2,
        20,
        20,
        0,
        0,
        @wm_broug_room_quest_id,
        0,
        0,
        0,
        @wm_broug_predators_strike_shell_spell_id,
        8,
        0,
        'Broug: Ninety-Eight',
        'In and around Moonbrook, kill 6 Defias Knuckledusters and 6 Defias Trappers, then kill Hal Morrow near -11042, 1503, 45.',
        'The Empty Court counted breaths instead of bodies. Hal Morrow has hired the wrong hands to measure you. Break the count.',
        'Return to Wei Jin after Hal Morrow falls.',
        @wm_broug_defias_knuckleduster_entry,
        6,
        @wm_broug_defias_trapper_entry,
        6,
        @wm_broug_hal_morrow_entry,
        1,
        'Defias Knuckledusters slain',
        'Defias Trappers slain',
        'Hal Morrow slain',
        12340
    ),
    (
        @wm_broug_room_quest_id,
        2,
        20,
        20,
        0,
        0,
        @wm_broug_domain_unsealed_quest_id,
        0,
        0,
        0,
        @wm_broug_killing_intent_domain_shell_spell_id,
        8,
        0,
        'Broug: The Room That Silenced',
        'Go to Moonbrook and click Bolted Cellar Hatch at -11095, 1538, 46. Defeat the 10 Silent Hall actors around the hatch.',
        'A room can die before every body in it is still. Enter the cellar and make the hall learn your pressure.',
        'Return to Wei Jin after the Silent Hall breaks.',
        @wm_broug_room_credit_entry,
        10,
        0,
        0,
        0,
        0,
        'Silent Hall actors defeated',
        '',
        '',
        12340
    ),
    (
        @wm_broug_domain_unsealed_quest_id,
        2,
        20,
        20,
        0,
        0,
        0,
        0,
        0,
        0,
        @wm_broug_vitality_drain_shell_spell_id,
        8,
        0,
        'Broug: Domain Unsealed',
        'Return to Wei Jin''s camp, then defeat Court Remnant at the ruined watchfire near -10830, 902, 37.',
        'Wei Jin leaves you with one oath duel. The Remnant has no blood worth keeping, but it remembers the shape of hunger.',
        'Return to Wei Jin after the Court Remnant falls.',
        @wm_broug_oath_credit_entry,
        1,
        0,
        0,
        0,
        0,
        'Court Remnant defeated',
        '',
        '',
        12340
    );

INSERT INTO quest_template_addon (ID, PrevQuestID, NextQuestID, SpecialFlags)
VALUES
    (@wm_broug_weight_quest_id, 0, @wm_broug_stilling_quest_id, 0),
    (@wm_broug_stilling_quest_id, @wm_broug_weight_quest_id, @wm_broug_ninety_eight_quest_id, 0),
    (@wm_broug_ninety_eight_quest_id, @wm_broug_stilling_quest_id, @wm_broug_room_quest_id, 0),
    (@wm_broug_room_quest_id, @wm_broug_ninety_eight_quest_id, @wm_broug_domain_unsealed_quest_id, 0),
    (@wm_broug_domain_unsealed_quest_id, @wm_broug_room_quest_id, 0, 0)
ON DUPLICATE KEY UPDATE
    PrevQuestID = VALUES(PrevQuestID),
    NextQuestID = VALUES(NextQuestID),
    SpecialFlags = VALUES(SpecialFlags);

INSERT INTO quest_request_items (ID, CompletionText, VerifiedBuild)
VALUES
    (@wm_broug_weight_quest_id, 'The track circle was bait, but not for prey. Wei Jin waits where the road dust thins.', 12340),
    (@wm_broug_stilling_quest_id, 'Still water reflects the poison before it enters.', 12340),
    (@wm_broug_ninety_eight_quest_id, 'The hired hands are dead. Wei Jin counts what remained in your breath.', 12340),
    (@wm_broug_room_quest_id, 'The hall went quiet before the last blade fell.', 12340),
    (@wm_broug_domain_unsealed_quest_id, 'The oath duel is done. Nothing in the room died alone.', 12340)
ON DUPLICATE KEY UPDATE
    CompletionText = VALUES(CompletionText),
    VerifiedBuild = VALUES(VerifiedBuild);

INSERT INTO quest_offer_reward (ID, RewardText, VerifiedBuild)
VALUES
    (@wm_broug_weight_quest_id, 'Wei Jin agrees to teach the First Peak of the Empty Court.', 12340),
    (@wm_broug_stilling_quest_id, 'You learn Qi Reversal.', 12340),
    (@wm_broug_ninety_eight_quest_id, 'You learn Predator''s Strike.', 12340),
    (@wm_broug_room_quest_id, 'You learn Killing Intent: Domain.', 12340),
    (@wm_broug_domain_unsealed_quest_id, 'You learn Vitality Drain.', 12340)
ON DUPLICATE KEY UPDATE
    RewardText = VALUES(RewardText),
    VerifiedBuild = VALUES(VerifiedBuild);

INSERT INTO creature_queststarter (id, quest)
VALUES
    (@wm_broug_gryan_stoutmantle_entry, @wm_broug_weight_quest_id),
    (@wm_broug_wei_jin_entry, @wm_broug_stilling_quest_id),
    (@wm_broug_wei_jin_entry, @wm_broug_ninety_eight_quest_id),
    (@wm_broug_wei_jin_entry, @wm_broug_room_quest_id),
    (@wm_broug_wei_jin_entry, @wm_broug_domain_unsealed_quest_id);

INSERT INTO creature_questender (id, quest)
VALUES
    (@wm_broug_wei_jin_entry, @wm_broug_weight_quest_id),
    (@wm_broug_wei_jin_entry, @wm_broug_stilling_quest_id),
    (@wm_broug_wei_jin_entry, @wm_broug_ninety_eight_quest_id),
    (@wm_broug_wei_jin_entry, @wm_broug_room_quest_id),
    (@wm_broug_wei_jin_entry, @wm_broug_domain_unsealed_quest_id);

INSERT INTO wm_reserved_slot
    (EntityType, ReservedID, SlotStatus, ArcKey, CharacterGUID, SourceQuestID, NotesJSON)
VALUES
    ('spell', @wm_broug_suppressed_shell_spell_id, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_room_quest_id, '{"key":"broug_suppressed_v1","family":"unit_target_effect"}'),
    ('spell', @wm_broug_qi_reversal_shell_spell_id, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_stilling_quest_id, '{"key":"broug_qi_reversal_v1","family":"self_aura"}'),
    ('spell', @wm_broug_purged_state_shell_spell_id, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_stilling_quest_id, '{"key":"broug_purged_state_v1","family":"self_aura"}'),
    ('spell', @wm_broug_killing_intent_domain_shell_spell_id, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_room_quest_id, '{"key":"broug_killing_intent_domain_v1","family":"passive_aura"}'),
    ('spell', @wm_broug_predators_strike_shell_spell_id, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_ninety_eight_quest_id, '{"key":"broug_predators_strike_v1","family":"passive_aura"}'),
    ('spell', @wm_broug_vitality_drain_shell_spell_id, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_domain_unsealed_quest_id, '{"key":"broug_vitality_drain_v1","family":"passive_aura"}'),
    ('quest', @wm_broug_weight_quest_id, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, NULL, '{"key":"broug_weight_before_blade"}'),
    ('quest', @wm_broug_stilling_quest_id, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_weight_quest_id, '{"key":"broug_stilling_water"}'),
    ('quest', @wm_broug_ninety_eight_quest_id, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_stilling_quest_id, '{"key":"broug_ninety_eight"}'),
    ('quest', @wm_broug_room_quest_id, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_ninety_eight_quest_id, '{"key":"broug_room_that_silenced"}'),
    ('quest', @wm_broug_domain_unsealed_quest_id, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_room_quest_id, '{"key":"broug_domain_unsealed"}'),
    ('creature_template', @wm_broug_wei_jin_entry, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, NULL, '{"key":"wei_jin_empty_court"}'),
    ('creature_template', @wm_broug_ash_hushed_wolf_entry, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_stilling_quest_id, '{"key":"ash_hushed_wolf"}'),
    ('creature_template', @wm_broug_ash_hushed_boar_entry, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_stilling_quest_id, '{"key":"ash_hushed_boar"}'),
    ('creature_template', @wm_broug_ash_hushed_bear_entry, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_stilling_quest_id, '{"key":"ash_hushed_bear"}'),
    ('creature_template', @wm_broug_hal_morrow_entry, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_ninety_eight_quest_id, '{"key":"hal_morrow"}'),
    ('creature_template', @wm_broug_silent_hall_first_entry, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_room_quest_id, '{"key":"silent_hall_actor_1"}'),
    ('creature_template', 915531, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_room_quest_id, '{"key":"silent_hall_actor_2"}'),
    ('creature_template', 915532, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_room_quest_id, '{"key":"silent_hall_actor_3"}'),
    ('creature_template', 915533, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_room_quest_id, '{"key":"silent_hall_actor_4"}'),
    ('creature_template', 915534, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_room_quest_id, '{"key":"silent_hall_actor_5"}'),
    ('creature_template', 915535, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_room_quest_id, '{"key":"silent_hall_actor_6"}'),
    ('creature_template', 915536, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_room_quest_id, '{"key":"silent_hall_actor_7"}'),
    ('creature_template', 915537, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_room_quest_id, '{"key":"silent_hall_actor_8"}'),
    ('creature_template', 915538, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_room_quest_id, '{"key":"silent_hall_actor_9"}'),
    ('creature_template', @wm_broug_silent_hall_last_entry, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_room_quest_id, '{"key":"silent_hall_actor_10"}'),
    ('creature_template', @wm_broug_court_remnant_entry, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_domain_unsealed_quest_id, '{"key":"court_remnant"}'),
    ('creature_template', @wm_broug_stillness_credit_entry, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_stilling_quest_id, '{"key":"stillness_trial_credit"}'),
    ('creature_template', @wm_broug_bounty_credit_entry, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_ninety_eight_quest_id, '{"key":"bounty_credit_reserved"}'),
    ('creature_template', @wm_broug_room_credit_entry, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_room_quest_id, '{"key":"silent_hall_credit"}'),
    ('creature_template', @wm_broug_oath_credit_entry, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_domain_unsealed_quest_id, '{"key":"oath_duel_credit"}'),
    ('gameobject_template', @wm_broug_ash_worn_track_go, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_weight_quest_id, '{"key":"ash_worn_track_circle"}'),
    ('gameobject_template', @wm_broug_bolted_cellar_hatch_go, 'active', 'broug_empty_court_v2', @wm_broug_player_guid, @wm_broug_room_quest_id, '{"key":"bolted_cellar_hatch"}')
ON DUPLICATE KEY UPDATE
    SlotStatus = VALUES(SlotStatus),
    ArcKey = VALUES(ArcKey),
    CharacterGUID = VALUES(CharacterGUID),
    SourceQuestID = VALUES(SourceQuestID),
    NotesJSON = VALUES(NotesJSON);

SELECT
    'broug_empty_court_behavior' AS metric,
    ShellSpellID AS shell_spell_id,
    BehaviorKind AS value,
    Status AS status
FROM wm_spell_behavior
WHERE ShellSpellID IN (
    @wm_broug_suppressed_shell_spell_id,
    @wm_broug_qi_reversal_shell_spell_id,
    @wm_broug_purged_state_shell_spell_id,
    @wm_broug_killing_intent_domain_shell_spell_id,
    @wm_broug_predators_strike_shell_spell_id,
    @wm_broug_vitality_drain_shell_spell_id
)
ORDER BY ShellSpellID;
