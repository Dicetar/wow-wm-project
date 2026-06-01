CREATE TABLE IF NOT EXISTS wm_bridge_player_perception (
    PlayerGUID INT NOT NULL PRIMARY KEY,
    MapID INT NULL,
    ZoneID INT NULL,
    AreaID INT NULL,
    CreatureCount INT NOT NULL DEFAULT 0,
    GameObjectCount INT NOT NULL DEFAULT 0,
    PayloadJSON LONGTEXT NULL,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_wm_bridge_player_perception_updated (UpdatedAt)
);
