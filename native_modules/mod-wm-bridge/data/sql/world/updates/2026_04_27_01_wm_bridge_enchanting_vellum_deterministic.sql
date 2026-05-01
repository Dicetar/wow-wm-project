-- WM Enchanting Vellum deterministic choice mode.
-- Runtime script owns application; this update only refreshes item text and slot notes for existing labs.

UPDATE item_template
SET
    stackable = 999,
    description = 'Right-click to choose an equipped weapon or armor item, then choose one enchant slot. Random reroll costs 1 vellum with tier chance 40% tier 3, 30% tier 4, 30% tier 5. Deterministic choice costs 5/12/20 vellums for tier 3/4/5.',
    ScriptName = 'wm_random_enchant_consumable'
WHERE entry = 910008;

INSERT INTO wm_reserved_slot
    (EntityType, ReservedID, SlotStatus, ArcKey, CharacterGUID, SourceQuestID, NotesJSON)
VALUES
    ('item', 910008, 'active', 'wm_content:item:enchanting-vellum', 5406, NULL, '["wm_random_enchant_consumable","base_item_entry:955","single_slot","tier_roll:3=40,4=30,5=30","deterministic_costs:t3=5,t4=12,t5=20","deterministic_categories:stats,damage,ratings,defense,resistances,utility,other"]')
ON DUPLICATE KEY UPDATE
    SlotStatus = VALUES(SlotStatus),
    ArcKey = VALUES(ArcKey),
    CharacterGUID = VALUES(CharacterGUID),
    SourceQuestID = VALUES(SourceQuestID),
    NotesJSON = VALUES(NotesJSON);
