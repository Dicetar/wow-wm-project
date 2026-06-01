CREATE TABLE IF NOT EXISTS wm_bridge_player_presence (
    PlayerGUID INT NOT NULL PRIMARY KEY,
    AccountID INT NULL,
    Online TINYINT(1) NOT NULL DEFAULT 0,
    MapID INT NULL,
    ZoneID INT NULL,
    AreaID INT NULL,
    ZoneName VARCHAR(128) NULL,
    AreaName VARCHAR(128) NULL,
    PosX FLOAT NULL,
    PosY FLOAT NULL,
    PosZ FLOAT NULL,
    Orientation FLOAT NULL,
    Level INT NULL,
    HealthPct INT NULL,
    InCombat TINYINT(1) NOT NULL DEFAULT 0,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_wm_bridge_player_presence_online (Online, UpdatedAt)
);
