INSERT INTO wm_bridge_action_policy (ActionKind, Profile, Enabled, MaxRiskLevel, CooldownMS, BurstLimit, AdminOnly) VALUES
('player_cast_spell', 'default', 0, 'medium', 1000, 5, 0),
('player_set_display_id', 'default', 0, 'medium', 1000, 5, 0),
('creature_cast_spell', 'default', 0, 'medium', 1000, 5, 0),
('creature_set_display_id', 'default', 0, 'medium', 1000, 5, 0),
('creature_set_scale', 'default', 0, 'medium', 1000, 5, 0)
ON DUPLICATE KEY UPDATE
    MaxRiskLevel = VALUES(MaxRiskLevel),
    CooldownMS = VALUES(CooldownMS),
    BurstLimit = VALUES(BurstLimit),
    AdminOnly = VALUES(AdminOnly);
