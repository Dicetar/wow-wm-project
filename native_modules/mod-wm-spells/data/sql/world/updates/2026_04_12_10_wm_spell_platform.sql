CREATE TABLE IF NOT EXISTS wm_spell_shell (
    ShellSpellID INT NOT NULL,
    ShellKey VARCHAR(64) NOT NULL,
    FamilyID VARCHAR(64) NOT NULL,
    Label VARCHAR(120) NOT NULL,
    State VARCHAR(32) NOT NULL DEFAULT 'draft',
    ClientPatchVersion VARCHAR(64) NOT NULL,
    OwnershipKey VARCHAR(128) DEFAULT NULL,
    ProvenanceJSON LONGTEXT DEFAULT NULL,
    CreatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (ShellSpellID),
    UNIQUE KEY uq_wm_spell_shell_key (ShellKey)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS wm_spell_behavior (
    ShellSpellID INT NOT NULL,
    BehaviorKind VARCHAR(64) NOT NULL,
    ConfigJSON LONGTEXT DEFAULT NULL,
    Status VARCHAR(32) NOT NULL DEFAULT 'active',
    CreatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (ShellSpellID),
    KEY idx_wm_spell_behavior_kind (BehaviorKind)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS wm_spell_grant (
    GrantID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    PlayerGUID INT NOT NULL,
    ShellSpellID INT NOT NULL,
    GrantKind VARCHAR(32) NOT NULL,
    SourceQuestID INT DEFAULT NULL,
    SourceItemEntry INT DEFAULT NULL,
    Author VARCHAR(64) DEFAULT NULL,
    MetadataJSON LONGTEXT DEFAULT NULL,
    RevokedAt TIMESTAMP NULL DEFAULT NULL,
    CreatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (GrantID),
    KEY idx_wm_spell_grant_player_spell (PlayerGUID, ShellSpellID, RevokedAt)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS wm_spell_debug_request (
    RequestID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    PlayerGUID INT NOT NULL,
    BehaviorKind VARCHAR(64) NOT NULL,
    PayloadJSON LONGTEXT DEFAULT NULL,
    Status VARCHAR(32) NOT NULL DEFAULT 'pending',
    ResultJSON LONGTEXT DEFAULT NULL,
    ErrorText TEXT DEFAULT NULL,
    CreatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ProcessedAt TIMESTAMP NULL DEFAULT NULL,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (RequestID),
    KEY idx_wm_spell_debug_request_status (Status, RequestID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO wm_spell_shell (ShellSpellID, ShellKey, FamilyID, Label, State, ClientPatchVersion, OwnershipKey, ProvenanceJSON) VALUES
(940000, 'bonebound_servant_v1', 'summon_pet', 'Bonebound Servant', 'planned', 'wm_spell_shell_bank.v1', 'wm.spell_shell:bonebound_servant_v1', '{}'),
(940500, 'bonebound_servant_slash_v1', 'pet_active', 'Bonebound Slash', 'planned', 'wm_spell_shell_bank.v1', 'wm.spell_shell:bonebound_servant_slash_v1', '{}')
ON DUPLICATE KEY UPDATE
    FamilyID = VALUES(FamilyID),
    Label = VALUES(Label),
    State = VALUES(State),
    ClientPatchVersion = VALUES(ClientPatchVersion),
    OwnershipKey = VALUES(OwnershipKey),
    ProvenanceJSON = VALUES(ProvenanceJSON),
    UpdatedAt = CURRENT_TIMESTAMP;

INSERT INTO wm_spell_behavior (ShellSpellID, BehaviorKind, ConfigJSON, Status) VALUES
(940000, 'summon_bonebound_servant_v1', '{"creature_entry":1860,"display_id":734,"name":"Bonebound Servant","require_corpse":true,"persist_pet":true,"virtual_item_1":1897,"virtual_item_2":0,"virtual_item_3":0}', 'planned'),
(940500, 'bonebound_pet_active_v1', '{}', 'planned')
ON DUPLICATE KEY UPDATE
    BehaviorKind = VALUES(BehaviorKind),
    ConfigJSON = VALUES(ConfigJSON),
    Status = VALUES(Status),
    UpdatedAt = CURRENT_TIMESTAMP;

DELETE FROM spell_script_names WHERE spell_id = 940000;
INSERT INTO spell_script_names (spell_id, ScriptName) VALUES
(940000, 'spell_wm_bonebound_servant_shell');
