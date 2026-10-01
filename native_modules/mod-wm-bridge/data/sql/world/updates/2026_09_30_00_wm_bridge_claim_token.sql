SET @wm_sql = (
    SELECT IF(
        EXISTS(
            SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'wm_bridge_action_request'
              AND COLUMN_NAME = 'ClaimToken'
        ),
        'SELECT 1',
        'ALTER TABLE wm_bridge_action_request ADD COLUMN ClaimToken VARCHAR(36) NULL AFTER ClaimedAt'
    )
);
PREPARE wm_stmt FROM @wm_sql;
EXECUTE wm_stmt;
DEALLOCATE PREPARE wm_stmt;
