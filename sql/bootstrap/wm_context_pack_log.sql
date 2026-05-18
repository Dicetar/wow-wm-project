CREATE TABLE IF NOT EXISTS wm_context_pack_log (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    player_guid     INT UNSIGNED NOT NULL,
    pack_hash       CHAR(16) NOT NULL,
    pack_json       MEDIUMTEXT NOT NULL,
    pack_version    VARCHAR(40) NOT NULL DEFAULT 'wm.context_pack.v2',
    generated_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    source_event_id INT UNSIGNED DEFAULT NULL,
    INDEX (player_guid, generated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
