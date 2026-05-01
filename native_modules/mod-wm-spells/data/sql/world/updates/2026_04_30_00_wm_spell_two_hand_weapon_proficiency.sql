-- Extend explicit WM combat proficiency with armor and two-handed weapon families.
-- These DBC override rows make the skill lines login-valid for explicit per-player grants.
-- They do not grant armor or weapons globally; character rows and wm_spell_grant still target one player GUID.
-- Plate keeps MinLevel 40, and the grant CLI skips the Plate character rows below that level.

INSERT INTO skillraceclassinfo_dbc
    (ID, SkillID, RaceMask, ClassMask, Flags, MinLevel, SkillTierID, SkillCostIndex)
VALUES
    (100293, 293, 2047, 8, 128, 40, 0, 0),
    (100055, 55, 2047, 8, 128, 0, 0, 0),
    (100172, 172, 2047, 8, 128, 0, 0, 0),
    (100229, 229, 2047, 8, 128, 0, 0, 0),
    (100413, 413, 2047, 8, 128, 0, 0, 0)
ON DUPLICATE KEY UPDATE
    SkillID = VALUES(SkillID),
    RaceMask = VALUES(RaceMask),
    ClassMask = VALUES(ClassMask),
    Flags = VALUES(Flags),
    MinLevel = VALUES(MinLevel),
    SkillTierID = VALUES(SkillTierID),
    SkillCostIndex = VALUES(SkillCostIndex);

INSERT INTO skilllineability_dbc
    (
        ID,
        SkillLine,
        Spell,
        RaceMask,
        ClassMask,
        ExcludeRace,
        ExcludeClass,
        MinSkillLineRank,
        SupercededBySpell,
        AcquireMethod,
        TrivialSkillLineRankHigh,
        TrivialSkillLineRankLow,
        CharacterPoints_1,
        CharacterPoints_2
    )
VALUES
    (100293, 293, 750, 0, 8, 0, 0, 1, 0, 2, 0, 0, 0, 0),
    (100055, 55, 202, 0, 8, 0, 0, 1, 0, 2, 0, 0, 0, 0),
    (100172, 172, 197, 0, 8, 0, 0, 1, 0, 2, 0, 0, 0, 0),
    (100229, 229, 200, 0, 8, 0, 0, 1, 0, 2, 0, 0, 0, 0),
    (100413, 413, 8737, 0, 8, 0, 0, 1, 0, 2, 0, 0, 0, 0)
ON DUPLICATE KEY UPDATE
    SkillLine = VALUES(SkillLine),
    Spell = VALUES(Spell),
    RaceMask = VALUES(RaceMask),
    ClassMask = VALUES(ClassMask),
    ExcludeRace = VALUES(ExcludeRace),
    ExcludeClass = VALUES(ExcludeClass),
    MinSkillLineRank = VALUES(MinSkillLineRank),
    SupercededBySpell = VALUES(SupercededBySpell),
    AcquireMethod = VALUES(AcquireMethod),
    TrivialSkillLineRankHigh = VALUES(TrivialSkillLineRankHigh),
    TrivialSkillLineRankLow = VALUES(TrivialSkillLineRankLow),
    CharacterPoints_1 = VALUES(CharacterPoints_1),
    CharacterPoints_2 = VALUES(CharacterPoints_2);
