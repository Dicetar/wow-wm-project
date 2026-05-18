-- wm_journal_v2.sql
-- Journal V2: counter table, special events, zone rollup

CREATE TABLE IF NOT EXISTS wm_journal_counter (
    player_guid   INT UNSIGNED NOT NULL,
    subject_entry INT UNSIGNED NOT NULL,
    counter_key   VARCHAR(60) NOT NULL,
    count         INT UNSIGNED NOT NULL DEFAULT 0,
    last_at       DATETIME DEFAULT NULL,
    PRIMARY KEY (player_guid, subject_entry, counter_key),
    INDEX (player_guid),
    INDEX (subject_entry)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS wm_journal_special_event (
    id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    player_guid   INT UNSIGNED NOT NULL,
    subject_entry INT UNSIGNED DEFAULT NULL,
    event_type    VARCHAR(60) NOT NULL,
    narrative_key VARCHAR(100) DEFAULT NULL,
    data_json     TEXT DEFAULT NULL,
    at            DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX (player_guid, subject_entry),
    INDEX (player_guid, event_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS wm_zone_rollup (
    zone_id       INT UNSIGNED NOT NULL,
    rollup_key    VARCHAR(60) NOT NULL,
    value_int     INT DEFAULT NULL,
    value_str     VARCHAR(200) DEFAULT NULL,
    computed_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (zone_id, rollup_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
