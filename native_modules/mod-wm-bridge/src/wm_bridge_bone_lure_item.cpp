#include "Cell.h"
#include "CellImpl.h"
#include "Combat/ThreatManager.h"
#include "Creature.h"
#include "CreatureData.h"
#include "CreatureScript.h"
#include "DatabaseEnv.h"
#include "GridNotifiers.h"
#include "Item.h"
#include "ItemScript.h"
#include "ObjectAccessor.h"
#include "Player.h"
#include "ScriptedCreature.h"
#include "SharedDefines.h"
#include "Spell.h"
#include "SpellAuraDefines.h"
#include "TemporarySummon.h"
#include "Unit.h"
#include "WorldSession.h"
#include "wm_bridge_common.h"

#include <algorithm>
#include <list>
#include <sstream>
#include <unordered_set>

namespace
{
    constexpr uint32 WM_BONE_LURE_ITEM_ENTRY = 910009;
    constexpr uint32 WM_BONE_LURE_CREATURE_ENTRY = 920102;
    constexpr uint32 BONE_LURE_DURATION_MS = 30000;
    constexpr uint32 BONE_LURE_TAUNT_INTERVAL_MS = 1000;
    constexpr float BONE_LURE_TAUNT_RADIUS = 200.0f;
    constexpr uint32 BONE_LURE_DAMAGE_TAKEN_PCT = 25;
    constexpr float BONE_LURE_THREAT = 10000000.0f;
    constexpr float BONE_LURE_RELEASE_OWNER_THREAT = 5000.0f;
    constexpr float BONE_LURE_FALLBACK_THROW_DISTANCE = 25.0f;

    void SendPlayerMessage(Player* player, std::string const& message)
    {
        if (player && player->GetSession())
        {
            player->GetSession()->SendAreaTriggerMessage(message);
        }
    }

    Position ResolveSpawnPosition(Player* player, SpellCastTargets const& targets)
    {
        if (targets.HasDst())
        {
            if (WorldLocation const* destination = targets.GetDstPos())
            {
                Position position(*destination);
                player->UpdateAllowedPositionZ(position.m_positionX, position.m_positionY, position.m_positionZ);
                return position;
            }
        }

        Position position = player->GetFirstCollisionPosition(BONE_LURE_FALLBACK_THROW_DISTANCE, player->GetOrientation());
        player->UpdateAllowedPositionZ(position.m_positionX, position.m_positionY, position.m_positionZ);
        return position;
    }

    void ApplyBoneLureImmunities(Creature* creature)
    {
        if (!creature)
        {
            return;
        }

        uint32 const immuneAuras[] = {
            SPELL_AURA_PERIODIC_DAMAGE,
            SPELL_AURA_PERIODIC_DAMAGE_PERCENT,
            SPELL_AURA_PERIODIC_LEECH,
            SPELL_AURA_PERIODIC_HEALTH_FUNNEL,
            SPELL_AURA_PERIODIC_MANA_LEECH,
            SPELL_AURA_MOD_CONFUSE,
            SPELL_AURA_MOD_CHARM,
            SPELL_AURA_MOD_FEAR,
            SPELL_AURA_MOD_STUN,
            SPELL_AURA_MOD_PACIFY,
            SPELL_AURA_MOD_ROOT,
            SPELL_AURA_MOD_SILENCE,
            SPELL_AURA_MOD_DECREASE_SPEED,
            SPELL_AURA_MOD_PACIFY_SILENCE,
            SPELL_AURA_MOD_DISARM,
            SPELL_AURA_MOD_DISARM_OFFHAND,
            SPELL_AURA_MOD_DISARM_RANGED,
        };

        for (uint32 aura : immuneAuras)
        {
            creature->ApplySpellImmune(0, IMMUNITY_STATE, aura, true);
        }

        uint32 const immuneMechanics[] = {
            MECHANIC_CHARM,
            MECHANIC_DISORIENTED,
            MECHANIC_DISARM,
            MECHANIC_FEAR,
            MECHANIC_ROOT,
            MECHANIC_SILENCE,
            MECHANIC_SLEEP,
            MECHANIC_SNARE,
            MECHANIC_STUN,
            MECHANIC_FREEZE,
            MECHANIC_KNOCKOUT,
            MECHANIC_BLEED,
            MECHANIC_POLYMORPH,
            MECHANIC_BANISH,
            MECHANIC_SHACKLE,
            MECHANIC_HORROR,
            MECHANIC_DAZE,
            MECHANIC_SAPPED,
            MECHANIC_TAUNTED,
        };

        for (uint32 mechanic : immuneMechanics)
        {
            creature->ApplySpellImmune(0, IMMUNITY_MECHANIC, mechanic, true);
        }
    }

    void ConfigureBoneLureCreature(Creature* creature, Player* owner)
    {
        if (!creature || !owner)
        {
            return;
        }

        uint32 ownerHealth = std::max<uint32>(1, owner->GetMaxHealth());
        creature->SetCreatorGUID(owner->GetGUID());
        creature->SetOwnerGUID(owner->GetGUID());
        creature->SetFaction(owner->GetFaction());
        creature->SetPhaseMask(owner->GetPhaseMask(), false);
        creature->SetLevel(owner->GetLevel());
        creature->SetCreateHealth(ownerHealth);
        creature->SetMaxHealth(ownerHealth);
        creature->SetHealth(ownerHealth);
        creature->SetHomePosition(creature->GetPosition());
        creature->SetReactState(REACT_PASSIVE);
        creature->AddUnitState(UNIT_STATE_ROOT);
        creature->SetControlled(true, UNIT_STATE_ROOT);
        ApplyBoneLureImmunities(creature);
    }

    bool IsEligibleBoneLureTarget(Creature* creature, Creature* lure, Player* owner)
    {
        if (!creature || !lure || creature == lure || !creature->IsAlive())
        {
            return false;
        }

        if (!creature->IsInWorld() || creature->IsTrigger() || creature->IsCivilian())
        {
            return false;
        }

        if (creature->GetOwnerGUID().IsPlayer())
        {
            return false;
        }

        if (creature->HasUnitTypeMask(UNIT_MASK_PET | UNIT_MASK_TOTEM | UNIT_MASK_PUPPET | UNIT_MASK_VEHICLE))
        {
            return false;
        }

        CreatureTemplate const* creatureTemplate = creature->GetCreatureTemplate();
        if (!creatureTemplate)
        {
            return false;
        }

        if (creature->isWorldBoss() || creature->IsDungeonBoss() || creatureTemplate->rank == CREATURE_ELITE_WORLDBOSS)
        {
            return false;
        }

        if (creature->HasFlagsExtra(CREATURE_FLAG_EXTRA_NO_TAUNT))
        {
            return false;
        }

        if (!creature->IsWithinDistInMap(lure, BONE_LURE_TAUNT_RADIUS))
        {
            return false;
        }

        if (owner && (creature->IsHostileTo(owner) || owner->IsValidAttackTarget(creature)))
        {
            return true;
        }

        return creature->IsHostileTo(lure) || lure->IsValidAttackTarget(creature);
    }

    void AttackLure(Creature* creature, Creature* lure, Player* owner)
    {
        if (!creature || !lure)
        {
            return;
        }

        creature->GetThreatMgr().AddThreat(lure, BONE_LURE_THREAT, nullptr, true, true);
        if (owner)
        {
            creature->GetThreatMgr().AddThreat(owner, 1.0f, nullptr, true, true);
        }
        creature->GetThreatMgr().FixateTarget(lure);
        creature->SetInCombatWith(lure);
        lure->SetInCombatWith(creature);
        creature->UpdateLeashExtensionTime();
        if (creature->AI())
        {
            creature->AI()->AttackStart(lure);
        }
    }
}

class wm_bone_lure_obelisk_ai : public ScriptedAI
{
public:
    explicit wm_bone_lure_obelisk_ai(Creature* creature) : ScriptedAI(creature) { }

    void IsSummonedBy(WorldObject* summoner) override
    {
        if (Player* player = summoner ? summoner->ToPlayer() : nullptr)
        {
            _ownerGuid = player->GetGUID();
            ConfigureBoneLureCreature(me, player);
        }
    }

    void SetGUID(ObjectGuid const& guid, int32 id = 0) override
    {
        if (id == 1 || id == 0)
        {
            _ownerGuid = guid;
        }
    }

    void Reset() override
    {
        _remainingMs = BONE_LURE_DURATION_MS;
        _pulseMs = 0;
        _released = false;
        me->SetReactState(REACT_PASSIVE);
        me->AddUnitState(UNIT_STATE_ROOT);
        ApplyBoneLureImmunities(me);
    }

    void DamageTaken(Unit* /*attacker*/, uint32& damage, DamageEffectType /*damageType*/, SpellSchoolMask /*damageSchoolMask*/) override
    {
        if (damage > 0)
        {
            damage = std::max<uint32>(1, damage * BONE_LURE_DAMAGE_TAKEN_PCT / 100);
        }
    }

    void JustDied(Unit* /*killer*/) override
    {
        ReleasePulledMobs();
    }

    void UpdateAI(uint32 diff) override
    {
        if (!me->IsAlive())
        {
            return;
        }

        if (_remainingMs <= diff)
        {
            ReleasePulledMobs();
            me->DespawnOrUnsummon(1ms);
            return;
        }
        _remainingMs -= diff;

        if (_pulseMs <= diff)
        {
            PulseTaunt();
            _pulseMs = BONE_LURE_TAUNT_INTERVAL_MS;
            return;
        }
        _pulseMs -= diff;
    }

private:
    Player* GetOwnerPlayer() const
    {
        if (_ownerGuid.IsEmpty())
        {
            return nullptr;
        }

        return ObjectAccessor::GetPlayer(*me, _ownerGuid);
    }

    void PulseTaunt()
    {
        Player* owner = GetOwnerPlayer();
        if (owner && !WmBridge::IsPlayerAllowed(owner))
        {
            return;
        }

        std::list<WorldObject*> nearbyObjects;
        Acore::AllWorldObjectsInRange check(me, BONE_LURE_TAUNT_RADIUS);
        Acore::WorldObjectListSearcher<Acore::AllWorldObjectsInRange> searcher(me, nearbyObjects, check);
        Cell::VisitObjects(me, searcher, BONE_LURE_TAUNT_RADIUS);

        for (WorldObject* object : nearbyObjects)
        {
            Creature* creature = object ? object->ToCreature() : nullptr;
            if (!IsEligibleBoneLureTarget(creature, me, owner))
            {
                continue;
            }

            AttackLure(creature, me, owner);
            _pulledCreatureGuids.insert(creature->GetGUID());
        }
    }

    void ReleasePulledMobs()
    {
        if (_released)
        {
            return;
        }
        _released = true;

        Player* owner = GetOwnerPlayer();
        for (ObjectGuid const& guid : _pulledCreatureGuids)
        {
            Creature* creature = ObjectAccessor::GetCreature(*me, guid);
            if (!creature || !creature->IsAlive())
            {
                continue;
            }

            if (creature->GetThreatMgr().GetFixateTarget() == me)
            {
                creature->GetThreatMgr().ClearFixate();
            }
            creature->GetThreatMgr().ClearThreat(me);

            if (owner && owner->IsAlive() && (creature->IsHostileTo(owner) || owner->IsValidAttackTarget(creature)))
            {
                creature->GetThreatMgr().AddThreat(owner, BONE_LURE_RELEASE_OWNER_THREAT, nullptr, true, true);
                creature->SetInCombatWith(owner);
                owner->SetInCombatWith(creature);
                creature->UpdateLeashExtensionTime();
                if (creature->AI())
                {
                    creature->AI()->AttackStart(owner);
                }
            }
        }
        _pulledCreatureGuids.clear();
    }

    ObjectGuid _ownerGuid;
    uint32 _remainingMs = BONE_LURE_DURATION_MS;
    uint32 _pulseMs = 0;
    bool _released = false;
    std::unordered_set<ObjectGuid> _pulledCreatureGuids;
};

class wm_bone_lure_obelisk : public CreatureScript
{
public:
    wm_bone_lure_obelisk() : CreatureScript("wm_bone_lure_obelisk") { }

    CreatureAI* GetAI(Creature* creature) const override
    {
        return new wm_bone_lure_obelisk_ai(creature);
    }
};

class wm_bone_lure_charm : public ItemScript
{
public:
    wm_bone_lure_charm() : ItemScript("wm_bone_lure_charm") { }

    bool OnUse(Player* player, Item* item, SpellCastTargets const& targets) override
    {
        if (!player || !item || item->GetEntry() != WM_BONE_LURE_ITEM_ENTRY)
        {
            return true;
        }

        if (!WmBridge::IsPlayerAllowed(player))
        {
            SendPlayerMessage(player, "Bone lure is inactive for this character.");
            return true;
        }

        Position position = ResolveSpawnPosition(player, targets);
        TempSummon* summon = player->SummonCreature(
            WM_BONE_LURE_CREATURE_ENTRY,
            position.m_positionX,
            position.m_positionY,
            position.m_positionZ,
            player->GetOrientation(),
            TEMPSUMMON_MANUAL_DESPAWN,
            0);

        if (!summon)
        {
            SendPlayerMessage(player, "The bone lure failed to anchor here.");
            return true;
        }

        ConfigureBoneLureCreature(summon, player);
        summon->AI()->SetGUID(player->GetGUID(), 1);

        uint32 destroyCount = 1;
        player->DestroyItemCount(item, destroyCount, true);

        CharacterDatabaseTransaction trans = CharacterDatabase.BeginTransaction();
        player->SaveInventoryAndGoldToDB(trans);
        CharacterDatabase.CommitTransaction(trans);

        std::ostringstream message;
        message << "Bone Lure Obelisk deployed for " << (BONE_LURE_DURATION_MS / 1000)
                << " seconds. It taunts non-boss enemies within 200 yards.";
        SendPlayerMessage(player, message.str());
        return true;
    }
};

void AddSC_mod_wm_bridge_bone_lure_item()
{
    new wm_bone_lure_obelisk();
    new wm_bone_lure_charm();
}
