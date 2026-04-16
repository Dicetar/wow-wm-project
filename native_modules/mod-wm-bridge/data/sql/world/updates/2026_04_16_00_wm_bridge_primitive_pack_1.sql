SET @wm_sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'wm_bridge_world_object'
              AND COLUMN_NAME = 'LiveGUIDLow'
        ),
        'SELECT 1',
        'ALTER TABLE wm_bridge_world_object ADD COLUMN LiveGUIDLow INT NULL AFTER LiveGUID'
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
              AND TABLE_NAME = 'wm_bridge_world_object'
              AND INDEX_NAME = 'idx_wm_bridge_world_object_live_low'
        ),
        'SELECT 1',
        'ALTER TABLE wm_bridge_world_object ADD INDEX idx_wm_bridge_world_object_live_low (LiveGUIDLow)'
    )
);
PREPARE wm_stmt FROM @wm_sql;
EXECUTE wm_stmt;
DEALLOCATE PREPARE wm_stmt;

INSERT INTO wm_bridge_action_policy (ActionKind, Profile, Enabled, MaxRiskLevel, CooldownMS, BurstLimit, AdminOnly) VALUES
('player_apply_aura', 'default', 0, 'medium', 1000, 5, 0),
('player_remove_aura', 'default', 0, 'medium', 1000, 5, 0),
('player_restore_health_power', 'default', 0, 'low', 1000, 5, 0),
('player_add_item', 'default', 0, 'medium', 1000, 5, 0),
('player_add_money', 'default', 0, 'medium', 1000, 5, 0),
('player_add_reputation', 'default', 0, 'medium', 1000, 5, 0),
('creature_say', 'default', 0, 'low', 1000, 5, 0),
('creature_emote', 'default', 0, 'low', 1000, 5, 0),
('creature_spawn', 'default', 0, 'medium', 1000, 5, 0),
('creature_despawn', 'default', 0, 'medium', 1000, 5, 0)
ON DUPLICATE KEY UPDATE
    MaxRiskLevel = VALUES(MaxRiskLevel),
    CooldownMS = VALUES(CooldownMS),
    BurstLimit = VALUES(BurstLimit),
    AdminOnly = VALUES(AdminOnly);
