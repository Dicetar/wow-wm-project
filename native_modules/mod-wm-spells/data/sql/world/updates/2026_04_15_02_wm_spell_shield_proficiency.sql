-- WM persistent Shield proficiency support.
-- DBC override rows make SkillID 433 valid for explicitly granted WM players at login.
-- They do not grant Shield by themselves; do not add Shield to playercreateinfo or bot maintenance paths.

INSERT INTO skillraceclassinfo_dbc
    (ID, SkillID, RaceMask, ClassMask, Flags, MinLevel, SkillTierID, SkillCostIndex)
VALUES
    (100433, 433, 0, 0, 0, 0, 0, 0)
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
    (100433, 433, 9116, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0),
    (100434, 433, 107, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0)
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

INSERT INTO wm_spell_shell
    (ShellSpellID, ShellKey, FamilyID, Label, State, ClientPatchVersion, OwnershipKey, ProvenanceJSON)
VALUES
    (
        944000,
        'jecia_intellect_block_v1',
        'passive_aura',
        'Jecia''s Guarded Mind',
        'planned',
        'wm_spell_shell_bank.v1',
        'wm.spell_shell:jecia_intellect_block_v1',
        '{"notes":["Passive block-rating behavior only. Shield proficiency persistence is granted through character_skills plus DBC validity."]}'
    )
ON DUPLICATE KEY UPDATE
    ShellKey = VALUES(ShellKey),
    FamilyID = VALUES(FamilyID),
    Label = VALUES(Label),
    State = VALUES(State),
    ClientPatchVersion = VALUES(ClientPatchVersion),
    OwnershipKey = VALUES(OwnershipKey),
    ProvenanceJSON = VALUES(ProvenanceJSON),
    UpdatedAt = CURRENT_TIMESTAMP;

INSERT INTO wm_spell_behavior
    (ShellSpellID, BehaviorKind, ConfigJSON, Status)
VALUES
    (
        944000,
        'passive_intellect_block_v1',
        '{"intellect_to_block_rating_scale":1.0,"spell_power_to_block_rating_scale":1.0,"spell_school_mask":126,"max_block_rating":0}',
        'active'
    )
ON DUPLICATE KEY UPDATE
    BehaviorKind = VALUES(BehaviorKind),
    ConfigJSON = VALUES(ConfigJSON),
    Status = VALUES(Status),
    UpdatedAt = CURRENT_TIMESTAMP;
