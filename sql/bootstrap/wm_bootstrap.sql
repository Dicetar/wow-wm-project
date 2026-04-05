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
