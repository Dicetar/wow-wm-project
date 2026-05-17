-- WM Journal V2: per-player per-zone deed rollup.
-- Populated by wm.journal.projector from wm_event_log (ZoneID). Read by the
-- Living World Local Legend feature. Idempotent create.

CREATE TABLE IF NOT EXISTS wm_player_zone_stats (
    PlayerGUID        INT UNSIGNED NOT NULL,
    ZoneID            INT UNSIGNED NOT NULL,
    KillCount         INT UNSIGNED NOT NULL DEFAULT 0,
    QuestCompleteCount INT UNSIGNED NOT NULL DEFAULT 0,
    NotableCount      INT UNSIGNED NOT NULL DEFAULT 0,
    LastActivityAt    DATETIME NULL,
    PRIMARY KEY (PlayerGUID, ZoneID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
