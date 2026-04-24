CREATE TABLE IF NOT EXISTS wm_reserved_id_range (
    EntityType VARCHAR(64) NOT NULL PRIMARY KEY,
    RangeStart INT NOT NULL,
    RangeEnd INT NOT NULL,
    Purpose TEXT NOT NULL,
    NotesJSON LONGTEXT NULL,
    UpdatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

REPLACE INTO wm_reserved_id_range (EntityType, RangeStart, RangeEnd, Purpose, NotesJSON) VALUES
('quest', 910000, 910999, 'WM private quest arcs, branch quests, follow-up quests, and repeatable bounty slots', '["Exact quest claims live in data/specs/custom_id_registry.json."]'),
('item', 910000, 910999, 'WM private reward items, equipped-gate items, and item prototypes', '["Exact item claims live in data/specs/custom_id_registry.json."]'),
('spell', 947000, 947999, 'WM managed spell publish and rollback slots', '["Shell-bank ids are tracked separately in data/specs/custom_id_registry.json."]'),
('gossip_menu', 912000, 912499, 'WM-authored conversation nodes and branching menus', '["Supports branch-choice driven arcs."]'),
('npc_text', 912500, 912999, 'WM-authored dialogue text blocks', '["Supports narrative text and private quest dialogue."]');
