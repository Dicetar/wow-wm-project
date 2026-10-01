-- Durable pilot for one event-origin native action. Apply to the configured world DB.
CREATE TABLE IF NOT EXISTS wm_director_request (
    RequestID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    OriginKey VARCHAR(191) NOT NULL,
    PlayerGUID BIGINT UNSIGNED NOT NULL,
    Verb VARCHAR(80) NOT NULL,
    ProposalHash CHAR(64) NOT NULL,
    NativeKey VARCHAR(191) NOT NULL,
    State VARCHAR(32) NOT NULL DEFAULT 'received',
    Revision INT UNSIGNED NOT NULL DEFAULT 0,
    NativeRequestID BIGINT UNSIGNED NULL,
    ResultJSON LONGTEXT NULL,
    CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_wm_director_origin (OriginKey),
    UNIQUE KEY uq_wm_director_native (NativeKey),
    KEY ix_wm_director_state (State, UpdatedAt),
    KEY ix_wm_director_player (PlayerGUID, CreatedAt)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS wm_director_transition (
    TransitionID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    RequestID BIGINT UNSIGNED NOT NULL,
    Revision INT UNSIGNED NOT NULL,
    FromState VARCHAR(32) NULL,
    ToState VARCHAR(32) NOT NULL,
    Reason VARCHAR(160) NOT NULL,
    CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_wm_director_transition (RequestID, Revision),
    KEY ix_wm_director_transition_request (RequestID, CreatedAt),
    CONSTRAINT fk_wm_director_transition_request FOREIGN KEY (RequestID)
        REFERENCES wm_director_request (RequestID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
