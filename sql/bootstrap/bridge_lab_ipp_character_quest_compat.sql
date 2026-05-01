-- BridgeLab compatibility shim for mod-individual-progression.
--
-- The module still queries the retired `character_quest` table for rewarded
-- hidden progression quests. Current AzerothCore stores rewarded quests in
-- `character_queststatus_rewarded`, so expose the old read-only shape without
-- changing core quest state.

SET @wm_character_quest_object_type := (
    SELECT TABLE_TYPE
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'character_quest'
    LIMIT 1
);

SET @wm_character_quest_sql := IF(
    @wm_character_quest_object_type = 'BASE TABLE',
    'SELECT ''character_quest base table already exists'' AS bridge_lab_ipp_compat',
    'CREATE OR REPLACE SQL SECURITY INVOKER VIEW `character_quest` AS
        SELECT
            `guid`,
            `quest`,
            CAST(6 AS UNSIGNED) AS `status`
        FROM `character_queststatus_rewarded`'
);

PREPARE wm_character_quest_stmt FROM @wm_character_quest_sql;
EXECUTE wm_character_quest_stmt;
DEALLOCATE PREPARE wm_character_quest_stmt;
