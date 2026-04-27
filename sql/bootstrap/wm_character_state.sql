CREATE TABLE IF NOT EXISTS wm_character_profile (
    CharacterGUID INT NOT NULL PRIMARY KEY,
    CharacterName VARCHAR(64) NOT NULL,
    WMPersona VARCHAR(64) NOT NULL DEFAULT 'default',
    Tone VARCHAR(64) NOT NULL DEFAULT 'adaptive',
    PreferredThemesJSON LONGTEXT NULL,
    AvoidedThemesJSON LONGTEXT NULL,
    UpdatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS wm_character_arc_state (
    CharacterGUID INT NOT NULL,
    ArcKey VARCHAR(128) NOT NULL,
    StageKey VARCHAR(128) NOT NULL,
    Status VARCHAR(32) NOT NULL DEFAULT 'active',
    BranchKey VARCHAR(128) NULL,
    Summary TEXT NULL,
    UpdatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (CharacterGUID, ArcKey)
);

CREATE TABLE IF NOT EXISTS wm_character_unlock (
    CharacterGUID INT NOT NULL,
    UnlockKind VARCHAR(32) NOT NULL,
    UnlockID INT NOT NULL,
    SourceArcKey VARCHAR(128) NULL,
    SourceQuestID INT NULL,
    GrantMethod VARCHAR(32) NOT NULL DEFAULT 'control',
    BotEligible TINYINT NOT NULL DEFAULT 0,
    GrantedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (CharacterGUID, UnlockKind, UnlockID)
);

CREATE TABLE IF NOT EXISTS wm_character_reward_instance (
    CharacterGUID INT NOT NULL,
    RewardKind VARCHAR(32) NOT NULL,
    TemplateID INT NOT NULL,
    SourceArcKey VARCHAR(128) NULL,
    SourceQuestID INT NULL,
    IsEquippedGate TINYINT NOT NULL DEFAULT 0,
    GrantedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (CharacterGUID, RewardKind, TemplateID, GrantedAt)
);

CREATE TABLE IF NOT EXISTS wm_character_conversation_steering (
    CharacterGUID INT NOT NULL,
    SteeringKey VARCHAR(128) NOT NULL,
    SteeringKind VARCHAR(64) NOT NULL DEFAULT 'player_preference',
    Body TEXT NOT NULL,
    Priority INT NOT NULL DEFAULT 0,
    Source VARCHAR(64) NOT NULL DEFAULT 'operator',
    IsActive TINYINT NOT NULL DEFAULT 1,
    MetadataJSON LONGTEXT NULL,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (CharacterGUID, SteeringKey),
    KEY idx_wm_character_steering_active (CharacterGUID, IsActive, Priority)
);

CREATE TABLE IF NOT EXISTS wm_character_prompt_queue (
    QueueID BIGINT AUTO_INCREMENT PRIMARY KEY,
    CharacterGUID INT NOT NULL,
    PromptKind VARCHAR(32) NOT NULL,
    Body TEXT NOT NULL,
    IsConsumed TINYINT NOT NULL DEFAULT 0,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
