-- Broug Skirmisher's Mark active rework.
-- Retires the old passive moving-pulse visible shell and publishes a fresh active shell.
-- Character DB cleanup is handled by `python -m wm.spells.broug_guard --mode apply`.

SET @wm_broug_retired_mobile_marksman_shell_spell_id := 946801;
SET @wm_broug_skirmisher_mark_shell_spell_id := 946604;
SET @wm_broug_player_guid := 5405;

UPDATE wm_spell_shell
SET
    State = 'retired',
    ProvenanceJSON = '{"status":"BROKEN","reason":"passive moving pulse felt wrong in live test","replaced_by":946604}',
    UpdatedAt = CURRENT_TIMESTAMP
WHERE ShellSpellID = @wm_broug_retired_mobile_marksman_shell_spell_id;

UPDATE wm_spell_behavior
SET
    Status = 'disabled',
    UpdatedAt = CURRENT_TIMESTAMP
WHERE ShellSpellID = @wm_broug_retired_mobile_marksman_shell_spell_id;

UPDATE wm_spell_grant
SET
    RevokedAt = COALESCE(RevokedAt, CURRENT_TIMESTAMP),
    MetadataJSON = '{"status":"BROKEN","replaced_by":946604,"reason":"replaced_by_active_skirmisher_mark_v2"}'
WHERE PlayerGUID = @wm_broug_player_guid
  AND ShellSpellID = @wm_broug_retired_mobile_marksman_shell_spell_id
  AND RevokedAt IS NULL;

INSERT INTO wm_spell_shell
    (ShellSpellID, ShellKey, FamilyID, Label, State, ClientPatchVersion, OwnershipKey, ProvenanceJSON)
VALUES
    (
        @wm_broug_skirmisher_mark_shell_spell_id,
        'broug_skirmisher_mark_v2',
        'self_aura',
        'Skirmisher''s Mark',
        'planned',
        'wm_spell_shell_bank.v2',
        'wm.spell_shell:broug_skirmisher_mark_v2',
        '{"notes":["Fresh active shell replacing retired passive 946801. Runtime owns a ranged/thrown auto-attack loop with native ranged weapon scaling."]}'
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
        @wm_broug_skirmisher_mark_shell_spell_id,
        'broug_skirmisher_mark_v2',
        JSON_OBJECT(
            'min_range_yards', 0.0,
            'max_range_yards', 35.0,
            'damage_pct', 100,
            'min_attack_interval_ms', 500,
            'max_attack_interval_ms', 6000,
            'visual_spell_id', 75,
            'impact_sound_id', 7140,
            'counter_key', 'skirmisher_auto_hit'
        ),
        'active'
    )
ON DUPLICATE KEY UPDATE
    BehaviorKind = VALUES(BehaviorKind),
    ConfigJSON = VALUES(ConfigJSON),
    Status = VALUES(Status),
    UpdatedAt = CURRENT_TIMESTAMP;

INSERT INTO wm_spell_grant
    (PlayerGUID, ShellSpellID, GrantKind, Author, MetadataJSON)
SELECT
    @wm_broug_player_guid,
    @wm_broug_skirmisher_mark_shell_spell_id,
    'broug_guard',
    'mod-wm-spells',
    '{"capability":"skirmisher_mark","behavior_kind":"broug_skirmisher_mark_v2","counter_key":"skirmisher_auto_hit","scales_with":["ranged_auto_attack_damage","ranged_attack_power","ranged_weapon_speed"],"status":"PARTIAL"}'
WHERE NOT EXISTS (
    SELECT 1
    FROM wm_spell_grant
    WHERE PlayerGUID = @wm_broug_player_guid
      AND ShellSpellID = @wm_broug_skirmisher_mark_shell_spell_id
      AND RevokedAt IS NULL
);

SELECT
    'broug_skirmisher_mark_active' AS metric,
    ShellSpellID AS shell_spell_id,
    BehaviorKind AS value,
    Status AS status
FROM wm_spell_behavior
WHERE ShellSpellID IN (@wm_broug_retired_mobile_marksman_shell_spell_id, @wm_broug_skirmisher_mark_shell_spell_id)
ORDER BY ShellSpellID;
