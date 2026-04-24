-- Lab-only cleanup for Jecia's legacy summon prototype state.
-- Scope is intentionally narrow:
-- - player GUID 5406 only
-- - retired legacy carrier spell IDs only
--
-- Stock Summon Voidwalker (697) is intentionally preserved. Bonebound Alpha now
-- lives on WM shell 940001, so cleanup must not strip the real warlock summon.

SET @wm_player_guid := 5406;

DROP TEMPORARY TABLE IF EXISTS wm_legacy_pet_ids;
CREATE TEMPORARY TABLE wm_legacy_pet_ids (
    id INT UNSIGNED NOT NULL PRIMARY KEY
);

INSERT INTO wm_legacy_pet_ids (id)
SELECT id
FROM character_pet
WHERE owner = @wm_player_guid
  AND CreatedBySpell IN (8853, 57913, 49126);

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
  AND spell IN (8853, 57913, 49126);

INSERT IGNORE INTO character_spell (guid, spell, specMask)
VALUES (@wm_player_guid, 697, 255);

UPDATE character_pet
SET entry = 920100,
    name = 'Bonebound Alpha'
WHERE owner = @wm_player_guid
  AND CreatedBySpell = 940001
  AND entry = 1860;

SELECT 'legacy_pet_rows_remaining' AS metric, COUNT(*) AS value
FROM character_pet
WHERE owner = @wm_player_guid
  AND CreatedBySpell IN (8853, 57913, 49126);

SELECT 'legacy_spell_rows_remaining' AS metric, COUNT(*) AS value
FROM character_spell
WHERE guid = @wm_player_guid
  AND spell IN (8853, 57913, 49126);

SELECT 'summon_voidwalker_spell_present' AS metric, COUNT(*) AS value
FROM character_spell
WHERE guid = @wm_player_guid
  AND spell = 697;

SELECT 'bonebound_alpha_shell_spell_present' AS metric, COUNT(*) AS value
FROM character_spell
WHERE guid = @wm_player_guid
  AND spell = 940001;

SELECT 'bonebound_alpha_rows_on_voidwalker_entry' AS metric, COUNT(*) AS value
FROM character_pet
WHERE owner = @wm_player_guid
  AND CreatedBySpell = 940001
  AND entry = 1860;
