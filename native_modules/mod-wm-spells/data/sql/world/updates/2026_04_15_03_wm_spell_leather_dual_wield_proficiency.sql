-- Extend the explicit WM combat proficiency package with Leather armor and Dual Wield.
-- Leather needs DBC validity at login. Dual Wield is spell-gated by stock spell 674
-- and is granted only through the explicit per-player character_spell path.

INSERT INTO skillraceclassinfo_dbc
    (ID, SkillID, RaceMask, ClassMask, Flags, MinLevel, SkillTierID, SkillCostIndex)
VALUES
    (100414, 414, 0, 0, 0, 0, 0, 0)
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
    (100414, 414, 9077, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0)
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
