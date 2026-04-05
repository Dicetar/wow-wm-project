UPDATE wm_reserved_slot
SET SlotStatus = 'free', ArcKey = NULL, CharacterGUID = NULL, SourceQuestID = NULL, NotesJSON = NULL
WHERE EntityType = 'spell_dbc_or_spell_slots' AND ReservedID = 900000;
