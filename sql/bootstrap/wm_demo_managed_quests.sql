-- WM vertical-slice demo: managed quests in the module's reserved range.
--
-- The demo story module (control/examples/story_modules/demo_one.story_module.json)
-- declares constraints.id_ranges.quest = [910500, 910549]. Its PINNED beats
-- and the b01 OPEN fixture grant quests by id via the native bus `quest_add`
-- action. They MUST be fresh managed quests no character has completed —
-- otherwise the grant collides with quest history (Blocker #2: granting a
-- stock quest the demo char already finished fails / shows no new content).
--
-- These rows are cloned from the Northshire starter quests they were modelled
-- on, re-id'd into the managed range, retitled, and stripped of any prereq
-- chain so they grant freely. Grant is direct (bus quest_add) — we deliberately
-- do NOT add creature_queststarter rows (Blocker #3: that would leak the quest
-- to every player who talks to the giver).
--
-- Idempotent: safe to re-run. After running, reload on the worldserver:
--   .reload all quest      (e.g. via SOAP, see wm.runtime_sync.SoapRuntimeClient)
--
-- Mapping:
--   910500  <- 783  "An Unfamiliar Weight"     (b00 PINNED onboarding)
--   910501  <- 33   "The Watcher's Lash"        (b03 PINNED finale)
--   910502  <- 15   "Echo Ridge Investigation"  (b01 OPEN fixture)

DELIMITER $$

DROP PROCEDURE IF EXISTS wm_clone_managed_quest $$
CREATE PROCEDURE wm_clone_managed_quest(
    IN p_new_id INT, IN p_src_id INT,
    IN p_title VARCHAR(255), IN p_qdesc TEXT, IN p_ldesc TEXT)
BEGIN
    DELETE FROM quest_template WHERE ID = p_new_id;
    DELETE FROM quest_template_addon WHERE ID = p_new_id;

    CREATE TEMPORARY TABLE wm_tmp_qt LIKE quest_template;
    INSERT INTO wm_tmp_qt SELECT * FROM quest_template WHERE ID = p_src_id;
    UPDATE wm_tmp_qt
       SET ID = p_new_id,
           LogTitle = p_title,
           QuestDescription = p_qdesc,
           LogDescription = p_ldesc;
    INSERT INTO quest_template SELECT * FROM wm_tmp_qt;
    DROP TEMPORARY TABLE wm_tmp_qt;

    CREATE TEMPORARY TABLE wm_tmp_qta LIKE quest_template_addon;
    INSERT INTO wm_tmp_qta SELECT * FROM quest_template_addon WHERE ID = p_src_id;
    UPDATE wm_tmp_qta
       SET ID = p_new_id,
           PrevQuestID = 0, NextQuestID = 0,
           ExclusiveGroup = 0, BreadcrumbForQuestId = 0;
    INSERT INTO quest_template_addon SELECT * FROM wm_tmp_qta;
    DROP TEMPORARY TABLE wm_tmp_qta;
END $$

DELIMITER ;

CALL wm_clone_managed_quest(910500, 783,
    'An Unfamiliar Weight',
    'The token in your pack hums faintly. Marshal McBride may know its meaning.',
    'Speak with Marshal McBride in Northshire Abbey.');

CALL wm_clone_managed_quest(910501, 33,
    'The Watcher''s Lash',
    'The watcher''s regard has drawn out the wolves. End them, and the regard becomes yours to use.',
    'Defeat the wolves troubling Northshire.');

CALL wm_clone_managed_quest(910502, 15,
    'Echo Ridge Investigation',
    'Marshal McBride asks you to scout Echo Ridge for trouble; the regard takes note of your efficiency.',
    'Investigate the disturbance at Echo Ridge.');

DROP PROCEDURE IF EXISTS wm_clone_managed_quest;
