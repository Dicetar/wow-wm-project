/*
 * Keep faction-capital mailboxes visible even when Individual Progression
 * optional phasing SQL has tagged them with IPP-aware ScriptName values.
 *
 * This override intentionally restores the expected mailbox behavior for:
 * - Stormwind
 * - Darnassus
 * - Orgrimmar
 * - Undercity
 */

UPDATE `gameobject`
SET `ScriptName` = ''
WHERE `guid` IN (
    49832,
    121573, 121574, 121575,
    932, 933, 100156, 100157, 100158, 100159, 100505, 100506,
    150736, 150737, 150738, 150740, 150742, 150743, 150744, 150746, 151239,
    150747, 150748, 150749, 150750, 150751, 150752, 150753, 150755,
    100500, 100501, 100502, 100503, 268683
)
AND `ScriptName` IN ('gobject_ipp_tbc', 'gobject_ipp_wotlk');
