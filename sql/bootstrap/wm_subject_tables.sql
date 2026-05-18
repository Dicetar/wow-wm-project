-- wm_subject_tables.sql
-- Subject enrichment and cluster tables for Phase 1

CREATE TABLE IF NOT EXISTS wm_subject_definition (
    entry           INT UNSIGNED NOT NULL,
    display_name    VARCHAR(100) NOT NULL,
    archetype_key   VARCHAR(60) DEFAULT NULL,
    settlement_role VARCHAR(40) DEFAULT NULL,
    area_context_json TEXT DEFAULT NULL,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (entry)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS wm_subject_enrichment (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    entry       INT UNSIGNED NOT NULL,
    note_key    VARCHAR(80) NOT NULL,
    note_value  TEXT NOT NULL,
    added_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX (entry)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS wm_subject_cluster (
    cluster_key  VARCHAR(80) NOT NULL,
    entry        INT UNSIGNED NOT NULL,
    cluster_type VARCHAR(30) NOT NULL,
    zone_id      INT UNSIGNED DEFAULT NULL,
    PRIMARY KEY (cluster_key, entry)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
