UPDATE wm_reserved_slot
SET SlotStatus = 'free', ArcKey = NULL, CharacterGUID = NULL, SourceQuestID = NULL, NotesJSON = NULL
WHERE EntityType = 'spell' AND ReservedID = 947000;
