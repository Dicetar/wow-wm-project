SET @wm_sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'wm_bridge_action_request'
              AND COLUMN_NAME = 'ClaimExpiresAt'
        ),
        'SELECT 1',
        'ALTER TABLE wm_bridge_action_request ADD COLUMN ClaimExpiresAt TIMESTAMP NULL DEFAULT NULL AFTER ClaimedAt'
    )
);
PREPARE wm_stmt FROM @wm_sql;
EXECUTE wm_stmt;
DEALLOCATE PREPARE wm_stmt;

SET @wm_sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'wm_bridge_action_request'
              AND COLUMN_NAME = 'AttemptCount'
        ),
        'SELECT 1',
        'ALTER TABLE wm_bridge_action_request ADD COLUMN AttemptCount INT NOT NULL DEFAULT 0 AFTER ClaimExpiresAt'
    )
);
PREPARE wm_stmt FROM @wm_sql;
EXECUTE wm_stmt;
DEALLOCATE PREPARE wm_stmt;

SET @wm_sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'wm_bridge_action_request'
              AND COLUMN_NAME = 'MaxAttempts'
        ),
        'SELECT 1',
        'ALTER TABLE wm_bridge_action_request ADD COLUMN MaxAttempts INT NOT NULL DEFAULT 3 AFTER AttemptCount'
    )
);
PREPARE wm_stmt FROM @wm_sql;
EXECUTE wm_stmt;
DEALLOCATE PREPARE wm_stmt;

SET @wm_sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'wm_bridge_action_request'
              AND COLUMN_NAME = 'SequenceID'
        ),
        'SELECT 1',
        'ALTER TABLE wm_bridge_action_request ADD COLUMN SequenceID VARCHAR(128) NULL AFTER ExpiresAt'
    )
);
PREPARE wm_stmt FROM @wm_sql;
EXECUTE wm_stmt;
DEALLOCATE PREPARE wm_stmt;

SET @wm_sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'wm_bridge_action_request'
              AND COLUMN_NAME = 'SequenceOrder'
        ),
        'SELECT 1',
        'ALTER TABLE wm_bridge_action_request ADD COLUMN SequenceOrder INT NOT NULL DEFAULT 0 AFTER SequenceID'
    )
);
PREPARE wm_stmt FROM @wm_sql;
EXECUTE wm_stmt;
DEALLOCATE PREPARE wm_stmt;

SET @wm_sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'wm_bridge_action_request'
              AND COLUMN_NAME = 'WaitForPrior'
        ),
        'SELECT 1',
        'ALTER TABLE wm_bridge_action_request ADD COLUMN WaitForPrior TINYINT(1) NOT NULL DEFAULT 0 AFTER SequenceOrder'
    )
);
PREPARE wm_stmt FROM @wm_sql;
EXECUTE wm_stmt;
DEALLOCATE PREPARE wm_stmt;

SET @wm_sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'wm_bridge_action_request'
              AND COLUMN_NAME = 'Priority'
        ),
        'SELECT 1',
        'ALTER TABLE wm_bridge_action_request ADD COLUMN Priority TINYINT NOT NULL DEFAULT 5 AFTER WaitForPrior'
    )
);
PREPARE wm_stmt FROM @wm_sql;
EXECUTE wm_stmt;
DEALLOCATE PREPARE wm_stmt;

SET @wm_sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'wm_bridge_action_request'
              AND COLUMN_NAME = 'PurgeAfter'
        ),
        'SELECT 1',
        'ALTER TABLE wm_bridge_action_request ADD COLUMN PurgeAfter TIMESTAMP NULL DEFAULT NULL AFTER Priority'
    )
);
PREPARE wm_stmt FROM @wm_sql;
EXECUTE wm_stmt;
DEALLOCATE PREPARE wm_stmt;

SET @wm_sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'wm_bridge_action_request'
              AND COLUMN_NAME = 'TargetMapID'
        ),
        'SELECT 1',
        'ALTER TABLE wm_bridge_action_request ADD COLUMN TargetMapID INT NULL AFTER PurgeAfter'
    )
);
PREPARE wm_stmt FROM @wm_sql;
EXECUTE wm_stmt;
DEALLOCATE PREPARE wm_stmt;

SET @wm_sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'wm_bridge_action_request'
              AND COLUMN_NAME = 'TargetX'
        ),
        'SELECT 1',
        'ALTER TABLE wm_bridge_action_request ADD COLUMN TargetX FLOAT NULL AFTER TargetMapID'
    )
);
PREPARE wm_stmt FROM @wm_sql;
EXECUTE wm_stmt;
DEALLOCATE PREPARE wm_stmt;

SET @wm_sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'wm_bridge_action_request'
              AND COLUMN_NAME = 'TargetY'
        ),
        'SELECT 1',
        'ALTER TABLE wm_bridge_action_request ADD COLUMN TargetY FLOAT NULL AFTER TargetX'
    )
);
PREPARE wm_stmt FROM @wm_sql;
EXECUTE wm_stmt;
DEALLOCATE PREPARE wm_stmt;

SET @wm_sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'wm_bridge_action_request'
              AND COLUMN_NAME = 'TargetZ'
        ),
        'SELECT 1',
        'ALTER TABLE wm_bridge_action_request ADD COLUMN TargetZ FLOAT NULL AFTER TargetY'
    )
);
PREPARE wm_stmt FROM @wm_sql;
EXECUTE wm_stmt;
DEALLOCATE PREPARE wm_stmt;

SET @wm_sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'wm_bridge_action_request'
              AND COLUMN_NAME = 'TargetO'
        ),
        'SELECT 1',
        'ALTER TABLE wm_bridge_action_request ADD COLUMN TargetO FLOAT NULL AFTER TargetZ'
    )
);
PREPARE wm_stmt FROM @wm_sql;
EXECUTE wm_stmt;
DEALLOCATE PREPARE wm_stmt;

SET @wm_sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'wm_bridge_action_request'
              AND COLUMN_NAME = 'TargetPlayerGUID'
        ),
        'SELECT 1',
        'ALTER TABLE wm_bridge_action_request ADD COLUMN TargetPlayerGUID INT NULL AFTER TargetO'
    )
);
PREPARE wm_stmt FROM @wm_sql;
EXECUTE wm_stmt;
DEALLOCATE PREPARE wm_stmt;

SET @wm_sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'wm_bridge_action_request'
              AND INDEX_NAME = 'idx_wm_bridge_action_request_priority'
        ),
        'SELECT 1',
        'ALTER TABLE wm_bridge_action_request ADD INDEX idx_wm_bridge_action_request_priority (Status, Priority, RequestID)'
    )
);
PREPARE wm_stmt FROM @wm_sql;
EXECUTE wm_stmt;
DEALLOCATE PREPARE wm_stmt;

SET @wm_sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'wm_bridge_action_request'
              AND INDEX_NAME = 'idx_wm_bridge_action_request_claim_expiry'
        ),
        'SELECT 1',
        'ALTER TABLE wm_bridge_action_request ADD INDEX idx_wm_bridge_action_request_claim_expiry (Status, ClaimExpiresAt)'
    )
);
PREPARE wm_stmt FROM @wm_sql;
EXECUTE wm_stmt;
DEALLOCATE PREPARE wm_stmt;

SET @wm_sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'wm_bridge_action_request'
              AND INDEX_NAME = 'idx_wm_bridge_action_request_sequence'
        ),
        'SELECT 1',
        'ALTER TABLE wm_bridge_action_request ADD INDEX idx_wm_bridge_action_request_sequence (SequenceID, SequenceOrder, Status)'
    )
);
PREPARE wm_stmt FROM @wm_sql;
EXECUTE wm_stmt;
DEALLOCATE PREPARE wm_stmt;

SET @wm_sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'wm_bridge_action_request'
              AND INDEX_NAME = 'idx_wm_bridge_action_request_purge'
        ),
        'SELECT 1',
        'ALTER TABLE wm_bridge_action_request ADD INDEX idx_wm_bridge_action_request_purge (PurgeAfter, Status)'
    )
);
PREPARE wm_stmt FROM @wm_sql;
EXECUTE wm_stmt;
DEALLOCATE PREPARE wm_stmt;

INSERT INTO wm_bridge_action_policy (ActionKind, Profile, Enabled, MaxRiskLevel, CooldownMS, BurstLimit, AdminOnly) VALUES
('quest_complete', 'default', 0, 'medium', 1000, 5, 0),
('creature_set_display_id', 'default', 0, 'medium', 1000, 5, 0),
('creature_set_scale', 'default', 0, 'medium', 1000, 5, 0),
('creature_set_health_pct', 'default', 0, 'medium', 1000, 5, 0),
('creature_attack_player', 'default', 0, 'high', 1000, 2, 0),
('creature_flee', 'default', 0, 'medium', 1000, 5, 0),
('player_play_sound', 'default', 0, 'low', 1000, 5, 0),
('player_play_movie', 'default', 0, 'medium', 1000, 5, 0)
ON DUPLICATE KEY UPDATE
    Enabled = VALUES(Enabled),
    MaxRiskLevel = VALUES(MaxRiskLevel),
    CooldownMS = VALUES(CooldownMS),
    BurstLimit = VALUES(BurstLimit),
    AdminOnly = VALUES(AdminOnly);
