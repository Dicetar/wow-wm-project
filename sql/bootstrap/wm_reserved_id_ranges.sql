CREATE TABLE IF NOT EXISTS wm_reserved_id_range (
    EntityType VARCHAR(64) NOT NULL PRIMARY KEY,
    RangeStart INT NOT NULL,
    RangeEnd INT NOT NULL,
    Purpose TEXT NOT NULL,
    NotesJSON LONGTEXT NULL,
    UpdatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

REPLACE INTO wm_reserved_id_range (EntityType, RangeStart, RangeEnd, Purpose, NotesJSON) VALUES
('quest_template', 910000, 910999, 'WM private quest arcs, branch quests, and follow-up quests', '["Pre-seed dummy quest rows here later."]'),
('item_template', 911000, 911999, 'WM private reward items, equipped-gate items, and item prototypes', '["Use for private items granted through GM commands."]'),
('spell_slots', 900000, 900999, 'WM private spell reward slots, wrapper spells, and alternate ability variants', '["Do not attach to class trainers or global skillline flows."]'),
('gossip_menu', 912000, 912499, 'WM-authored conversation nodes and branching menus', '["Supports branch-choice driven arcs."]'),
('npc_text', 912500, 912999, 'WM-authored dialogue text blocks', '["Supports narrative text and private quest dialogue."]');
