-- WM Living World persistent state tables
-- Each table holds live decision state that Python reads/writes between evaluations.

-- Nemesis records: one row per player+subject awakening
CREATE TABLE IF NOT EXISTS wm_nemesis (
    player_guid     INT UNSIGNED  NOT NULL,
    subject_entry   INT UNSIGNED  NOT NULL,
    nemesis_name    VARCHAR(120)  NOT NULL DEFAULT '',
    arc_key         VARCHAR(160)  NOT NULL DEFAULT '',
    status          VARCHAR(20)   NOT NULL DEFAULT 'awakened',  -- awakened | slain | cooldown
    awakened_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at     DATETIME      DEFAULT NULL,
    PRIMARY KEY (player_guid, subject_entry),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Patron favor: one row per player+patron
CREATE TABLE IF NOT EXISTS wm_patron (
    player_guid     INT UNSIGNED  NOT NULL,
    patron_key      VARCHAR(80)   NOT NULL,
    favor           INT           NOT NULL DEFAULT 0,
    tier_name       VARCHAR(60)   DEFAULT NULL,
    updated_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (player_guid, patron_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Zone mood snapshot: refreshed by evaluate_zone_mood
CREATE TABLE IF NOT EXISTS wm_zone_mood (
    zone_id         INT UNSIGNED  NOT NULL,
    player_guid     INT UNSIGNED  NOT NULL DEFAULT 0,  -- 0 = zone-wide
    mood_key        VARCHAR(60)   NOT NULL DEFAULT 'neutral',
    intensity       TINYINT       NOT NULL DEFAULT 1,
    evaluated_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (zone_id, player_guid),
    INDEX idx_zone (zone_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Oath state: one row per player+oath_key
CREATE TABLE IF NOT EXISTS wm_oath (
    player_guid      INT UNSIGNED  NOT NULL,
    oath_key         VARCHAR(80)   NOT NULL,
    constraint_label VARCHAR(200)  NOT NULL DEFAULT '',
    target_count     INT           NOT NULL DEFAULT 1,
    current_count    INT           NOT NULL DEFAULT 0,
    phase            VARCHAR(20)   NOT NULL DEFAULT 'accept',  -- accept | resolve
    oath_quest_id    INT UNSIGNED  DEFAULT NULL,
    created_at       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (player_guid, oath_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Rumor dispatch log: cooldown tracking + audit trail
CREATE TABLE IF NOT EXISTS wm_rumor_active (
    id              INT UNSIGNED  AUTO_INCREMENT PRIMARY KEY,
    player_guid     INT UNSIGNED  NOT NULL,
    subject_entry   INT UNSIGNED  NOT NULL DEFAULT 0,
    deed_count      INT           NOT NULL DEFAULT 0,
    line            TEXT          NOT NULL,
    dispatched_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_player_subject (player_guid, subject_entry, dispatched_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Mentor relationship: tracks which step the player is on
CREATE TABLE IF NOT EXISTS wm_mentor_relationship (
    player_guid       INT UNSIGNED  NOT NULL,
    mentor_npc_entry  INT UNSIGNED  NOT NULL,
    task_key          VARCHAR(120)  NOT NULL,
    current_step_key  VARCHAR(120)  DEFAULT NULL,
    completed_steps   TEXT          DEFAULT NULL,  -- JSON array of completed step_keys
    status            VARCHAR(20)   NOT NULL DEFAULT 'active',  -- active | complete | abandoned
    started_at        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (player_guid, task_key),
    INDEX idx_mentor (mentor_npc_entry)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
