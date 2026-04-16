from __future__ import annotations

from dataclasses import dataclass

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.refs import NpcRef
from wm.targets.resolver import decode_faction_label

_ALLIANCE_RACES = {1, 3, 4, 7, 11}
_HORDE_RACES = {2, 5, 6, 8, 10}
_ALLIANCE_RACE_MASK = 1101
_HORDE_RACE_MASK = 690
_GENERIC_FRIENDLY_FACTIONS = {35}
_ALLIANCE_FACTION_KEYWORDS = (
    "alliance",
    "stormwind",
    "ironforge",
    "darnassus",
    "gnomeregan",
    "exodar",
)
_HORDE_FACTION_KEYWORDS = (
    "horde",
    "orgrimmar",
    "undercity",
    "forsaken",
    "thunder bluff",
    "silvermoon",
)
_GENERIC_FRIENDLY_KEYWORDS = ("friendly", "neutral", "civilian")


@dataclass(frozen=True, slots=True)
class ZoneQuestTurnInCandidate:
    entry: int
    name: str
    subname: str | None
    faction_id: int
    faction_label: str | None
    starter_count: int
    ender_count: int
    spawn_count: int

    @property
    def quest_tie_count(self) -> int:
        return int(self.starter_count) + int(self.ender_count)

    def to_npc_ref(self) -> NpcRef:
        return NpcRef(entry=int(self.entry), name=self.name)


class ZoneQuestTurnInSelector:
    def __init__(self, *, client: MysqlCliClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def select(self, *, player_guid: int, zone_id: int | None) -> ZoneQuestTurnInCandidate | None:
        resolved_zone_id = _int_or_none(zone_id)
        if resolved_zone_id is None or resolved_zone_id <= 0:
            return None

        player_team = self._player_team_for_guid(player_guid)
        player_race_mask = _team_race_mask(player_team)
        candidates = self._load_zone_candidates(zone_id=resolved_zone_id, player_race_mask=player_race_mask)
        if not candidates:
            return None

        ranked = sorted(
            candidates,
            key=lambda candidate: (
                candidate.quest_tie_count,
                candidate.starter_count,
                self._team_score(team=player_team, candidate=candidate),
                candidate.spawn_count,
                -candidate.entry,
            ),
            reverse=True,
        )
        return ranked[0]

    def _player_team_for_guid(self, player_guid: int) -> str | None:
        rows = self.client.query(
            host=self.settings.char_db_host,
            port=self.settings.char_db_port,
            user=self.settings.char_db_user,
            password=self.settings.char_db_password,
            database=self.settings.char_db_name,
            sql=(
                "SELECT race FROM characters "
                f"WHERE guid = {int(player_guid)} LIMIT 1"
            ),
        )
        if not rows:
            return None
        race = _int_or_none(rows[0].get("race"))
        if race in _ALLIANCE_RACES:
            return "alliance"
        if race in _HORDE_RACES:
            return "horde"
        return None

    def _load_zone_candidates(self, *, zone_id: int, player_race_mask: int | None) -> list[ZoneQuestTurnInCandidate]:
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=_build_zone_questgiver_sql(zone_id=zone_id, player_race_mask=player_race_mask),
        )
        candidates = self._rows_to_candidates(rows)
        if candidates:
            return candidates

        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=_build_spawn_zone_questgiver_sql(zone_id=zone_id, player_race_mask=player_race_mask),
        )
        return self._rows_to_candidates(rows)

    def _rows_to_candidates(self, rows: list[dict[str, object]]) -> list[ZoneQuestTurnInCandidate]:
        candidates: list[ZoneQuestTurnInCandidate] = []
        for row in rows:
            starter_count = _int_or_none(row.get("quest_starter_count")) or 0
            ender_count = _int_or_none(row.get("quest_ender_count")) or 0
            if starter_count + ender_count <= 0:
                continue
            name = str(row.get("name") or "").strip()
            if not name:
                continue
            faction_id = _int_or_none(row.get("faction")) or 0
            faction_label = _normalize_text_or_none(row.get("faction_name")) or decode_faction_label(faction_id)
            candidates.append(
                ZoneQuestTurnInCandidate(
                    entry=int(row["entry"]),
                    name=name,
                    subname=_normalize_text_or_none(row.get("subname")),
                    faction_id=faction_id,
                    faction_label=faction_label,
                    starter_count=starter_count,
                    ender_count=ender_count,
                    spawn_count=_int_or_none(row.get("spawn_count")) or 0,
                )
            )
        return candidates

    def _team_score(self, *, team: str | None, candidate: ZoneQuestTurnInCandidate) -> int:
        faction_label = (candidate.faction_label or "").strip().lower()
        if candidate.faction_id in _GENERIC_FRIENDLY_FACTIONS:
            return 1
        if any(keyword in faction_label for keyword in _GENERIC_FRIENDLY_KEYWORDS):
            return 1
        if team == "alliance" and any(keyword in faction_label for keyword in _ALLIANCE_FACTION_KEYWORDS):
            return 2
        if team == "horde" and any(keyword in faction_label for keyword in _HORDE_FACTION_KEYWORDS):
            return 2
        return 0


def _build_zone_questgiver_sql(*, zone_id: int, player_race_mask: int | None) -> str:
    starter_filter = _quest_availability_filter(alias="qts", player_race_mask=player_race_mask)
    ender_filter = _quest_availability_filter(alias="qte", player_race_mask=player_race_mask)
    return f"""
SELECT
    ct.entry,
    ct.name,
    NULLIF(ct.subname, '') AS subname,
    ct.faction,
    COALESCE(fd.Name_Lang_enUS, '') AS faction_name,
    (
        SELECT COUNT(*)
        FROM creature c
        WHERE c.id1 = ct.entry
    ) AS spawn_count,
    COUNT(DISTINCT CASE WHEN qts.QuestSortID = {int(zone_id)} AND {starter_filter} THEN cqs.quest END) AS quest_starter_count,
    COUNT(DISTINCT CASE WHEN qte.QuestSortID = {int(zone_id)} AND {ender_filter} THEN cqe.quest END) AS quest_ender_count
FROM creature_template ct
LEFT JOIN faction_dbc fd ON fd.ID = ct.faction
LEFT JOIN creature_queststarter cqs ON cqs.id = ct.entry
LEFT JOIN quest_template qts ON qts.ID = cqs.quest
LEFT JOIN creature_questender cqe ON cqe.id = ct.entry
LEFT JOIN quest_template qte ON qte.ID = cqe.quest
GROUP BY ct.entry, ct.name, ct.subname, ct.faction, fd.Name_Lang_enUS
HAVING (
    COUNT(DISTINCT CASE WHEN qts.QuestSortID = {int(zone_id)} AND {starter_filter} THEN cqs.quest END)
    + COUNT(DISTINCT CASE WHEN qte.QuestSortID = {int(zone_id)} AND {ender_filter} THEN cqe.quest END)
) > 0
ORDER BY
    (
        COUNT(DISTINCT CASE WHEN qts.QuestSortID = {int(zone_id)} AND {starter_filter} THEN cqs.quest END)
        + COUNT(DISTINCT CASE WHEN qte.QuestSortID = {int(zone_id)} AND {ender_filter} THEN cqe.quest END)
    ) DESC,
    COUNT(DISTINCT CASE WHEN qts.QuestSortID = {int(zone_id)} AND {starter_filter} THEN cqs.quest END) DESC,
    spawn_count DESC,
    ct.entry ASC
LIMIT 64
""".strip()


def _build_spawn_zone_questgiver_sql(*, zone_id: int, player_race_mask: int | None) -> str:
    starter_filter = _quest_availability_filter(alias="qts", player_race_mask=player_race_mask)
    ender_filter = _quest_availability_filter(alias="qte", player_race_mask=player_race_mask)
    return f"""
SELECT
    ct.entry,
    ct.name,
    NULLIF(ct.subname, '') AS subname,
    ct.faction,
    COALESCE(fd.Name_Lang_enUS, '') AS faction_name,
    COUNT(DISTINCT c.guid) AS spawn_count,
    COUNT(DISTINCT CASE WHEN {starter_filter} THEN cqs.quest END) AS quest_starter_count,
    COUNT(DISTINCT CASE WHEN {ender_filter} THEN cqe.quest END) AS quest_ender_count
FROM creature c
JOIN creature_template ct ON ct.entry = c.id1
LEFT JOIN faction_dbc fd ON fd.ID = ct.faction
LEFT JOIN creature_queststarter cqs ON cqs.id = ct.entry
LEFT JOIN quest_template qts ON qts.ID = cqs.quest
LEFT JOIN creature_questender cqe ON cqe.id = ct.entry
LEFT JOIN quest_template qte ON qte.ID = cqe.quest
WHERE c.zoneId = {int(zone_id)}
GROUP BY ct.entry, ct.name, ct.subname, ct.faction, fd.Name_Lang_enUS
HAVING (
    COUNT(DISTINCT CASE WHEN {starter_filter} THEN cqs.quest END)
    + COUNT(DISTINCT CASE WHEN {ender_filter} THEN cqe.quest END)
) > 0
ORDER BY
    (
        COUNT(DISTINCT CASE WHEN {starter_filter} THEN cqs.quest END)
        + COUNT(DISTINCT CASE WHEN {ender_filter} THEN cqe.quest END)
    ) DESC,
    COUNT(DISTINCT CASE WHEN {starter_filter} THEN cqs.quest END) DESC,
    COUNT(DISTINCT c.guid) DESC,
    ct.entry ASC
LIMIT 64
""".strip()


def _quest_availability_filter(*, alias: str, player_race_mask: int | None) -> str:
    if player_race_mask is None:
        return "1 = 1"
    return f"({alias}.AllowableRaces = 0 OR ({alias}.AllowableRaces & {int(player_race_mask)}) <> 0)"


def _int_or_none(value: object) -> int | None:
    if value in (None, "", "NULL"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_text_or_none(value: object) -> str | None:
    if value in (None, "", "NULL"):
        return None
    return str(value).strip() or None


def _team_race_mask(team: str | None) -> int | None:
    if team == "alliance":
        return _ALLIANCE_RACE_MASK
    if team == "horde":
        return _HORDE_RACE_MASK
    return None
