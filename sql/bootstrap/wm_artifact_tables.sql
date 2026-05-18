-- WM content artifact lifecycle registry
-- Tracks every WM-owned WoW ID (quest, item, creature, spell, gossip, scene)
-- with status: reserved -> active -> retired | error

CREATE TABLE IF NOT EXISTS wm_artifact (
    id             INT UNSIGNED  NOT NULL,
    kind           VARCHAR(30)   NOT NULL,
    status         VARCHAR(20)   NOT NULL DEFAULT 'reserved',
    label          VARCHAR(200)  NOT NULL DEFAULT '',
    owner_key      VARCHAR(120)  NOT NULL DEFAULT '',
    schema_version VARCHAR(40)   NOT NULL DEFAULT 'wm.artifact.v1',
    metadata_json  TEXT          DEFAULT NULL,
    created_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id, kind),
    INDEX idx_kind_status (kind, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
