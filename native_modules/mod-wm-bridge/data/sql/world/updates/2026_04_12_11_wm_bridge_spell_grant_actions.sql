INSERT INTO wm_bridge_action_policy (ActionKind, Profile, Enabled, MaxRiskLevel, CooldownMS, BurstLimit, AdminOnly) VALUES
('player_learn_spell', 'default', 0, 'medium', 1000, 5, 0),
('player_unlearn_spell', 'default', 0, 'medium', 1000, 5, 0)
ON DUPLICATE KEY UPDATE
    Enabled = VALUES(Enabled),
    MaxRiskLevel = VALUES(MaxRiskLevel),
    CooldownMS = VALUES(CooldownMS),
    BurstLimit = VALUES(BurstLimit),
    AdminOnly = VALUES(AdminOnly);
