CREATE TABLE IF NOT EXISTS wm_subject_definition (
    SubjectID BIGINT AUTO_INCREMENT PRIMARY KEY,
    SubjectType VARCHAR(32) NOT NULL,
    CreatureEntry INT NULL,
    JournalName VARCHAR(120) NOT NULL,
    Archetype VARCHAR(64) NOT NULL,
    Species VARCHAR(64) NULL,
    Occupation VARCHAR(128) NULL,
    HomeArea VARCHAR(128) NULL,
    ShortDescription TEXT NULL,
    TagsJSON LONGTEXT NULL,
    IsActive TINYINT NOT NULL DEFAULT 1,
    UNIQUE KEY uniq_subject_creature (SubjectType, CreatureEntry)
);

CREATE TABLE IF NOT EXISTS wm_subject_enrichment (
    SubjectType VARCHAR(32) NOT NULL,
    EntryID INT NOT NULL,
    Species VARCHAR(64) NULL,
    Profession VARCHAR(128) NULL,
    RoleLabel VARCHAR(128) NULL,
    HomeArea VARCHAR(128) NULL,
    ShortDescription TEXT NULL,
    TagsJSON LONGTEXT NULL,
    PRIMARY KEY (SubjectType, EntryID)
);

CREATE TABLE IF NOT EXISTS wm_player_subject_journal (
    JournalID BIGINT AUTO_INCREMENT PRIMARY KEY,
    PlayerGUID INT NOT NULL,
    SubjectID BIGINT NOT NULL,
    FirstSeenAt TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    LastSeenAt TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    KillCount INT NOT NULL DEFAULT 0,
    SkinCount INT NOT NULL DEFAULT 0,
    FeedCount INT NOT NULL DEFAULT 0,
    TalkCount INT NOT NULL DEFAULT 0,
    QuestCompleteCount INT NOT NULL DEFAULT 0,
    LastQuestTitle VARCHAR(200) NULL,
    NotesJSON LONGTEXT NULL,
    UNIQUE KEY uniq_player_subject (PlayerGUID, SubjectID)
);

CREATE TABLE IF NOT EXISTS wm_player_subject_event (
    EventID BIGINT AUTO_INCREMENT PRIMARY KEY,
    PlayerGUID INT NOT NULL,
    SubjectID BIGINT NOT NULL,
    EventType VARCHAR(64) NOT NULL,
    EventValue VARCHAR(255) NULL,
    CreatedAt TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS wm_event_log (
    EventID BIGINT AUTO_INCREMENT PRIMARY KEY,
    EventClass VARCHAR(32) NOT NULL,
    EventType VARCHAR(64) NOT NULL,
    Source VARCHAR(64) NOT NULL,
    SourceEventKey VARCHAR(128) NOT NULL,
    OccurredAt VARCHAR(64) NOT NULL,
    RecordedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PlayerGUID INT NULL,
    SubjectType VARCHAR(32) NULL,
    SubjectEntry INT NULL,
    MapID INT NULL,
    ZoneID INT NULL,
    AreaID INT NULL,
    EventValue VARCHAR(255) NULL,
    MetadataJSON LONGTEXT NULL,
    ProjectedAt TIMESTAMP NULL DEFAULT NULL,
    EvaluatedAt TIMESTAMP NULL DEFAULT NULL,
    UNIQUE KEY uniq_event_source_key (Source, SourceEventKey),
    KEY idx_event_log_class (EventClass),
    KEY idx_event_log_projected (EventClass, ProjectedAt),
    KEY idx_event_log_evaluated (EventClass, EvaluatedAt)
);

CREATE TABLE IF NOT EXISTS wm_event_cursor (
    AdapterName VARCHAR(64) NOT NULL,
    CursorKey VARCHAR(64) NOT NULL,
    CursorValue VARCHAR(255) NOT NULL,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (AdapterName, CursorKey)
);

CREATE TABLE IF NOT EXISTS wm_bridge_event (
    BridgeEventID BIGINT AUTO_INCREMENT PRIMARY KEY,
    OccurredAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    EventFamily VARCHAR(32) NOT NULL,
    EventType VARCHAR(64) NOT NULL,
    Source VARCHAR(64) NOT NULL DEFAULT 'native_bridge',
    PlayerGUID INT NULL,
    AccountID INT NULL,
    SubjectType VARCHAR(32) NULL,
    SubjectGUID VARCHAR(128) NULL,
    SubjectEntry INT NULL,
    ObjectType VARCHAR(32) NULL,
    ObjectGUID VARCHAR(128) NULL,
    ObjectEntry INT NULL,
    MapID INT NULL,
    ZoneID INT NULL,
    AreaID INT NULL,
    PayloadJSON LONGTEXT NULL,
    KEY idx_wm_bridge_event_family_type (EventFamily, EventType),
    KEY idx_wm_bridge_event_player (PlayerGUID, BridgeEventID),
    KEY idx_wm_bridge_event_occurred (OccurredAt)
);

CREATE TABLE IF NOT EXISTS wm_bridge_context_request (
    RequestID BIGINT AUTO_INCREMENT PRIMARY KEY,
    RequestedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PlayerGUID INT NOT NULL,
    ContextKind VARCHAR(64) NOT NULL,
    Radius INT NOT NULL DEFAULT 40,
    Status VARCHAR(32) NOT NULL DEFAULT 'pending',
    RequestedBy VARCHAR(64) NULL,
    MetadataJSON LONGTEXT NULL,
    ProcessedAt TIMESTAMP NULL DEFAULT NULL,
    KEY idx_wm_bridge_context_request_status (Status, RequestedAt),
    KEY idx_wm_bridge_context_request_player (PlayerGUID, RequestedAt)
);

CREATE TABLE IF NOT EXISTS wm_bridge_context_snapshot (
    SnapshotID BIGINT AUTO_INCREMENT PRIMARY KEY,
    RequestID BIGINT NULL,
    OccurredAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PlayerGUID INT NOT NULL,
    ContextKind VARCHAR(64) NOT NULL,
    Radius INT NOT NULL DEFAULT 40,
    MapID INT NULL,
    ZoneID INT NULL,
    AreaID INT NULL,
    Source VARCHAR(64) NOT NULL DEFAULT 'native_bridge',
    PayloadJSON LONGTEXT NOT NULL,
    KEY idx_wm_bridge_context_snapshot_player (PlayerGUID, OccurredAt),
    KEY idx_wm_bridge_context_snapshot_request (RequestID)
);

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

CREATE TABLE IF NOT EXISTS wm_reaction_cooldown (
    ReactionKey VARCHAR(255) NOT NULL,
    RuleType VARCHAR(64) NOT NULL,
    PlayerGUID INT NOT NULL,
    SubjectType VARCHAR(32) NOT NULL,
    SubjectEntry INT NOT NULL,
    CooldownUntil TIMESTAMP NOT NULL,
    LastTriggeredAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    MetadataJSON LONGTEXT NULL,
    PRIMARY KEY (ReactionKey),
    KEY idx_reaction_cooldown_expiry (CooldownUntil)
);

CREATE TABLE IF NOT EXISTS wm_reaction_log (
    ReactionID BIGINT AUTO_INCREMENT PRIMARY KEY,
    ReactionKey VARCHAR(255) NOT NULL,
    RuleType VARCHAR(64) NOT NULL,
    Status VARCHAR(32) NOT NULL,
    PlayerGUID INT NOT NULL,
    SubjectType VARCHAR(32) NOT NULL,
    SubjectEntry INT NOT NULL,
    PlannedActionsJSON LONGTEXT NOT NULL,
    ResultJSON LONGTEXT NULL,
    CreatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_reaction_log_key (ReactionKey),
    KEY idx_reaction_log_status (Status)
);

CREATE TABLE IF NOT EXISTS wm_control_schema_version (
    SchemaKey VARCHAR(128) NOT NULL,
    SchemaVersion VARCHAR(64) NOT NULL,
    SchemaHash VARCHAR(128) NOT NULL,
    RegistryHash VARCHAR(128) NULL,
    MetadataJSON LONGTEXT NULL,
    CreatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (SchemaKey, SchemaVersion)
);

CREATE TABLE IF NOT EXISTS wm_control_proposal (
    ProposalID BIGINT AUTO_INCREMENT PRIMARY KEY,
    IdempotencyKey VARCHAR(255) NOT NULL,
    SchemaVersion VARCHAR(64) NOT NULL,
    RegistryHash VARCHAR(128) NULL,
    SchemaHash VARCHAR(128) NULL,
    AuthorMode VARCHAR(32) NOT NULL,
    AuthorName VARCHAR(128) NULL,
    PlayerGUID INT NULL,
    SourceEventID BIGINT NULL,
    SourceEventKey VARCHAR(128) NULL,
    SelectedRecipe VARCHAR(128) NOT NULL,
    ActionKind VARCHAR(64) NOT NULL,
    Status VARCHAR(32) NOT NULL,
    RawProposalJSON LONGTEXT NOT NULL,
    NormalizedProposalJSON LONGTEXT NULL,
    ValidationJSON LONGTEXT NULL,
    DryRunJSON LONGTEXT NULL,
    ApplyJSON LONGTEXT NULL,
    PolicyDecisionJSON LONGTEXT NULL,
    CreatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_control_idempotency (IdempotencyKey),
    KEY idx_control_proposal_status (Status),
    KEY idx_control_proposal_player (PlayerGUID, CreatedAt),
    KEY idx_control_proposal_event (SourceEventID)
);

CREATE TABLE IF NOT EXISTS wm_control_apply_lock (
    IdempotencyKey VARCHAR(255) NOT NULL,
    LockedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ExpiresAt TIMESTAMP NOT NULL,
    Owner VARCHAR(128) NULL,
    PRIMARY KEY (IdempotencyKey),
    KEY idx_control_apply_lock_expiry (ExpiresAt)
);

CREATE TABLE IF NOT EXISTS wm_reactive_quest_rule (
    RuleKey VARCHAR(128) NOT NULL,
    IsActive TINYINT NOT NULL DEFAULT 1,
    PlayerGUIDScope INT NULL,
    SubjectType VARCHAR(32) NOT NULL,
    SubjectEntry INT NOT NULL,
    TriggerEventType VARCHAR(64) NOT NULL,
    KillThreshold INT NOT NULL DEFAULT 4,
    WindowSeconds INT NOT NULL DEFAULT 120,
    QuestID INT NOT NULL,
    TurnInNpcEntry INT NOT NULL,
    GrantMode VARCHAR(64) NOT NULL DEFAULT 'direct_quest_add',
    PostRewardCooldownSeconds INT NOT NULL DEFAULT 60,
    MetadataJSON LONGTEXT NULL,
    NotesJSON LONGTEXT NULL,
    CreatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (RuleKey),
    KEY idx_reactive_rule_active (IsActive, SubjectType, SubjectEntry, TriggerEventType),
    KEY idx_reactive_rule_quest (QuestID)
);

CREATE TABLE IF NOT EXISTS wm_player_quest_runtime_state (
    PlayerGUID INT NOT NULL,
    QuestID INT NOT NULL,
    CurrentState VARCHAR(32) NOT NULL,
    LastTransitionAt TIMESTAMP NULL DEFAULT NULL,
    LastObservedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    MetadataJSON LONGTEXT NULL,
    PRIMARY KEY (PlayerGUID, QuestID),
    KEY idx_player_quest_runtime_state (QuestID, CurrentState)
);

CREATE TABLE IF NOT EXISTS wm_publish_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    artifact_type VARCHAR(64) NOT NULL,
    artifact_entry INT NOT NULL,
    action VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT NULL
);

CREATE TABLE IF NOT EXISTS wm_rollback_snapshot (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    artifact_type VARCHAR(64) NOT NULL,
    artifact_entry INT NOT NULL,
    snapshot_json LONGTEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS wm_reserved_slot (
    EntityType VARCHAR(64) NOT NULL,
    ReservedID INT NOT NULL,
    SlotStatus VARCHAR(32) NOT NULL DEFAULT 'free',
    ArcKey VARCHAR(128) NULL,
    CharacterGUID INT NULL,
    SourceQuestID INT NULL,
    NotesJSON LONGTEXT NULL,
    CreatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (EntityType, ReservedID),
    KEY idx_reserved_slot_status (EntityType, SlotStatus)
);
