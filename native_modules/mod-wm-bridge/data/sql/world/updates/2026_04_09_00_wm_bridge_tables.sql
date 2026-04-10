CREATE TABLE IF NOT EXISTS wm_bridge_event (
    BridgeEventID BIGINT AUTO_INCREMENT PRIMARY KEY,
    OccurredAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    EventFamily VARCHAR(32) NOT NULL,
    EventType VARCHAR(64) NOT NULL,
    Source VARCHAR(64) NOT NULL DEFAULT 'native_bridge',
    PlayerGUID INT NULL,
    AccountID INT NULL,
    SubjectType VARCHAR(32) NULL,
    SubjectGUID VARCHAR(128) NULL,
    SubjectEntry INT NULL,
    ObjectType VARCHAR(32) NULL,
    ObjectGUID VARCHAR(128) NULL,
    ObjectEntry INT NULL,
    MapID INT NULL,
    ZoneID INT NULL,
    AreaID INT NULL,
    PayloadJSON LONGTEXT NULL,
    KEY idx_wm_bridge_event_family_type (EventFamily, EventType),
    KEY idx_wm_bridge_event_player (PlayerGUID, BridgeEventID),
    KEY idx_wm_bridge_event_occurred (OccurredAt)
);

CREATE TABLE IF NOT EXISTS wm_bridge_context_request (
    RequestID BIGINT AUTO_INCREMENT PRIMARY KEY,
    RequestedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PlayerGUID INT NOT NULL,
    ContextKind VARCHAR(64) NOT NULL,
    Radius INT NOT NULL DEFAULT 40,
    Status VARCHAR(32) NOT NULL DEFAULT 'pending',
    RequestedBy VARCHAR(64) NULL,
    MetadataJSON LONGTEXT NULL,
    ProcessedAt TIMESTAMP NULL DEFAULT NULL,
    KEY idx_wm_bridge_context_request_status (Status, RequestedAt),
    KEY idx_wm_bridge_context_request_player (PlayerGUID, RequestedAt)
);

CREATE TABLE IF NOT EXISTS wm_bridge_context_snapshot (
    SnapshotID BIGINT AUTO_INCREMENT PRIMARY KEY,
    RequestID BIGINT NULL,
    OccurredAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PlayerGUID INT NOT NULL,
    ContextKind VARCHAR(64) NOT NULL,
    Radius INT NOT NULL DEFAULT 40,
    MapID INT NULL,
    ZoneID INT NULL,
    AreaID INT NULL,
    Source VARCHAR(64) NOT NULL DEFAULT 'native_bridge',
    PayloadJSON LONGTEXT NOT NULL,
    KEY idx_wm_bridge_context_snapshot_player (PlayerGUID, OccurredAt),
    KEY idx_wm_bridge_context_snapshot_request (RequestID)
);
