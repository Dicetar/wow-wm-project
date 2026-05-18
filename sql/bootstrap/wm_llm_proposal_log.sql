-- LLM proposal provenance log
-- Records every LLM-generated proposal with its raw response, parsed JSON,
-- and lifecycle state: PENDING -> ADOPTED | REJECTED

CREATE TABLE IF NOT EXISTS wm_llm_proposal_log (
    id              INT UNSIGNED  AUTO_INCREMENT PRIMARY KEY,
    schema_version  VARCHAR(80)   NOT NULL,
    instruction     TEXT          NOT NULL,
    raw_response    MEDIUMTEXT    NOT NULL,
    parsed_json     MEDIUMTEXT    DEFAULT NULL,
    model_id        VARCHAR(120)  DEFAULT NULL,
    operator        VARCHAR(80)   DEFAULT NULL,
    state           VARCHAR(20)   NOT NULL DEFAULT 'PENDING',  -- PENDING | ADOPTED | REJECTED
    metadata_json   TEXT          DEFAULT NULL,
    created_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    adopted_at      DATETIME      DEFAULT NULL,
    INDEX idx_state (state),
    INDEX idx_schema (schema_version),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
