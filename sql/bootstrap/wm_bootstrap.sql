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
