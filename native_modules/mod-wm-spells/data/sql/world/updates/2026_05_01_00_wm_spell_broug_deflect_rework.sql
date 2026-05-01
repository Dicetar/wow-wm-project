-- Broug Deflect animation-window rework.
-- Fresh visible IDs only: 946200 Vulnerable and 946201 Deflected.
-- Deflect remains the existing active shell 946603 and stays aura-free.

SET @wm_broug_vulnerable_shell_spell_id := 946200;
SET @wm_broug_deflected_shell_spell_id := 946201;
SET @wm_broug_deflect_shell_spell_id := 946603;
SET @wm_broug_player_guid := 5405;

INSERT INTO wm_spell_shell
    (ShellSpellID, ShellKey, FamilyID, Label, State, ClientPatchVersion, OwnershipKey, ProvenanceJSON)
VALUES
    (
        @wm_broug_vulnerable_shell_spell_id,
        'broug_vulnerable_v1',
        'unit_target_effect',
        'Vulnerable',
        'planned',
        'wm_spell_shell_bank.v2',
        'wm.spell_shell:broug_vulnerable_v1',
        '{"notes":["Broug Deflect visible debuff. Runtime owns stack application, damage multiplier, and consumption.","Duration defaults to 60000ms; icon 558 is stock Forceful Deflection."]}'
    ),
    (
        @wm_broug_deflected_shell_spell_id,
        'broug_deflected_v1',
        'unit_target_effect',
        'Deflected',
        'planned',
        'wm_spell_shell_bank.v2',
        'wm.spell_shell:broug_deflected_v1',
        '{"notes":["Broug Deflect visible status. Runtime forced stun remains the real control path.","Stack count equals consumed Vulnerable stacks and is retained for future mechanics."]}'
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
            'parry_pre_ms', 100,
            'parry_animation_ms', 450,
            'parry_post_ms', 100,
            'window_ms', 650,
            'cooldown_ms', 500,
            'energy_cost', 5,
            'stun_ms', 1000,
            'deflected_stun_ms_per_stack', 1000,
            'vulnerable_spell_id', @wm_broug_vulnerable_shell_spell_id,
            'deflected_spell_id', @wm_broug_deflected_shell_spell_id,
            'vulnerable_duration_ms', 60000,
            'max_vulnerable_stacks', 255,
            'base_damage', 1,
            'weapon_damage_pct', 120,
            'attack_power_pct', 80,
            'visual_spell_id', @wm_broug_deflect_shell_spell_id,
            'counter_key', 'deflect_success'
        ),
        'active'
    ),
    (
        @wm_broug_vulnerable_shell_spell_id,
        'broug_vulnerable_v1',
        JSON_OBJECT(
            'duration_ms', 60000,
            'icon_id', 558,
            'runtime_owned', TRUE,
            'consumed_by_next_damage', TRUE
        ),
        'active'
    ),
    (
        @wm_broug_deflected_shell_spell_id,
        'broug_deflected_v1',
        JSON_OBJECT(
            'icon_id', 558,
            'runtime_owned', TRUE,
            'forced_stun_visible_state', TRUE
        ),
        'active'
    )
ON DUPLICATE KEY UPDATE
    BehaviorKind = VALUES(BehaviorKind),
    ConfigJSON = VALUES(ConfigJSON),
    Status = VALUES(Status),
    UpdatedAt = CURRENT_TIMESTAMP;

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

INSERT INTO wm_reserved_slot
    (EntityType, ReservedID, SlotStatus, ArcKey, CharacterGUID, SourceQuestID, NotesJSON)
VALUES
    ('spell', @wm_broug_vulnerable_shell_spell_id, 'active', 'broug_guard_progression_v1', @wm_broug_player_guid, NULL, '{"key":"broug_vulnerable_v1","fresh_visible_id":true}'),
    ('spell', @wm_broug_deflected_shell_spell_id, 'active', 'broug_guard_progression_v1', @wm_broug_player_guid, NULL, '{"key":"broug_deflected_v1","fresh_visible_id":true}')
ON DUPLICATE KEY UPDATE
    SlotStatus = VALUES(SlotStatus),
    ArcKey = VALUES(ArcKey),
    CharacterGUID = VALUES(CharacterGUID),
    SourceQuestID = VALUES(SourceQuestID),
    NotesJSON = VALUES(NotesJSON);

SELECT
    'broug_deflect_rework_behavior' AS metric,
    ShellSpellID AS shell_spell_id,
    BehaviorKind AS value
FROM wm_spell_behavior
WHERE ShellSpellID IN (
    @wm_broug_vulnerable_shell_spell_id,
    @wm_broug_deflected_shell_spell_id,
    @wm_broug_deflect_shell_spell_id
)
ORDER BY ShellSpellID;
