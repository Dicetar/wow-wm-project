CREATE TABLE IF NOT EXISTS wm_bridge_player_scope (
    PlayerGUID INT NOT NULL,
    Profile VARCHAR(64) NOT NULL DEFAULT 'default',
    Enabled TINYINT(1) NOT NULL DEFAULT 0,
    Reason VARCHAR(255) NULL,
    ExpiresAt TIMESTAMP NULL DEFAULT NULL,
    CreatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (PlayerGUID, Profile),
    KEY idx_wm_bridge_player_scope_enabled (Enabled, ExpiresAt)
);

CREATE TABLE IF NOT EXISTS wm_bridge_action_policy (
    ActionKind VARCHAR(96) NOT NULL,
    Profile VARCHAR(64) NOT NULL DEFAULT 'default',
    Enabled TINYINT(1) NOT NULL DEFAULT 0,
    MaxRiskLevel VARCHAR(16) NOT NULL DEFAULT 'low',
    CooldownMS INT NULL,
    BurstLimit INT NULL,
    AdminOnly TINYINT(1) NOT NULL DEFAULT 0,
    CreatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (ActionKind, Profile),
    KEY idx_wm_bridge_action_policy_enabled (Profile, Enabled)
);

CREATE TABLE IF NOT EXISTS wm_bridge_action_request (
    RequestID BIGINT AUTO_INCREMENT PRIMARY KEY,
    IdempotencyKey VARCHAR(255) NOT NULL,
    PlayerGUID INT NOT NULL,
    ActionKind VARCHAR(96) NOT NULL,
    PayloadJSON LONGTEXT NULL,
    Status VARCHAR(32) NOT NULL DEFAULT 'pending',
    ClaimedAt TIMESTAMP NULL DEFAULT NULL,
    ProcessedAt TIMESTAMP NULL DEFAULT NULL,
    ResultJSON LONGTEXT NULL,
    ErrorText TEXT NULL,
    CreatedBy VARCHAR(64) NOT NULL DEFAULT 'wm',
    RiskLevel VARCHAR(16) NOT NULL DEFAULT 'low',
    ExpiresAt TIMESTAMP NULL DEFAULT NULL,
    CreatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_wm_bridge_action_request_idem (IdempotencyKey),
    KEY idx_wm_bridge_action_request_status (Status, RequestID),
    KEY idx_wm_bridge_action_request_player (PlayerGUID, RequestID),
    KEY idx_wm_bridge_action_request_kind (ActionKind, Status)
);

CREATE TABLE IF NOT EXISTS wm_bridge_world_object (
    ObjectID BIGINT AUTO_INCREMENT PRIMARY KEY,
    ObjectType VARCHAR(32) NOT NULL,
    OwnerPlayerGUID INT NULL,
    ArcKey VARCHAR(128) NULL,
    TemplateEntry INT NULL,
    LiveGUID VARCHAR(128) NULL,
    MapID INT NULL,
    PositionX FLOAT NULL,
    PositionY FLOAT NULL,
    PositionZ FLOAT NULL,
    Orientation FLOAT NULL,
    PhaseMask INT NULL,
    DespawnPolicy VARCHAR(64) NOT NULL DEFAULT 'manual',
    MetadataJSON LONGTEXT NULL,
    CreatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_wm_bridge_world_object_owner (OwnerPlayerGUID, ObjectType),
    KEY idx_wm_bridge_world_object_live (LiveGUID),
    KEY idx_wm_bridge_world_object_arc (ArcKey)
);

CREATE TABLE IF NOT EXISTS wm_bridge_companion (
    CompanionID BIGINT AUTO_INCREMENT PRIMARY KEY,
    PlayerGUID INT NOT NULL,
    CompanionKey VARCHAR(128) NOT NULL,
    State VARCHAR(64) NOT NULL DEFAULT 'inactive',
    FollowMode VARCHAR(64) NULL,
    ActiveCreatureGUID VARCHAR(128) NULL,
    AppearanceJSON LONGTEXT NULL,
    ProfileJSON LONGTEXT NULL,
    CreatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_wm_bridge_companion_player_key (PlayerGUID, CompanionKey),
    KEY idx_wm_bridge_companion_active (ActiveCreatureGUID)
);

CREATE TABLE IF NOT EXISTS wm_bridge_gossip_override (
    OverrideID BIGINT AUTO_INCREMENT PRIMARY KEY,
    PlayerGUID INT NOT NULL,
    ContextType VARCHAR(32) NOT NULL,
    ContextEntry INT NULL,
    ContextGUID VARCHAR(128) NULL,
    ArcKey VARCHAR(128) NULL,
    OptionsJSON LONGTEXT NOT NULL,
    ExpiresAt TIMESTAMP NULL DEFAULT NULL,
    CreatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_wm_bridge_gossip_override_player (PlayerGUID, ContextType, ContextEntry),
    KEY idx_wm_bridge_gossip_override_expiry (ExpiresAt)
);

CREATE TABLE IF NOT EXISTS wm_bridge_item_script (
    ItemEntry INT NOT NULL,
    PlayerGUID INT NULL,
    HookKind VARCHAR(64) NOT NULL,
    ActionJSON LONGTEXT NOT NULL,
    Enabled TINYINT(1) NOT NULL DEFAULT 0,
    CreatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (ItemEntry, HookKind),
    KEY idx_wm_bridge_item_script_player (PlayerGUID, Enabled)
);

CREATE TABLE IF NOT EXISTS wm_bridge_spell_intercept (
    SpellID INT NOT NULL,
    PlayerGUID INT NULL,
    InterceptKind VARCHAR(64) NOT NULL,
    Enabled TINYINT(1) NOT NULL DEFAULT 0,
    MetadataJSON LONGTEXT NULL,
    CreatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (SpellID, InterceptKind),
    KEY idx_wm_bridge_spell_intercept_player (PlayerGUID, Enabled)
);

CREATE TABLE IF NOT EXISTS wm_bridge_spell_script (
    SpellID INT NOT NULL,
    ScriptKind VARCHAR(64) NOT NULL,
    MetadataJSON LONGTEXT NOT NULL,
    Enabled TINYINT(1) NOT NULL DEFAULT 0,
    CreatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (SpellID, ScriptKind),
    KEY idx_wm_bridge_spell_script_enabled (Enabled)
);

CREATE TABLE IF NOT EXISTS wm_bridge_counter (
    PlayerGUID INT NOT NULL,
    CounterKey VARCHAR(128) NOT NULL,
    CounterValue INT NOT NULL DEFAULT 0,
    ArcKey VARCHAR(128) NULL,
    MetadataJSON LONGTEXT NULL,
    ExpiresAt TIMESTAMP NULL DEFAULT NULL,
    CreatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (PlayerGUID, CounterKey),
    KEY idx_wm_bridge_counter_arc (ArcKey),
    KEY idx_wm_bridge_counter_expiry (ExpiresAt)
);

CREATE TABLE IF NOT EXISTS wm_bridge_chat_keyword (
    KeywordID BIGINT AUTO_INCREMENT PRIMARY KEY,
    PlayerGUID INT NULL,
    Keyword VARCHAR(128) NOT NULL,
    MatchMode VARCHAR(32) NOT NULL DEFAULT 'exact',
    ActionJSON LONGTEXT NULL,
    Enabled TINYINT(1) NOT NULL DEFAULT 0,
    CreatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_wm_bridge_chat_keyword_scope (PlayerGUID, Enabled)
);

CREATE TABLE IF NOT EXISTS wm_bridge_runtime_status (
    StatusKey VARCHAR(96) NOT NULL PRIMARY KEY,
    StatusValue VARCHAR(255) NULL,
    PayloadJSON LONGTEXT NULL,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

INSERT INTO wm_bridge_action_policy (ActionKind, Profile, Enabled, MaxRiskLevel, CooldownMS, BurstLimit, AdminOnly) VALUES
('debug_ping', 'default', 1, 'low', 1000, 10, 1),
('debug_echo', 'default', 1, 'low', 1000, 10, 1),
('debug_fail', 'default', 1, 'low', 1000, 10, 1),
('context_snapshot_request', 'default', 1, 'low', 1000, 10, 0)
ON DUPLICATE KEY UPDATE
    Enabled = VALUES(Enabled),
    MaxRiskLevel = VALUES(MaxRiskLevel),
    CooldownMS = VALUES(CooldownMS),
    BurstLimit = VALUES(BurstLimit),
    AdminOnly = VALUES(AdminOnly);
