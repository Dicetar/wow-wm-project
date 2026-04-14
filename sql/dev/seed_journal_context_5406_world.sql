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
    '["murloc", "shoreline", "scavenger", "hostile", "journal_fixture"]',
    1
) ON DUPLICATE KEY UPDATE
    JournalName = VALUES(JournalName),
    Archetype = VALUES(Archetype),
    Species = VALUES(Species),
    Occupation = VALUES(Occupation),
    HomeArea = VALUES(HomeArea),
    ShortDescription = VALUES(ShortDescription),
    TagsJSON = VALUES(TagsJSON),
    IsActive = VALUES(IsActive);

INSERT INTO wm_subject_enrichment (
    SubjectType,
    EntryID,
    Species,
    Profession,
    RoleLabel,
    HomeArea,
    ShortDescription,
    TagsJSON
) VALUES (
    'creature',
    46,
    'murloc',
    'forager',
    'shoreline raider',
    'Elwynn coastline',
    'A small murloc known to harass the road and shoreline around the eastern forest.',
    '["murloc", "elwynn", "shoreline", "reactive_test", "journal_fixture"]'
) ON DUPLICATE KEY UPDATE
    Species = VALUES(Species),
    Profession = VALUES(Profession),
    RoleLabel = VALUES(RoleLabel),
    HomeArea = VALUES(HomeArea),
    ShortDescription = VALUES(ShortDescription),
    TagsJSON = VALUES(TagsJSON);

DELETE FROM wm_player_subject_event
WHERE PlayerGUID = 5406
  AND SubjectID IN (
    SELECT SubjectID
    FROM wm_subject_definition
    WHERE SubjectType = 'creature'
      AND CreatureEntry = 46
  );

DELETE FROM wm_player_subject_journal
WHERE PlayerGUID = 5406
  AND SubjectID IN (
    SELECT SubjectID
    FROM wm_subject_definition
    WHERE SubjectType = 'creature'
      AND CreatureEntry = 46
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
    5406,
    SubjectID,
    5,
    0,
    0,
    1,
    1,
    'Murloc Trouble',
    '["Seeded lab journal fixture for context-pack proof."]'
FROM wm_subject_definition
WHERE SubjectType = 'creature'
  AND CreatureEntry = 46;

INSERT INTO wm_player_subject_event (
    PlayerGUID,
    SubjectID,
    EventType,
    EventValue
)
SELECT 5406, SubjectID, 'note', 'Jecia found repeated murloc movement near the road.'
FROM wm_subject_definition
WHERE SubjectType = 'creature'
  AND CreatureEntry = 46;

INSERT INTO wm_player_subject_event (
    PlayerGUID,
    SubjectID,
    EventType,
    EventValue
)
SELECT 5406, SubjectID, 'quest_completed', 'Murloc Trouble'
FROM wm_subject_definition
WHERE SubjectType = 'creature'
  AND CreatureEntry = 46;

INSERT INTO wm_event_log (
    EventClass,
    EventType,
    Source,
    SourceEventKey,
    OccurredAt,
    PlayerGUID,
    SubjectType,
    SubjectEntry,
    MapID,
    ZoneID,
    AreaID,
    EventValue,
    MetadataJSON
) VALUES (
    'observed',
    'kill',
    'dev_seed',
    'journal-context-5406-46-kill-1',
    '2026-04-14 00:00:00',
    5406,
    'creature',
    46,
    NULL,
    NULL,
    NULL,
    '1',
    '{"fixture":"journal_context_5406","purpose":"context_pack_event_smoke"}'
) ON DUPLICATE KEY UPDATE
    EventClass = VALUES(EventClass),
    EventType = VALUES(EventType),
    OccurredAt = VALUES(OccurredAt),
    PlayerGUID = VALUES(PlayerGUID),
    SubjectType = VALUES(SubjectType),
    SubjectEntry = VALUES(SubjectEntry),
    EventValue = VALUES(EventValue),
    MetadataJSON = VALUES(MetadataJSON);
