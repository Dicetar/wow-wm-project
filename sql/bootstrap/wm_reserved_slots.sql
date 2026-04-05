CREATE TABLE IF NOT EXISTS wm_reserved_slot (
    SlotID BIGINT AUTO_INCREMENT PRIMARY KEY,
    EntityType VARCHAR(64) NOT NULL,
    ReservedID INT NOT NULL,
    SlotStatus VARCHAR(32) NOT NULL DEFAULT 'free',
    ArcKey VARCHAR(128) NULL,
    CharacterGUID INT NULL,
    SourceQuestID INT NULL,
    NotesJSON LONGTEXT NULL,
    UpdatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_entity_reserved (EntityType, ReservedID),
    KEY idx_entity_status (EntityType, SlotStatus)
);
