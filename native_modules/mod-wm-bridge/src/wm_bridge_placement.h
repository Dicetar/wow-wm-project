#pragma once

#include "MapMgr.h"
#include "Player.h"
#include "wm_bridge_action_support.h"
#include <cmath>

namespace WmBridge
{
    inline bool ResolvePlacement(Player* player, std::string const& json, Position& position)
    {
        using namespace detail;
        uint32 mapId = player->GetMapId();
        TryExtractJsonUInt32Field(json, "map_id", mapId);
        if (mapId != player->GetMapId())
            return false;
        bool hasX = TryExtractJsonFloatField(json, "x", position.m_positionX);
        bool hasY = TryExtractJsonFloatField(json, "y", position.m_positionY);
        bool hasZ = TryExtractJsonFloatField(json, "z", position.m_positionZ);
        if ((hasX || hasY || hasZ) && !(hasX && hasY && hasZ))
            return false;
        float orientation = position.GetOrientation();
        TryExtractJsonFloatField(json, "orientation", orientation);
        if (!std::isfinite(orientation))
            return false;
        position.SetOrientation(Position::NormalizeOrientation(orientation));
        return MapMgr::IsValidMapCoord(mapId, position);
    }
}
