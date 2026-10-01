-- Additive extension of wm_director_request. Apply wm_director_request.sql first.
CREATE TABLE IF NOT EXISTS wm_director_artifact (
    RequestID BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    ArtifactHash CHAR(64) NOT NULL,
    ArtifactJSON LONGTEXT NOT NULL,
    PreviewJSON LONGTEXT NOT NULL,
    EvidenceJSON LONGTEXT NOT NULL,
    CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_wm_director_artifact_request FOREIGN KEY (RequestID)
        REFERENCES wm_director_request (RequestID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS wm_director_authorization (
    RequestID BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    ArtifactHash CHAR(64) NOT NULL,
    PlayerGUID BIGINT UNSIGNED NOT NULL,
    Mode VARCHAR(16) NOT NULL,
    Principal VARCHAR(96) NOT NULL,
    PolicyJSON LONGTEXT NOT NULL,
    ExpiresAt DATETIME NOT NULL,
    AuthorizedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_wm_director_authorization_request FOREIGN KEY (RequestID)
        REFERENCES wm_director_request (RequestID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS wm_director_proof (
    RequestID BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    ProofJSON LONGTEXT NOT NULL,
    VerifiedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_wm_director_proof_request FOREIGN KEY (RequestID)
        REFERENCES wm_director_request (RequestID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS wm_director_effect (
    EffectID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    RequestID BIGINT UNSIGNED NOT NULL,
    StepOrdinal INT UNSIGNED NOT NULL,
    EffectKey VARCHAR(191) NOT NULL,
    Kind VARCHAR(64) NOT NULL,
    State VARCHAR(32) NOT NULL DEFAULT 'pending',
    Revision INT UNSIGNED NOT NULL DEFAULT 0,
    ReceiptJSON LONGTEXT NULL,
    UpdatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_wm_director_effect_step (RequestID, StepOrdinal),
    UNIQUE KEY uq_wm_director_effect_key (EffectKey),
    KEY ix_wm_director_effect_state (State, UpdatedAt),
    CONSTRAINT fk_wm_director_effect_request FOREIGN KEY (RequestID)
        REFERENCES wm_director_request (RequestID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
