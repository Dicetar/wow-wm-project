-- Bonebound Echo Stasis: visible self-cast shell that stores active Echo role
-- counts and later restores those counts from the current Bonebound Alpha.

SET @wm_echo_stasis_shell_spell_id := 946600;
SET @wm_alpha_shell_spell_id := 940001;
SET @wm_soul_shard_item_id := 6265;

CREATE TABLE IF NOT EXISTS wm_bonebound_echo_stasis (
    PlayerGUID INT UNSIGNED NOT NULL,
    DestroyerCount INT UNSIGNED NOT NULL DEFAULT 0,
    RestorerCount INT UNSIGNED NOT NULL DEFAULT 0,
    StoredAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (PlayerGUID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO wm_spell_shell
    (ShellSpellID, ShellKey, FamilyID, Label, State, ClientPatchVersion, OwnershipKey, ProvenanceJSON)
VALUES
    (
        @wm_echo_stasis_shell_spell_id,
        'bonebound_echo_stasis_v1',
        'self_aura',
        'Bonebound Echo Stasis',
        'planned',
        'wm_spell_shell_bank.v2',
        'wm.spell_shell:bonebound_echo_stasis_v1',
        '{"notes":["Named self-cast shell from the generic V2 self_aura range. Runtime stores role counts only."]}'
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
        @wm_echo_stasis_shell_spell_id,
        'bonebound_echo_stasis_v1',
        JSON_OBJECT(
            'alpha_shell_spell_id', @wm_alpha_shell_spell_id,
            'soul_shard_item_id', @wm_soul_shard_item_id,
            'soul_shard_count', 1
        ),
        'active'
    )
ON DUPLICATE KEY UPDATE
    BehaviorKind = VALUES(BehaviorKind),
    ConfigJSON = VALUES(ConfigJSON),
    Status = VALUES(Status),
    UpdatedAt = CURRENT_TIMESTAMP;

DELETE FROM spell_script_names
WHERE spell_id = @wm_echo_stasis_shell_spell_id
  AND ScriptName = 'spell_wm_shell_dispatch';

INSERT INTO spell_script_names (spell_id, ScriptName)
VALUES (@wm_echo_stasis_shell_spell_id, 'spell_wm_shell_dispatch');

SELECT
    'bonebound_echo_stasis_behavior' AS metric,
    BehaviorKind AS value
FROM wm_spell_behavior
WHERE ShellSpellID = @wm_echo_stasis_shell_spell_id;

SELECT
    'bonebound_echo_stasis_table' AS metric,
    COUNT(*) AS value
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'wm_bonebound_echo_stasis';
