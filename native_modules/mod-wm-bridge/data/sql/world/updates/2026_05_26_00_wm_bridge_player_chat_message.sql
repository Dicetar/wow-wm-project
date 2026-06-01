INSERT INTO wm_bridge_action_policy (ActionKind, Profile, Enabled, MaxRiskLevel, CooldownMS, BurstLimit, AdminOnly) VALUES
('player_chat_message', 'default', 0, 'low', 1000, 5, 0)
ON DUPLICATE KEY UPDATE
    MaxRiskLevel = VALUES(MaxRiskLevel),
    CooldownMS = VALUES(CooldownMS),
    BurstLimit = VALUES(BurstLimit),
    AdminOnly = VALUES(AdminOnly);
