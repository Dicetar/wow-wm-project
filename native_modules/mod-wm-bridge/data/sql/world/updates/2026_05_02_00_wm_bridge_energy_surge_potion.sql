-- WM Energy Surge Potion.
-- Server truth: item 910014 is a scoped right-click potion. Native ItemScript
-- applies visible WM aura 946606 and the PlayerScript restores +10 energy/sec
-- only while that aura is present.
-- Client/server DBC truth for aura 946606 is generated from
-- control/runtime/spell_shell_bank.json.

SET @wm_energy_surge_potion_item_entry := 910014;
SET @wm_energy_surge_aura_spell_id := 946606;
SET @wm_energy_surge_base_item_entry := 33448; -- Runic Mana Potion, used for a known-good potion row/appearance.

DROP TEMPORARY TABLE IF EXISTS wm_tmp_energy_surge_potion;
CREATE TEMPORARY TABLE wm_tmp_energy_surge_potion LIKE item_template;

INSERT INTO wm_tmp_energy_surge_potion
SELECT *
FROM item_template
WHERE entry = @wm_energy_surge_base_item_entry
LIMIT 1;

UPDATE wm_tmp_energy_surge_potion
SET
    entry = @wm_energy_surge_potion_item_entry,
    class = 0,
    subclass = 1,
    name = 'Energy Surge Potion',
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
    spellid_1 = 8096,
    spelltrigger_1 = 0,
    spellcharges_1 = -1,
    spellppmRate_1 = 0,
    spellcooldown_1 = 60000,
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
    bonding = 1,
    description = 'Drink to gain Energy Surge for 2 hours, restoring 10 additional energy every second while the buff remains active.',
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
    ScriptName = 'wm_energy_surge_potion',
    DisenchantID = 0,
    FoodType = 0,
    minMoneyLoot = 0,
    maxMoneyLoot = 0,
    flagsCustom = 0,
    VerifiedBuild = 0;

DELETE FROM item_template WHERE entry = @wm_energy_surge_potion_item_entry;
INSERT INTO item_template
SELECT *
FROM wm_tmp_energy_surge_potion;

DROP TEMPORARY TABLE IF EXISTS wm_tmp_energy_surge_potion;

INSERT INTO wm_reserved_slot
    (EntityType, ReservedID, SlotStatus, ArcKey, CharacterGUID, SourceQuestID, NotesJSON)
VALUES
    ('item', @wm_energy_surge_potion_item_entry, 'active', 'wm_content:item:energy-surge-potion', 5406, NULL, '["wm_energy_surge_potion","base_item_entry:33448","native_script:wm_energy_surge_potion","visible_aura:946606","energy_per_second:10","duration_ms:7200000"]'),
    ('spell', @wm_energy_surge_aura_spell_id, 'active', 'wm_content:spell:energy-surge-potion-aura', 5406, NULL, '["shell_spell","energy_surge_potion_v1","visible_aura","energy_per_second:10","duration_ms:7200000"]')
ON DUPLICATE KEY UPDATE
    SlotStatus = VALUES(SlotStatus),
    ArcKey = VALUES(ArcKey),
    CharacterGUID = VALUES(CharacterGUID),
    SourceQuestID = VALUES(SourceQuestID),
    NotesJSON = VALUES(NotesJSON);
