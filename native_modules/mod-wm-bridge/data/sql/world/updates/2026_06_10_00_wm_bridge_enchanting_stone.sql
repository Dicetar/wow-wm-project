-- WM Enchanting Stone.
-- Server truth: item 910015 is a right-click consumable whose ItemScript opens
-- the WMBridge addon upgrade slot. Successful upgrades multiply gear stats by
-- 2^upgrade level; the item is consumed on every attempt.

SET @wm_enchanting_stone_item_entry := 910015;
SET @wm_enchanting_stone_base_item_entry := 34057; -- Abyss Crystal, used for a known-good shard/crystal row.

DROP TEMPORARY TABLE IF EXISTS wm_tmp_enchanting_stone;
CREATE TEMPORARY TABLE wm_tmp_enchanting_stone LIKE item_template;

INSERT INTO wm_tmp_enchanting_stone
SELECT *
FROM item_template
WHERE entry = @wm_enchanting_stone_base_item_entry
LIMIT 1;

UPDATE wm_tmp_enchanting_stone
SET
    entry = @wm_enchanting_stone_item_entry,
    class = 0,
    subclass = 4,
    name = 'Enchanting Stone',
    displayid = 56465,
    Quality = 3,
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
    spellid_1 = 8096,
    spelltrigger_1 = 0,
    spellcharges_1 = -1,
    spellppmRate_1 = 0,
    spellcooldown_1 = -1,
    spellcategory_1 = 0,
    spellcategorycooldown_1 = -1,
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
    bonding = 0,
    description = 'Right-click to open an upgrade slot. Drop a weapon or armor item into the slot and press Upgrade. The stone is consumed on each attempt.',
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
    ScriptName = 'wm_enchanting_stone',
    DisenchantID = 0,
    FoodType = 0,
    minMoneyLoot = 0,
    maxMoneyLoot = 0,
    flagsCustom = 0,
    VerifiedBuild = 0;

DELETE FROM item_template WHERE entry = @wm_enchanting_stone_item_entry;
INSERT INTO item_template
SELECT *
FROM wm_tmp_enchanting_stone;

DROP TEMPORARY TABLE IF EXISTS wm_tmp_enchanting_stone;

DELETE FROM creature_loot_template
WHERE Item = @wm_enchanting_stone_item_entry;

INSERT INTO creature_loot_template
    (Entry, Item, Reference, Chance, QuestRequired, LootMode, GroupId, MinCount, MaxCount, Comment)
SELECT
    boss.lootid,
    @wm_enchanting_stone_item_entry,
    0,
    CASE WHEN boss.is_final_boss = 1 THEN 100 ELSE 35 END,
    0,
    1,
    0,
    1,
    1,
    CONCAT(boss.boss_name, ' - WM Enchanting Stone')
FROM (
    SELECT
        ct.lootid,
        MIN(ct.name) AS boss_name,
        MAX(CASE WHEN ie.lastEncounterDungeon > 0 THEN 1 ELSE 0 END) AS is_final_boss
    FROM instance_encounters ie
    INNER JOIN creature_template ct ON ct.entry = ie.creditEntry
    WHERE ie.creditType = 0
        AND ct.lootid > 0
    GROUP BY ct.lootid
) boss;

INSERT INTO wm_reserved_slot
    (EntityType, ReservedID, SlotStatus, ArcKey, CharacterGUID, SourceQuestID, NotesJSON)
VALUES
    ('item', @wm_enchanting_stone_item_entry, 'active', 'wm_content:item:enchanting-stone', NULL, NULL, '["wm_enchanting_stone","base_item_entry:34057","native_script:wm_enchanting_stone","addon_gui:slot_upgrade_cancel","max_upgrade:+8","stat_multiplier:2^level","boss_drop:35","final_boss_drop:100","global_all_characters","bind:none"]')
ON DUPLICATE KEY UPDATE
    SlotStatus = VALUES(SlotStatus),
    ArcKey = VALUES(ArcKey),
    CharacterGUID = VALUES(CharacterGUID),
    SourceQuestID = VALUES(SourceQuestID),
    NotesJSON = VALUES(NotesJSON);
