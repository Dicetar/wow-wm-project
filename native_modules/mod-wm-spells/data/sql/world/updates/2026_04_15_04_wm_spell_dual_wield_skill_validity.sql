-- Make Dual Wield skill line 118 valid for explicit WM combat proficiency grants.
-- This does not grant Dual Wield by itself; character rows and wm_spell_grant still target one player GUID.

INSERT INTO skillraceclassinfo_dbc
    (ID, SkillID, RaceMask, ClassMask, Flags, MinLevel, SkillTierID, SkillCostIndex)
VALUES
    (100118, 118, 0, 0, 0, 0, 0, 0)
ON DUPLICATE KEY UPDATE
    SkillID = VALUES(SkillID),
    RaceMask = VALUES(RaceMask),
    ClassMask = VALUES(ClassMask),
    Flags = VALUES(Flags),
    MinLevel = VALUES(MinLevel),
    SkillTierID = VALUES(SkillTierID),
    SkillCostIndex = VALUES(SkillCostIndex);
