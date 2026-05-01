-- WM random-enchant vellum pool expansion.
-- Server truth:
-- - Stock weapon enchant IDs stay stock: 3827 Massacre, 3239 Icebreaker, 3789 Berserking.
-- - Missing rating rows use WM-owned SpellItemEnchantment.dbc override IDs.
-- - EffectArg_1 36 = ITEM_MOD_HASTE_RATING.
-- - EffectArg_1 37 = ITEM_MOD_EXPERTISE_RATING.
-- - The all-stats/ratings enchant uses a WM-owned server spell; stock DBC supports percent stats and flat all-rating,
--   not percent rating scaling.

SET @wm_vellum_haste_52_enchant := 100520;
SET @wm_vellum_expertise_25_enchant := 100525;
SET @wm_vellum_all_stats_ratings_enchant := 100530;
SET @wm_vellum_all_stats_ratings_spell := 947950;

DELETE FROM spell_dbc
WHERE ID = @wm_vellum_all_stats_ratings_spell;

INSERT INTO spell_dbc
    (
        ID,
        Category,
        DispelType,
        Mechanic,
        Attributes,
        CastingTimeIndex,
        DurationIndex,
        PowerType,
        ManaCost,
        RangeIndex,
        EquippedItemClass,
        EquippedItemSubclass,
        EquippedItemInvTypes,
        Effect_1,
        Effect_2,
        Effect_3,
        EffectDieSides_1,
        EffectDieSides_2,
        EffectDieSides_3,
        EffectBasePoints_1,
        EffectBasePoints_2,
        EffectBasePoints_3,
        ImplicitTargetA_1,
        ImplicitTargetA_2,
        ImplicitTargetA_3,
        EffectAura_1,
        EffectAura_2,
        EffectAura_3,
        EffectMiscValue_1,
        EffectMiscValue_2,
        EffectMiscValue_3,
        SpellIconID,
        ActiveIconID,
        Name_Lang_enUS,
        Name_Lang_enGB,
        Name_Lang_Mask,
        Description_Lang_enUS,
        Description_Lang_enGB,
        Description_Lang_Mask,
        AuraDescription_Lang_enUS,
        AuraDescription_Lang_enGB,
        AuraDescription_Lang_Mask,
        DefenseType,
        PreventionType
    )
VALUES
    (
        @wm_vellum_all_stats_ratings_spell,
        0,
        0,
        0,
        128,
        1,
        0,
        0,
        0,
        1,
        -1,
        0,
        0,
        6,
        6,
        0,
        1,
        1,
        0,
        9,
        9,
        0,
        1,
        1,
        0,
        137,
        189,
        0,
        -1,
        -1,
        0,
        3783,
        0,
        'WM Vellum: All Stats and Ratings',
        'WM Vellum: All Stats and Ratings',
        3,
        'Increases all statistics by 10% and all ratings by 10.',
        'Increases all statistics by 10% and all ratings by 10.',
        3,
        'All statistics increased by 10%. All ratings increased by 10.',
        'All statistics increased by 10%. All ratings increased by 10.',
        3,
        0,
        0
    );

INSERT INTO wm_reserved_slot
    (EntityType, ReservedID, SlotStatus, ArcKey, CharacterGUID, SourceQuestID, NotesJSON)
VALUES
    ('spell', @wm_vellum_all_stats_ratings_spell, 'active', 'wm_content:spell:vellum-all-stats-ratings-aura', 5406, NULL, '["server_spell_dbc","random_enchant_vellum","all_stats_pct:10","all_ratings_flat:10"]')
ON DUPLICATE KEY UPDATE
    SlotStatus = VALUES(SlotStatus),
    ArcKey = VALUES(ArcKey),
    CharacterGUID = VALUES(CharacterGUID),
    SourceQuestID = VALUES(SourceQuestID),
    NotesJSON = VALUES(NotesJSON);

INSERT INTO spellitemenchantment_dbc
    (
        ID,
        Charges,
        Effect_1,
        Effect_2,
        Effect_3,
        EffectPointsMin_1,
        EffectPointsMin_2,
        EffectPointsMin_3,
        EffectPointsMax_1,
        EffectPointsMax_2,
        EffectPointsMax_3,
        EffectArg_1,
        EffectArg_2,
        EffectArg_3,
        Name_Lang_enUS,
        Name_Lang_enGB,
        Name_Lang_Mask,
        ItemVisual,
        Flags,
        Src_ItemID,
        Condition_Id,
        RequiredSkillID,
        RequiredSkillRank,
        MinLevel
    )
VALUES
    (@wm_vellum_haste_52_enchant, 0, 5, 0, 0, 52, 0, 0, 52, 0, 0, 36, 0, 0, '+52 Haste Rating', '+52 Haste Rating', 3, 0, 0, 0, 0, 0, 0, 0),
    (@wm_vellum_expertise_25_enchant, 0, 5, 0, 0, 25, 0, 0, 25, 0, 0, 37, 0, 0, '+25 Expertise Rating', '+25 Expertise Rating', 3, 0, 0, 0, 0, 0, 0, 0),
    (@wm_vellum_all_stats_ratings_enchant, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, @wm_vellum_all_stats_ratings_spell, 0, 0, '+10% All Stats / +10 Ratings', '+10% All Stats / +10 Ratings', 3, 0, 0, 0, 0, 0, 0, 0)
ON DUPLICATE KEY UPDATE
    Charges = VALUES(Charges),
    Effect_1 = VALUES(Effect_1),
    Effect_2 = VALUES(Effect_2),
    Effect_3 = VALUES(Effect_3),
    EffectPointsMin_1 = VALUES(EffectPointsMin_1),
    EffectPointsMin_2 = VALUES(EffectPointsMin_2),
    EffectPointsMin_3 = VALUES(EffectPointsMin_3),
    EffectPointsMax_1 = VALUES(EffectPointsMax_1),
    EffectPointsMax_2 = VALUES(EffectPointsMax_2),
    EffectPointsMax_3 = VALUES(EffectPointsMax_3),
    EffectArg_1 = VALUES(EffectArg_1),
    EffectArg_2 = VALUES(EffectArg_2),
    EffectArg_3 = VALUES(EffectArg_3),
    Name_Lang_enUS = VALUES(Name_Lang_enUS),
    Name_Lang_enGB = VALUES(Name_Lang_enGB),
    Name_Lang_Mask = VALUES(Name_Lang_Mask),
    ItemVisual = VALUES(ItemVisual),
    Flags = VALUES(Flags),
    Src_ItemID = VALUES(Src_ItemID),
    Condition_Id = VALUES(Condition_Id),
    RequiredSkillID = VALUES(RequiredSkillID),
    RequiredSkillRank = VALUES(RequiredSkillRank),
    MinLevel = VALUES(MinLevel);

DELETE FROM item_enchantment_random_tiers
WHERE enchantID IN (
    @wm_vellum_haste_52_enchant,
    @wm_vellum_expertise_25_enchant,
    @wm_vellum_all_stats_ratings_enchant,
    3827,
    3239,
    3789
);

INSERT INTO item_enchantment_random_tiers
    (enchantID, tier, class, exclusiveSubClass)
VALUES
    (@wm_vellum_haste_52_enchant, 5, 'ANY', NULL),
    (@wm_vellum_expertise_25_enchant, 5, 'ANY', NULL),
    (@wm_vellum_all_stats_ratings_enchant, 5, 'ANY', NULL),
    (3827, 5, 'WEAPON', NULL), -- Massacre / +110 Attack Power.
    (3239, 5, 'WEAPON', NULL), -- Icebreaker.
    (3789, 5, 'WEAPON', NULL); -- Berserking.
