-- Broug Deflect counterstrike stance.
-- Fresh shell 946605 controls whether Deflect auto-counterattacks after applying Vulnerable.

SET @wm_broug_player_guid := 5405;
SET @wm_broug_deflect_shell_spell_id := 946603;
SET @wm_broug_deflect_counter_stance_shell_spell_id := 946605;
SET @wm_broug_parry_quest_id := 910180;

CREATE TABLE IF NOT EXISTS wm_broug_deflect_counter_stance (
    PlayerGUID INT NOT NULL,
    CounterattackEnabled TINYINT UNSIGNED NOT NULL DEFAULT 1,
    StoredAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (PlayerGUID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO wm_spell_shell
    (ShellSpellID, ShellKey, FamilyID, Label, State, ClientPatchVersion, OwnershipKey, ProvenanceJSON)
VALUES
    (
        @wm_broug_deflect_counter_stance_shell_spell_id,
        'broug_deflect_counter_stance_v1',
        'self_aura',
        'Counterstrike Stance',
        'planned',
        'wm_spell_shell_bank.v2',
        'wm.spell_shell:broug_deflect_counter_stance_v1',
        '{"notes":["Fresh stance-style dispatch shell. Native runtime stores persistent Deflect counterstrike state.","When held, Deflect still blocks and applies Vulnerable, but skips the automatic window-end counterattack."]}'
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
        @wm_broug_deflect_counter_stance_shell_spell_id,
        'broug_deflect_counter_stance_v1',
        JSON_OBJECT(
            'controls_spell_id', @wm_broug_deflect_shell_spell_id,
            'default_counterattack_enabled', TRUE,
            'persistent_state_table', 'wm_broug_deflect_counter_stance'
        ),
        'active'
    )
ON DUPLICATE KEY UPDATE
    BehaviorKind = VALUES(BehaviorKind),
    ConfigJSON = VALUES(ConfigJSON),
    Status = VALUES(Status),
    UpdatedAt = CURRENT_TIMESTAMP;

UPDATE wm_spell_behavior
SET ConfigJSON = JSON_SET(
        COALESCE(ConfigJSON, JSON_OBJECT()),
        '$.counterattack_enabled_default', TRUE
    ),
    UpdatedAt = CURRENT_TIMESTAMP
WHERE ShellSpellID = @wm_broug_deflect_shell_spell_id
  AND BehaviorKind = 'broug_deflect_v1';

INSERT INTO spell_cooldown_overrides
    (Id, RecoveryTime, CategoryRecoveryTime, StartRecoveryTime, StartRecoveryCategory, Comment)
VALUES
    (@wm_broug_deflect_counter_stance_shell_spell_id, 0, 0, 0, 0, 'WM Broug Deflect counterstrike stance toggle/no-GCD shell')
ON DUPLICATE KEY UPDATE
    RecoveryTime = VALUES(RecoveryTime),
    CategoryRecoveryTime = VALUES(CategoryRecoveryTime),
    StartRecoveryTime = VALUES(StartRecoveryTime),
    StartRecoveryCategory = VALUES(StartRecoveryCategory),
    Comment = VALUES(Comment);

INSERT INTO wm_reserved_slot
    (EntityType, ReservedID, SlotStatus, ArcKey, CharacterGUID, SourceQuestID, NotesJSON)
VALUES
    ('spell', @wm_broug_deflect_counter_stance_shell_spell_id, 'active', 'broug_guard_progression_v1', @wm_broug_player_guid, @wm_broug_parry_quest_id, '{"key":"broug_deflect_counter_stance_v1","fresh_visible_id":true}')
ON DUPLICATE KEY UPDATE
    SlotStatus = VALUES(SlotStatus),
    ArcKey = VALUES(ArcKey),
    CharacterGUID = VALUES(CharacterGUID),
    SourceQuestID = VALUES(SourceQuestID),
    NotesJSON = VALUES(NotesJSON);

INSERT INTO wm_spell_grant
    (PlayerGUID, ShellSpellID, GrantKind, SourceQuestID, Author, MetadataJSON)
SELECT
    @wm_broug_player_guid,
    @wm_broug_deflect_counter_stance_shell_spell_id,
    'broug_guard_reward',
    @wm_broug_parry_quest_id,
    'mod-wm-spells',
    '{"capability":"deflect_counter_stance","behavior_kind":"broug_deflect_counter_stance_v1","source":"broug_guard_quest","status":"PARTIAL"}'
WHERE EXISTS (
    SELECT 1
    FROM wm_spell_grant
    WHERE PlayerGUID = @wm_broug_player_guid
      AND ShellSpellID = @wm_broug_deflect_shell_spell_id
      AND RevokedAt IS NULL
)
AND NOT EXISTS (
    SELECT 1
    FROM wm_spell_grant
    WHERE PlayerGUID = @wm_broug_player_guid
      AND ShellSpellID = @wm_broug_deflect_counter_stance_shell_spell_id
      AND RevokedAt IS NULL
);

INSERT INTO wm_broug_deflect_counter_stance (PlayerGUID, CounterattackEnabled, StoredAt, UpdatedAt)
VALUES (@wm_broug_player_guid, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON DUPLICATE KEY UPDATE
    CounterattackEnabled = CounterattackEnabled,
    UpdatedAt = UpdatedAt;

SELECT
    'broug_deflect_counter_stance' AS metric,
    b.ShellSpellID AS shell_spell_id,
    b.BehaviorKind AS value
FROM wm_spell_behavior b
WHERE b.ShellSpellID IN (@wm_broug_deflect_shell_spell_id, @wm_broug_deflect_counter_stance_shell_spell_id)
ORDER BY b.ShellSpellID;
