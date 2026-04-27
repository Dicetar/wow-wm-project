-- Keep Echo Restorer template movement speed aligned with Echo Destroyer.
-- Runtime also enforces movement rates after stat recalculation, but this keeps fresh template truth sane.

SET @wm_alpha_echo_creature_entry := 920101;
SET @wm_priest_echo_creature_entry := 920103;

UPDATE creature_template restorer
JOIN creature_template destroyer ON destroyer.entry = @wm_alpha_echo_creature_entry
SET
    restorer.speed_walk = destroyer.speed_walk,
    restorer.speed_run = destroyer.speed_run
WHERE restorer.entry = @wm_priest_echo_creature_entry;

SELECT
    'bonebound_restorer_speed_match' AS metric,
    destroyer.speed_walk AS destroyer_speed_walk,
    restorer.speed_walk AS restorer_speed_walk,
    destroyer.speed_run AS destroyer_speed_run,
    restorer.speed_run AS restorer_speed_run
FROM creature_template restorer
JOIN creature_template destroyer ON destroyer.entry = @wm_alpha_echo_creature_entry
WHERE restorer.entry = @wm_priest_echo_creature_entry;
