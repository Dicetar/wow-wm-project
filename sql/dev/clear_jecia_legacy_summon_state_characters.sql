-- Lab-only cleanup for Jecia's legacy summon prototype state.
-- Scope is intentionally narrow:
-- - player GUID 5406 only
-- - legacy stock carrier spell IDs only

SET @wm_player_guid := 5406;

DROP TEMPORARY TABLE IF EXISTS wm_legacy_pet_ids;
CREATE TEMPORARY TABLE wm_legacy_pet_ids (
    id INT UNSIGNED NOT NULL PRIMARY KEY
);

INSERT INTO wm_legacy_pet_ids (id)
SELECT id
FROM character_pet
WHERE owner = @wm_player_guid
  AND CreatedBySpell IN (697, 8853, 57913, 49126);

DELETE FROM pet_aura
WHERE guid IN (SELECT id FROM wm_legacy_pet_ids);

DELETE FROM pet_spell
WHERE guid IN (SELECT id FROM wm_legacy_pet_ids);

DELETE FROM pet_spell_cooldown
WHERE guid IN (SELECT id FROM wm_legacy_pet_ids);

DELETE FROM character_pet
WHERE id IN (SELECT id FROM wm_legacy_pet_ids);

DELETE FROM character_spell
WHERE guid = @wm_player_guid
  AND spell IN (697, 8853, 57913, 49126);

SELECT 'legacy_pet_rows_remaining' AS metric, COUNT(*) AS value
FROM character_pet
WHERE owner = @wm_player_guid
  AND CreatedBySpell IN (697, 8853, 57913, 49126);

SELECT 'legacy_spell_rows_remaining' AS metric, COUNT(*) AS value
FROM character_spell
WHERE guid = @wm_player_guid
  AND spell IN (697, 8853, 57913, 49126);
