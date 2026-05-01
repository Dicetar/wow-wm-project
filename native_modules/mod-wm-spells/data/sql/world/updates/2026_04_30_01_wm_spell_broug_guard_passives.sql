-- Broug guard passives.
-- These rows define WM-owned passive shells and grant-gated native behavior only.
-- They do not grant anything globally and do not alter stock Auto Shot, Throw, Parry, or class creation tables.

SET @wm_broug_universal_parry_shell_spell_id := 946800;
SET @wm_broug_mobile_marksman_shell_spell_id := 946801;

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
        @wm_broug_universal_parry_shell_spell_id,
        'broug_universal_parry_v1',
        'passive_aura',
        'Impossible Guard',
        'planned',
        'wm_spell_shell_bank.v2',
        'wm.spell_shell:broug_universal_parry_v1',
        '{"notes":["Broug-scoped passive shell. Runtime owns universal hostile-damage parry behavior and parry counters."]}'
    ),
    (
        @wm_broug_mobile_marksman_shell_spell_id,
        'broug_mobile_marksman_v1',
        'passive_aura',
        'Skirmisher''s Mark',
        'planned',
        'wm_spell_shell_bank.v2',
        'wm.spell_shell:broug_mobile_marksman_v1',
        '{"notes":["Broug-scoped passive shell. Runtime supplies moving ranged/throwing pulses without globally changing stock movement checks."]}'
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
        @wm_broug_universal_parry_shell_spell_id,
        'broug_universal_parry_v1',
        JSON_OBJECT(
            'base_chance_pct', 30.0,
            'strength_to_chance_pct', 0.45,
            'agility_to_chance_pct', 0.45,
            'expertise_to_chance_pct', 2.5,
            'weapon_mastery_to_chance_pct', 0.25,
            'attack_power_to_chance_pct', 0.0,
            'max_chance_pct', 90.0,
            'counter_key', 'universal_parry',
            'count_spell_damage', true,
            'count_periodic_damage', true
        ),
        'active'
    ),
    (
        @wm_broug_mobile_marksman_shell_spell_id,
        'broug_mobile_marksman_v1',
        JSON_OBJECT(
            'pulse_interval_ms', 1200,
            'min_range_yards', 3.0,
            'max_range_yards', 35.0,
            'base_damage', 1,
            'weapon_damage_pct', 100,
            'ranged_attack_power_pct', 20,
            'agility_damage_pct', 35,
            'visual_spell_id', 75,
            'counter_key', 'mobile_ranged_hit'
        ),
        'active'
    )
ON DUPLICATE KEY UPDATE
    BehaviorKind = VALUES(BehaviorKind),
    ConfigJSON = VALUES(ConfigJSON),
    Status = VALUES(Status),
    UpdatedAt = CURRENT_TIMESTAMP;

SELECT
    'broug_guard_behavior' AS metric,
    ShellSpellID AS shell_spell_id,
    BehaviorKind AS value
FROM wm_spell_behavior
WHERE ShellSpellID IN (@wm_broug_universal_parry_shell_spell_id, @wm_broug_mobile_marksman_shell_spell_id)
ORDER BY ShellSpellID;

SELECT
    'broug_guard_counter_table' AS metric,
    COUNT(*) AS value
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'wm_broug_guard_counter';
