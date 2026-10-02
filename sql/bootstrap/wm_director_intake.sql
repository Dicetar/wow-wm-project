-- Durable, immutable evidence and typed decision for one selected player request.
CREATE TABLE IF NOT EXISTS wm_director_intake (
    OriginKey VARCHAR(191) NOT NULL PRIMARY KEY,
    PlayerGUID BIGINT UNSIGNED NOT NULL,
    EvidenceHash CHAR(64) NOT NULL,
    EvidenceJSON LONGTEXT NOT NULL,
    DecisionJSON LONGTEXT NULL,
    State VARCHAR(32) NOT NULL DEFAULT 'received',
    Revision INT UNSIGNED NOT NULL DEFAULT 0,
    CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    DecidedAt DATETIME NULL,
    KEY ix_wm_director_intake_player (PlayerGUID, CreatedAt)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE wm_director_intake MODIFY COLUMN State VARCHAR(32) NOT NULL DEFAULT 'received';

CREATE TABLE IF NOT EXISTS wm_director_development_task (
    TaskID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    OriginKey VARCHAR(191) NOT NULL,
    PlayerGUID BIGINT UNSIGNED NOT NULL,
    CapabilityKey VARCHAR(191) NOT NULL,
    TaskJSON LONGTEXT NOT NULL,
    State VARCHAR(32) NOT NULL DEFAULT 'proposed',
    CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_wm_director_development_task_origin (OriginKey),
    KEY ix_wm_director_development_task_capability (CapabilityKey, State),
    CONSTRAINT fk_wm_director_development_task_intake FOREIGN KEY (OriginKey)
        REFERENCES wm_director_intake (OriginKey)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
