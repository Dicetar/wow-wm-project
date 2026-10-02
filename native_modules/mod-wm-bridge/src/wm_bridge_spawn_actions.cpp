#include "Creature.h"
#include "GameObject.h"
#include "Map.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "wm_bridge_action_registry.h"
#include "wm_bridge_action_support.h"
#include "wm_bridge_placement.h"

namespace
{
    using namespace WmBridge::detail;

    bool ExecuteWorldSpawn(uint64 requestId, uint32 playerGuid, std::string const& kind, std::string const& json)
    {
        Player* player = nullptr;
        if (!ResolveScopedOnlinePlayer(requestId, playerGuid, kind, json, player))
            return true;
        auto fail = [&](std::string const& message) {
            CompleteAction(requestId, "rejected", kind, ActionResultJson("rejected", kind, message), message);
            return true;
        };
        std::string type = ExtractJsonStringField(json, "object_type");
        bool isCreature = type == "creature";
        if (!isCreature && type != "gameobject")
            return fail("invalid_object_type");
        if (ExtractJsonStringField(json, "reason").empty())
            return fail("missing_change_reason");
        Map* map = player->GetMap();
        if (map->Instanceable() || player->GetTransport())
            return fail("persistent_spawn_requires_outdoor_map");
        uint32 spawnId = 0;
        uint32 entry = 0;
        uint32 phase = player->GetPhaseMaskForSpawn();
        uint32 respawn = 300;
        bool hasRespawn = TryExtractJsonUInt32Field(json, "respawn_seconds", respawn);
        bool hasPhase = TryExtractJsonUInt32Field(json, "phase_mask", phase);
        if (!phase || respawn > 2147483647)
            return fail("invalid_phase_or_respawn");
        bool create = kind == "world_spawn_create";
        bool remove = kind == "world_spawn_delete";
        Creature* creature = nullptr;
        GameObject* object = nullptr;
        Position position = player->GetPosition();
        if (!create)
        {
            if (!TryExtractJsonUInt32Field(json, "spawn_id", spawnId) || !spawnId)
                return fail("missing_spawn_id");
            if (isCreature)
            {
                auto& store = map->GetCreatureBySpawnIdStore();
                auto found = store.find(spawnId);
                if (found == store.end())
                    return fail("spawn_not_loaded_on_player_map");
                creature = found->second;
                position = creature->GetPosition();
            }
            else
            {
                auto& store = map->GetGameObjectBySpawnIdStore();
                auto found = store.find(spawnId);
                if (found == store.end())
                    return fail("spawn_not_loaded_on_player_map");
                object = found->second;
                if (sObjectMgr->IsGameObjectStaticTransport(object->GetEntry()))
                    return fail("transport_spawn_not_supported");
                position = object->GetPosition();
            }
        }
        if (!remove && !WmBridge::ResolvePlacement(player, json, position))
            return fail("invalid_spawn_position");
        if (create)
        {
            if (!TryExtractJsonUInt32Field(json, "entry", entry) || !entry)
                return fail("missing_template_entry");
            if (isCreature)
            {
                if (!sObjectMgr->GetCreatureTemplate(entry))
                    return fail("invalid_creature_template");
                creature = new Creature();
                if (!creature->Create(map->GenerateLowGuid<HighGuid::Unit>(), map, phase, entry, 0,
                    position.GetPositionX(), position.GetPositionY(), position.GetPositionZ(), position.GetOrientation()))
                {
                    delete creature;
                    return fail("creature_create_failed");
                }
                creature->SetRespawnDelay(respawn);
                creature->SaveToDB(map->GetId(), 1 << map->GetSpawnMode(), phase);
                spawnId = creature->GetSpawnId();
                creature->CleanupsBeforeDelete();
                delete creature;
                creature = new Creature();
                if (!creature->LoadCreatureFromDB(spawnId, map, true, true))
                {
                    delete creature;
                    CompleteAction(requestId, "failed", kind, ActionResultJson("failed", kind, "spawn_saved_but_not_loaded", {}, {{"spawn_id", spawnId}}), "spawn_saved_but_not_loaded");
                    return true;
                }
                sObjectMgr->AddCreatureToGrid(spawnId, sObjectMgr->GetCreatureData(spawnId));
            }
            else
            {
                auto info = sObjectMgr->GetGameObjectTemplate(entry);
                if (!info || sObjectMgr->IsGameObjectStaticTransport(entry))
                    return fail("invalid_or_transport_gameobject_template");
                object = new GameObject();
                auto rotation = G3D::Quat::fromAxisAngleRotation(G3D::Vector3::unitZ(), position.GetOrientation());
                if (!object->Create(map->GenerateLowGuid<HighGuid::GameObject>(), entry, map, phase,
                    position.GetPositionX(), position.GetPositionY(), position.GetPositionZ(), position.GetOrientation(), rotation, 0, GO_STATE_READY))
                {
                    delete object;
                    return fail("gameobject_create_failed");
                }
                object->SetRespawnDelay(respawn);
                object->SaveToDB(map->GetId(), 1 << map->GetSpawnMode(), phase);
                spawnId = object->GetSpawnId();
                delete object;
                object = new GameObject();
                if (!object->LoadGameObjectFromDB(spawnId, map, true))
                {
                    delete object;
                    CompleteAction(requestId, "failed", kind, ActionResultJson("failed", kind, "spawn_saved_but_not_loaded", {}, {{"spawn_id", spawnId}}), "spawn_saved_but_not_loaded");
                    return true;
                }
                sObjectMgr->AddGameobjectToGrid(spawnId, sObjectMgr->GetGameObjectData(spawnId));
            }
        }
        else if (isCreature)
        {
            if (remove)
            {
                creature->CombatStop();
                creature->DeleteFromDB();
                creature->AddObjectToRemoveList();
            }
            else
            {
                sObjectMgr->RemoveCreatureFromGrid(spawnId, sObjectMgr->GetCreatureData(spawnId));
                map->CreatureRelocation(creature, position.GetPositionX(), position.GetPositionY(), position.GetPositionZ(), position.GetOrientation());
                creature->SetHomePosition(position);
                if (hasRespawn) creature->SetRespawnDelay(respawn);
                if (hasPhase) creature->SetPhaseMask(phase, true);
                creature->SaveToDB();
                sObjectMgr->AddCreatureToGrid(spawnId, sObjectMgr->GetCreatureData(spawnId));
            }
        }
        else if (remove)
        {
            object->SetRespawnTime(0);
            object->DeleteFromDB();
            object->Delete();
        }
        else
        {
            sObjectMgr->RemoveGameobjectFromGrid(spawnId, object->GetGameObjectData());
            object->Relocate(position);
            object->SetWorldRotationAngles(position.GetOrientation(), 0, 0);
            if (hasRespawn) object->SetRespawnDelay(respawn);
            if (hasPhase) object->SetPhaseMask(phase, true);
            object->SaveToDB(map->GetId(), object->GetGameObjectData()->spawnMask, object->GetPhaseMask());
            sObjectMgr->AddGameobjectToGrid(spawnId, object->GetGameObjectData());
            // Use a new live GUID because 3.3.5 caches an object's old position.
            object->Delete();
            object = new GameObject();
            if (!object->LoadGameObjectFromDB(spawnId, map, true))
            {
                delete object;
                CompleteAction(requestId, "failed", kind, ActionResultJson("failed", kind, "spawn_saved_but_not_loaded", {}, {{"spawn_id", spawnId}}), "spawn_saved_but_not_loaded");
                return true;
            }
        }
        CompleteAction(requestId, "done", kind, ActionResultJson("done", kind, remove ? "spawn_deleted" : create ? "spawn_created" : "spawn_updated",
            {{"object_type", type}}, {{"spawn_id", spawnId}, {"map_id", player->GetMapId()}},
            {{"x", position.GetPositionX()}, {"y", position.GetPositionY()}, {"z", position.GetPositionZ()}, {"orientation", position.GetOrientation()}}));
        return true;
    }
}

namespace WmBridge
{
    void RegisterWmBridgeSpawnActions(ActionRegistry& registry)
    {
        registry.Register("world_spawn_create", &ExecuteWorldSpawn);
        registry.Register("world_spawn_update", &ExecuteWorldSpawn);
        registry.Register("world_spawn_delete", &ExecuteWorldSpawn);
    }
}
