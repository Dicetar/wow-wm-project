from __future__ import annotations

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.targets.live_profile import LiveTargetProfile, build_live_target_profile


class RuntimeTargetResolver:
    def __init__(self, client: MysqlCliClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def resolve_creature_entry(self, entry: int) -> LiveTargetProfile | None:
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=build_runtime_target_sql(int(entry)),
        )
        if not rows:
            return None
        return build_live_target_profile(rows[0])


def build_runtime_target_sql(entry: int) -> str:
    return f"""
SELECT
    ct.entry,
    ct.name,
    NULLIF(ct.subname, '') AS subname,
    ct.minlevel,
    ct.maxlevel,
    ct.faction,
    ct.npcflag,
    ct.type,
    ct.family,
    ct.rank,
    ct.unit_class,
    ct.gossip_menu_id,
    COALESCE(fd.Name_Lang_enUS, '') AS faction_name,
    (
        SELECT COUNT(*)
        FROM gossip_menu_option gmo
        WHERE gmo.MenuID = ct.gossip_menu_id
    ) AS gossip_option_count,
    (
        SELECT GROUP_CONCAT(cqs.quest ORDER BY cqs.quest SEPARATOR ',')
        FROM creature_queststarter cqs
        WHERE cqs.id = ct.entry
    ) AS quest_starter_ids,
    (
        SELECT GROUP_CONCAT(cqe.quest ORDER BY cqe.quest SEPARATOR ',')
        FROM creature_questender cqe
        WHERE cqe.id = ct.entry
    ) AS quest_ender_ids,
    (
        SELECT COUNT(*)
        FROM npc_vendor nv
        WHERE nv.entry = ct.entry
    ) AS vendor_item_count,
    (
        SELECT COUNT(*)
        FROM trainer_spell ts
        JOIN trainer t ON t.Id = ts.TrainerId
        WHERE t.Id = ct.entry
    ) AS trainer_spell_count,
    (
        SELECT COUNT(*)
        FROM creature c
        WHERE c.id1 = ct.entry
    ) AS spawn_count,
    (
        SELECT GROUP_CONCAT(CONCAT(grouped.map, ':', grouped.zoneId, ':', grouped.spawn_count) ORDER BY grouped.spawn_count DESC, grouped.map, grouped.zoneId SEPARATOR ';')
        FROM (
            SELECT c.map AS map, c.zoneId AS zoneId, COUNT(*) AS spawn_count
            FROM creature c
            WHERE c.id1 = ct.entry
            GROUP BY c.map, c.zoneId
            ORDER BY COUNT(*) DESC, c.map, c.zoneId
            LIMIT 5
        ) AS grouped
    ) AS spawn_contexts
FROM creature_template ct
LEFT JOIN faction_dbc fd ON fd.ID = ct.faction
WHERE ct.entry = {entry}
LIMIT 1;
""".strip()
