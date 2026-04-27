-- WM Bone Lure Obelisk consumable.
-- Server truth: item 910009 is a scoped right-click throwable that deploys
-- creature 920102. Native ItemScript/CreatureScript own taunt pulses, damage
-- reduction, status immunity, duration, and release behavior.

SET @wm_bone_lure_item_entry := 910009;
SET @wm_bone_lure_creature_entry := 920102;
SET @wm_bone_lure_base_item_entry := 41119; -- Saronite Bomb, used for ground-target client UX.
SET @wm_bone_lure_base_creature_entry := 3579; -- Stoneclaw Totem, attackable totem chassis.
SET @wm_bone_lure_display_id := 16135; -- Necrotic Shard, visible obelisk-like model.

DROP TEMPORARY TABLE IF EXISTS wm_tmp_bone_lure_item;
CREATE TEMPORARY TABLE wm_tmp_bone_lure_item LIKE item_template;

INSERT INTO wm_tmp_bone_lure_item
SELECT *
FROM item_template
WHERE entry = @wm_bone_lure_base_item_entry
LIMIT 1;

UPDATE wm_tmp_bone_lure_item
SET
    entry = @wm_bone_lure_item_entry,
    class = 0,
    subclass = 0,
    name = 'Bone Lure Charm',
    displayid = 52864,
    Quality = 2,
    Flags = 0,
    FlagsExtra = 0,
    BuyCount = 1,
    BuyPrice = 0,
    SellPrice = 0,
    InventoryType = 0,
    AllowableClass = -1,
    AllowableRace = -1,
    ItemLevel = 20,
    RequiredLevel = 1,
    RequiredSkill = 0,
    RequiredSkillRank = 0,
    requiredspell = 0,
    requiredhonorrank = 0,
    RequiredCityRank = 0,
    RequiredReputationFaction = 0,
    RequiredReputationRank = 0,
    maxcount = 0,
    stackable = 20,
    ContainerSlots = 0,
    stat_type1 = 0,
    stat_value1 = 0,
    stat_type2 = 0,
    stat_value2 = 0,
    stat_type3 = 0,
    stat_value3 = 0,
    stat_type4 = 0,
    stat_value4 = 0,
    stat_type5 = 0,
    stat_value5 = 0,
    stat_type6 = 0,
    stat_value6 = 0,
    stat_type7 = 0,
    stat_value7 = 0,
    stat_type8 = 0,
    stat_value8 = 0,
    stat_type9 = 0,
    stat_value9 = 0,
    stat_type10 = 0,
    stat_value10 = 0,
    ScalingStatDistribution = 0,
    ScalingStatValue = 0,
    dmg_min1 = 0,
    dmg_max1 = 0,
    dmg_type1 = 0,
    dmg_min2 = 0,
    dmg_max2 = 0,
    dmg_type2 = 0,
    armor = 0,
    holy_res = 0,
    fire_res = 0,
    nature_res = 0,
    frost_res = 0,
    shadow_res = 0,
    arcane_res = 0,
    delay = 1000,
    ammo_type = 0,
    RangedModRange = 0,
    spellid_1 = 56350,
    spelltrigger_1 = 0,
    spellcharges_1 = -1,
    spellppmRate_1 = 0,
    spellcooldown_1 = 1000,
    spellcategory_1 = 24,
    spellcategorycooldown_1 = 60000,
    spellid_2 = 0,
    spelltrigger_2 = 0,
    spellcharges_2 = 0,
    spellppmRate_2 = 0,
    spellcooldown_2 = -1,
    spellcategory_2 = 0,
    spellcategorycooldown_2 = -1,
    spellid_3 = 0,
    spelltrigger_3 = 0,
    spellcharges_3 = 0,
    spellppmRate_3 = 0,
    spellcooldown_3 = -1,
    spellcategory_3 = 0,
    spellcategorycooldown_3 = -1,
    spellid_4 = 0,
    spelltrigger_4 = 0,
    spellcharges_4 = 0,
    spellppmRate_4 = 0,
    spellcooldown_4 = -1,
    spellcategory_4 = 0,
    spellcategorycooldown_4 = -1,
    spellid_5 = 0,
    spelltrigger_5 = 0,
    spellcharges_5 = 0,
    spellppmRate_5 = 0,
    spellcooldown_5 = -1,
    spellcategory_5 = 0,
    spellcategorycooldown_5 = -1,
    bonding = 1,
    description = 'Throw to deploy a Bone Lure Obelisk for 30 sec. It repeatedly taunts non-boss enemies within 200 yards, has your maximum health, and takes 75% reduced damage.',
    PageText = 0,
    LanguageID = 0,
    PageMaterial = 0,
    startquest = 0,
    lockid = 0,
    RandomProperty = 0,
    RandomSuffix = 0,
    block = 0,
    itemset = 0,
    MaxDurability = 0,
    area = 0,
    Map = 0,
    BagFamily = 0,
    TotemCategory = 0,
    socketColor_1 = 0,
    socketContent_1 = 0,
    socketColor_2 = 0,
    socketContent_2 = 0,
    socketColor_3 = 0,
    socketContent_3 = 0,
    socketBonus = 0,
    GemProperties = 0,
    RequiredDisenchantSkill = -1,
    ArmorDamageModifier = 0,
    duration = 0,
    ItemLimitCategory = 0,
    HolidayId = 0,
    ScriptName = 'wm_bone_lure_charm',
    DisenchantID = 0,
    FoodType = 0,
    minMoneyLoot = 0,
    maxMoneyLoot = 0,
    flagsCustom = 0,
    VerifiedBuild = 0;

DELETE FROM item_template WHERE entry = @wm_bone_lure_item_entry;
INSERT INTO item_template
SELECT *
FROM wm_tmp_bone_lure_item;

DROP TEMPORARY TABLE IF EXISTS wm_tmp_bone_lure_item;

DELETE FROM creature_template_model WHERE CreatureID = @wm_bone_lure_creature_entry;
DELETE FROM creature_template_addon WHERE entry = @wm_bone_lure_creature_entry;
DELETE FROM creature_template_movement WHERE CreatureId = @wm_bone_lure_creature_entry;
DELETE FROM creature_template_resistance WHERE CreatureID = @wm_bone_lure_creature_entry;
DELETE FROM creature_template_spell WHERE CreatureID = @wm_bone_lure_creature_entry;
DELETE FROM creature_template WHERE entry = @wm_bone_lure_creature_entry;

DROP TEMPORARY TABLE IF EXISTS wm_tmp_bone_lure_creature;
CREATE TEMPORARY TABLE wm_tmp_bone_lure_creature AS
SELECT *
FROM creature_template
WHERE entry = @wm_bone_lure_base_creature_entry;

UPDATE wm_tmp_bone_lure_creature
SET
    entry = @wm_bone_lure_creature_entry,
    name = 'Bone Lure Obelisk',
    subname = 'WM Lure',
    minlevel = 1,
    maxlevel = 80,
    faction = 58,
    npcflag = 0,
    speed_walk = 1.0,
    speed_run = 1.0,
    detection_range = 1,
    `rank` = 0,
    DamageModifier = 0,
    BaseAttackTime = 2000,
    RangeAttackTime = 2000,
    unit_flags = 0,
    unit_flags2 = 2048,
    dynamicflags = 0,
    family = 0,
    type = 11,
    type_flags = 0,
    lootid = 0,
    pickpocketloot = 0,
    skinloot = 0,
    PetSpellDataId = 0,
    mingold = 0,
    maxgold = 0,
    AIName = '',
    MovementType = 0,
    HealthModifier = 1,
    ManaModifier = 0,
    ArmorModifier = 1,
    ExperienceModifier = 0,
    RacialLeader = 0,
    movementId = 0,
    RegenHealth = 0,
    CreatureImmunitiesId = 0,
    flags_extra = 100925504,
    ScriptName = 'wm_bone_lure_obelisk',
    VerifiedBuild = NULL;

INSERT INTO creature_template
SELECT *
FROM wm_tmp_bone_lure_creature;

DROP TEMPORARY TABLE IF EXISTS wm_tmp_bone_lure_creature;

INSERT INTO creature_template_model (CreatureID, Idx, CreatureDisplayID, DisplayScale, Probability, VerifiedBuild)
VALUES (@wm_bone_lure_creature_entry, 0, @wm_bone_lure_display_id, 1, 1, NULL);

INSERT INTO creature_template_movement (CreatureId, Ground, Swim, Flight, Rooted, Chase, Random, InteractionPauseTimer)
VALUES (@wm_bone_lure_creature_entry, 1, 1, 0, 1, 0, 0, 0);

INSERT INTO wm_reserved_slot
    (EntityType, ReservedID, SlotStatus, ArcKey, CharacterGUID, SourceQuestID, NotesJSON)
VALUES
    ('item', @wm_bone_lure_item_entry, 'active', 'wm_content:item:bone-lure-charm', 5406, NULL, '["wm_bone_lure_charm","base_item_entry:41119","native_script:wm_bone_lure_charm","deploys_creature:920102"]'),
    ('creature_template', @wm_bone_lure_creature_entry, 'active', 'wm_content:creature:bone-lure-obelisk', 5406, NULL, '["wm_bone_lure_obelisk","base_creature_entry:3579","display_id:16135","native_script:wm_bone_lure_obelisk"]')
ON DUPLICATE KEY UPDATE
    SlotStatus = VALUES(SlotStatus),
    ArcKey = VALUES(ArcKey),
    CharacterGUID = VALUES(CharacterGUID),
    SourceQuestID = VALUES(SourceQuestID),
    NotesJSON = VALUES(NotesJSON);
