-- Lana'thel stance: a WM-owned self-cast shell that toggles a persistent
-- transformation and native movement stance. The client shell only exposes the
-- button; mod-wm-spells owns model and speed behavior.

SET @wm_lanathel_stance_shell_spell_id := 946601;
SET @wm_lanathel_display_id := 31165;
SET @wm_riding_skill_id := 762;

CREATE TABLE IF NOT EXISTS wm_lanathel_stance_state (
    PlayerGUID INT UNSIGNED NOT NULL,
    ShellSpellID INT UNSIGNED NOT NULL,
    Active TINYINT UNSIGNED NOT NULL DEFAULT 1,
    StoredAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (PlayerGUID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO wm_spell_shell
    (ShellSpellID, ShellKey, FamilyID, Label, State, ClientPatchVersion, OwnershipKey, ProvenanceJSON)
VALUES
    (
        @wm_lanathel_stance_shell_spell_id,
        'lanathel_blood_queen_stance_v1',
        'self_aura',
        'Blood Queen''s Pursuit',
        'planned',
        'wm_spell_shell_bank.v2',
        'wm.spell_shell:lanathel_blood_queen_stance_v1',
        '{"notes":["Named self-cast shell from the generic V2 self_aura range. Runtime owns persistent model and movement speed."]}'
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
        @wm_lanathel_stance_shell_spell_id,
        'lanathel_blood_queen_stance_v1',
        JSON_OBJECT(
            'display_id', @wm_lanathel_display_id,
            'display_scale', 0.35,
            'riding_skill_id', @wm_riding_skill_id,
            'apprentice_riding_skill', 75,
            'journeyman_riding_skill', 150,
            'expert_riding_skill', 225,
            'artisan_riding_skill', 300,
            'master_riding_skill', 375,
            'base_land_speed_rate', 1.4,
            'apprentice_land_speed_rate', 1.6,
            'journeyman_land_speed_rate', 2.0,
            'expert_flight_speed_rate', 2.5,
            'artisan_flight_speed_rate', 3.8,
            'master_flight_speed_rate', 4.1,
            'flight_requires_flyable_area', true
        ),
        'active'
    )
ON DUPLICATE KEY UPDATE
    BehaviorKind = VALUES(BehaviorKind),
    ConfigJSON = VALUES(ConfigJSON),
    Status = VALUES(Status),
    UpdatedAt = CURRENT_TIMESTAMP;

DELETE FROM spell_script_names
WHERE spell_id = @wm_lanathel_stance_shell_spell_id
  AND ScriptName = 'spell_wm_shell_dispatch';

INSERT INTO spell_script_names (spell_id, ScriptName)
VALUES (@wm_lanathel_stance_shell_spell_id, 'spell_wm_shell_dispatch');

SELECT
    'lanathel_stance_behavior' AS metric,
    BehaviorKind AS value
FROM wm_spell_behavior
WHERE ShellSpellID = @wm_lanathel_stance_shell_spell_id;

SELECT
    'lanathel_stance_table' AS metric,
    COUNT(*) AS value
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'wm_lanathel_stance_state';
