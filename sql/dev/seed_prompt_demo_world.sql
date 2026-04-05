DELETE FROM wm_player_subject_event WHERE PlayerGUID = 42 AND SubjectID IN (
    SELECT SubjectID FROM wm_subject_definition WHERE SubjectType = 'creature' AND CreatureEntry = 46
);

DELETE FROM wm_player_subject_journal WHERE PlayerGUID = 42 AND SubjectID IN (
    SELECT SubjectID FROM wm_subject_definition WHERE SubjectType = 'creature' AND CreatureEntry = 46
);

DELETE FROM wm_subject_definition WHERE SubjectType = 'creature' AND CreatureEntry = 46;

INSERT INTO wm_subject_definition (
    SubjectType,
    CreatureEntry,
    JournalName,
    Archetype,
    Species,
    Occupation,
    HomeArea,
    ShortDescription,
    TagsJSON,
    IsActive
) VALUES (
    'creature',
    46,
    'Murloc Forager',
    'creature',
    'murloc',
    'forager',
    'Elwynn coastline',
    'Shabby shoreline scavenger with a nervous, territorial streak.',
    '["murloc", "shoreline", "scavenger", "hostile"]',
    1
);

INSERT INTO wm_player_subject_journal (
    PlayerGUID,
    SubjectID,
    KillCount,
    SkinCount,
    FeedCount,
    TalkCount,
    QuestCompleteCount,
    LastQuestTitle,
    NotesJSON
)
SELECT
    42,
    SubjectID,
    7,
    0,
    1,
    0,
    1,
    'A Curious Offering',
    '["The player has begun experimenting with non-violent contact."]'
FROM wm_subject_definition
WHERE SubjectType = 'creature' AND CreatureEntry = 46;

INSERT INTO wm_player_subject_event (
    PlayerGUID,
    SubjectID,
    EventType,
    EventValue
)
SELECT 42, SubjectID, 'feed_trigger_quest', 'A Curious Offering'
FROM wm_subject_definition
WHERE SubjectType = 'creature' AND CreatureEntry = 46;

INSERT INTO wm_player_subject_event (
    PlayerGUID,
    SubjectID,
    EventType,
    EventValue
)
SELECT 42, SubjectID, 'note', 'The murloc did not attack immediately after the offering.'
FROM wm_subject_definition
WHERE SubjectType = 'creature' AND CreatureEntry = 46;
