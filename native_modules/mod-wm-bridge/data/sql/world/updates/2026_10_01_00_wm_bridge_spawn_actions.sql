INSERT IGNORE INTO wm_bridge_action_policy
    (ActionKind, Profile, Enabled, MaxRiskLevel, CooldownMS, BurstLimit, AdminOnly)
VALUES
    ('world_spawn_create', 'default', 1, 'high', 0, 20, 1),
    ('world_spawn_update', 'default', 1, 'high', 0, 20, 1),
    ('world_spawn_delete', 'default', 1, 'high', 0, 20, 1);
