from __future__ import annotations

import argparse, json, sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.quests.bounty import build_bounty_quest_draft
from wm.targets.resolver import TargetProfile, decode_creature_type, decode_family, decode_faction_label, decode_npc_flags, decode_rank, decode_unit_class

_TEMPLATE_DEFAULT_CANDIDATE_COLUMNS = {"Method","QuestMethod","Type","QuestType","QuestFlags","Flags","SpecialFlags","QuestInfoID","QuestSortID","ZoneOrSort","SuggestedPlayers"}

@dataclass(slots=True)
class CreatureLookupResult:
    entry:int; name:str; subname:str|None; profile:TargetProfile

class LiveCreatureResolver:
    def __init__(self, *, client: MysqlCliClient, settings: Settings) -> None:
        self.client=client; self.settings=settings
    def resolve(self, *, entry:int|None=None, name:str|None=None) -> CreatureLookupResult:
        if entry is None and not name: raise ValueError("Provide either an entry or a creature name.")
        if entry is not None:
            rows=self._query_rows("SELECT `entry`, `name`, `subname`, `minlevel`, `maxlevel`, `faction`, `npcflag`, `type`, `family`, `rank`, `unit_class`, `gossip_menu_id` FROM `creature_template` WHERE `entry` = %d LIMIT 1" % int(entry))
            if not rows: raise ValueError(f"Creature entry {entry} was not found in creature_template.")
            return self._build_result(rows[0])
        assert name is not None
        exact_rows=self._query_rows("SELECT `entry`, `name`, `subname`, `minlevel`, `maxlevel`, `faction`, `npcflag`, `type`, `family`, `rank`, `unit_class`, `gossip_menu_id` FROM `creature_template` WHERE `name` = %s ORDER BY `entry` LIMIT 10" % _sql_string(name))
        if len(exact_rows)==1: return self._build_result(exact_rows[0])
        if len(exact_rows)>1: raise ValueError(f"Multiple exact creature matches found for name {name!r}: {self._render_candidates(exact_rows)}")
        like_rows=self._query_rows("SELECT `entry`, `name`, `subname`, `minlevel`, `maxlevel`, `faction`, `npcflag`, `type`, `family`, `rank`, `unit_class`, `gossip_menu_id` FROM `creature_template` WHERE `name` LIKE %s ORDER BY `name`, `entry` LIMIT 10" % _sql_string('%'+name+'%'))
        if len(like_rows)==1: return self._build_result(like_rows[0])
        if not like_rows: raise ValueError(f"No creature name match found for {name!r}.")
        raise ValueError(f"Multiple partial creature matches found for name {name!r}: {self._render_candidates(like_rows)}")
    def fetch_template_defaults_for_questgiver(self, questgiver_entry:int) -> dict[str,Any]:
        starter_rows=self._query_rows("SELECT `quest` FROM `creature_queststarter` WHERE `id` = %d ORDER BY `quest` LIMIT 5" % int(questgiver_entry))
        if not starter_rows: return {}
        columns=self._quest_template_columns(); copy_columns=sorted(_TEMPLATE_DEFAULT_CANDIDATE_COLUMNS & columns)
        if not copy_columns: return {}
        for starter_row in starter_rows:
            quest_id=int(starter_row["quest"])
            rows=self._query_rows("SELECT %s FROM `quest_template` WHERE `ID` = %d LIMIT 1" % (", ".join(f"`{c}`" for c in copy_columns), quest_id))
            if not rows: continue
            defaults={}
            for c in copy_columns:
                v=rows[0].get(c)
                if v in (None,""): continue
                try: defaults[c]=int(v)
                except: defaults[c]=v
            if defaults: return defaults
        return {}
    def _quest_template_columns(self)->set[str]:
        rows=self.client.query(host=self.settings.world_db_host,port=self.settings.world_db_port,user=self.settings.world_db_user,password=self.settings.world_db_password,database="information_schema",sql="SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'quest_template'" % _sql_string(self.settings.world_db_name))
        return {str(r["COLUMN_NAME"]) for r in rows}
    def _query_rows(self, sql:str)->list[dict[str,Any]]:
        return self.client.query(host=self.settings.world_db_host,port=self.settings.world_db_port,user=self.settings.world_db_user,password=self.settings.world_db_password,database=self.settings.world_db_name,sql=sql)
    def _build_result(self,row:dict[str,Any])->CreatureLookupResult:
        profile=TargetProfile(entry=int(row["entry"]),name=str(row.get("name") or ""),subname=row.get("subname"),level_min=int(row.get("minlevel") or 0),level_max=int(row.get("maxlevel") or 0),faction_id=int(row.get("faction") or 0),faction_label=decode_faction_label(int(row.get("faction") or 0)),mechanical_type=decode_creature_type(int(row.get("type") or 0)),family=decode_family(int(row.get("family") or 0)),rank=decode_rank(int(row.get("rank") or 0)),unit_class=decode_unit_class(int(row.get("unit_class") or 0)),service_roles=decode_npc_flags(int(row.get("npcflag") or 0)),has_gossip_menu=int(row.get("gossip_menu_id") or 0)>0)
        return CreatureLookupResult(entry=profile.entry,name=profile.name,subname=profile.subname,profile=profile)
    @staticmethod
    def _render_candidates(rows:list[dict[str,Any]])->str:
        return ", ".join(f"{r.get('entry')}:{r.get('name')}" for r in rows)

def _build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(prog="python -m wm.quests.generate_bounty"); qg=p.add_mutually_exclusive_group(required=True); qg.add_argument("--questgiver-entry",type=int); qg.add_argument("--questgiver-name"); tg=p.add_mutually_exclusive_group(required=True); tg.add_argument("--target-entry",type=int); tg.add_argument("--target-name"); p.add_argument("--quest-id",type=int,required=True); p.add_argument("--kill-count",type=int,default=8); p.add_argument("--reward-money-copper",type=int); p.add_argument("--output-json",type=Path,default=Path("artifacts/generated_bounty.json")); p.add_argument("--summary",action="store_true"); return p

def _render_summary(payload:dict[str,Any], output_path:Path)->str:
    d=payload.get("draft",{}); o=d.get("objective",{}); r=d.get("reward",{}); td=d.get("template_defaults",{}); return "\n".join([f"quest_id: {d.get('quest_id')}",f"title: {d.get('title')}",f"questgiver_entry: {d.get('questgiver_entry')} | {d.get('questgiver_name')}",f"target_entry: {o.get('target_entry')} | {o.get('target_name')}",f"kill_count: {o.get('kill_count')}",f"reward_money_copper: {r.get('money_copper')}",f"reward_item_entry: {r.get('reward_item_entry')}",f"reward_xp_difficulty: {r.get('reward_xp_difficulty')}",f"template_defaults: {', '.join(sorted(td.keys())) if td else '(none)'}",f"output_json: {output_path}"])

def main(argv:list[str]|None=None)->int:
    args=_build_parser().parse_args(argv); settings=Settings.from_env(); client=MysqlCliClient(); resolver=LiveCreatureResolver(client=client,settings=settings)
    questgiver=resolver.resolve(entry=args.questgiver_entry,name=args.questgiver_name); target=resolver.resolve(entry=args.target_entry,name=args.target_name); template_defaults=resolver.fetch_template_defaults_for_questgiver(questgiver.entry)
    draft=build_bounty_quest_draft(quest_id=args.quest_id,questgiver_entry=questgiver.entry,questgiver_name=questgiver.name,target_profile=target.profile,kill_count=args.kill_count,reward_money_copper=args.reward_money_copper,template_defaults=template_defaults)
    payload={"draft":draft.to_dict(),"generation_context":{"questgiver_profile":questgiver.profile.to_dict(),"target_profile":target.profile.to_dict()}}; args.output_json.parent.mkdir(parents=True,exist_ok=True); args.output_json.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
    print(_render_summary(payload,args.output_json) if args.summary else json.dumps(payload,indent=2,ensure_ascii=False)); return 0

def _sql_string(value:str)->str:
    return "'"+value.replace("'","''")+"'"

if __name__=="__main__": raise SystemExit(main())
