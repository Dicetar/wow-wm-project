#include "wm_test.h"
#include "wm_effect_registry.h"

#include <chrono>
#include <thread>

using WmBridge::WMEffectRegistry;

// WMEffectRegistry is a process singleton (Instance()). State persists
// across cases, so every test uses a disjoint target-GUID range to stay
// independent. These cases characterize CURRENT behavior — they are the
// regression net for the Phase 0 refactor, not a redesign.

namespace
{
    constexpr bool kPlayer = true;
    constexpr bool kCreature = false;
}

TEST(WMEffectRegistry, IsActiveFalseWhenUnregistered)
{
    auto& r = WMEffectRegistry::Instance();
    EXPECT_FALSE(r.IsActive(9990001, kPlayer, 946001));
}

TEST(WMEffectRegistry, RegisterThenIsActivePermanent)
{
    auto& r = WMEffectRegistry::Instance();
    r.Register(5406, 9990010, kPlayer, 946001, "damage_dot", "{}", 0);
    EXPECT_TRUE(r.IsActive(9990010, kPlayer, 946001));
}

TEST(WMEffectRegistry, UnregisterClearsActive)
{
    auto& r = WMEffectRegistry::Instance();
    r.Register(5406, 9990020, kPlayer, 946001, "slow", "{}", 0);
    EXPECT_TRUE(r.IsActive(9990020, kPlayer, 946001));
    r.Unregister(9990020, kPlayer, 946001);
    EXPECT_FALSE(r.IsActive(9990020, kPlayer, 946001));
}

TEST(WMEffectRegistry, PermanentSurvivesExpireSweep)
{
    auto& r = WMEffectRegistry::Instance();
    r.Register(5406, 9990030, kPlayer, 946001, "buff", "{}", /*permanent*/ 0);
    r.ExpireOverdue();
    EXPECT_TRUE(r.IsActive(9990030, kPlayer, 946001));
}

TEST(WMEffectRegistry, PlayerCreatureKeyIsolation)
{
    auto& r = WMEffectRegistry::Instance();
    r.Register(5406, 9990040, kPlayer, 946001, "dot", "{}", 0);
    EXPECT_TRUE(r.IsActive(9990040, kPlayer, 946001));
    // Same guid + spell but creature kind must be a distinct slot.
    EXPECT_FALSE(r.IsActive(9990040, kCreature, 946001));
}

TEST(WMEffectRegistry, AuraIdIsolation)
{
    auto& r = WMEffectRegistry::Instance();
    r.Register(5406, 9990050, kPlayer, 946001, "dot", "{}", 0);
    EXPECT_TRUE(r.IsActive(9990050, kPlayer, 946001));
    EXPECT_FALSE(r.IsActive(9990050, kPlayer, 946999));
}

TEST(WMEffectRegistry, TargetGuidIsolation)
{
    auto& r = WMEffectRegistry::Instance();
    r.Register(5406, 9990060, kPlayer, 946001, "dot", "{}", 0);
    EXPECT_TRUE(r.IsActive(9990060, kPlayer, 946001));
    EXPECT_FALSE(r.IsActive(9990061, kPlayer, 946001));
}

TEST(WMEffectRegistry, CreatureTargetTracked)
{
    auto& r = WMEffectRegistry::Instance();
    r.Register(5406, 9990070, kCreature, 946001, "dot", "{}", 0);
    EXPECT_TRUE(r.IsActive(9990070, kCreature, 946001));
    EXPECT_FALSE(r.IsActive(9990070, kPlayer, 946001));
}

TEST(WMEffectRegistry, DuplicateRegisterReactivates)
{
    auto& r = WMEffectRegistry::Instance();
    r.Register(5406, 9990080, kPlayer, 946001, "dot", "{}", 0);
    r.Unregister(9990080, kPlayer, 946001);
    EXPECT_FALSE(r.IsActive(9990080, kPlayer, 946001));
    r.Register(5406, 9990080, kPlayer, 946001, "dot", "{}", 0);
    EXPECT_TRUE(r.IsActive(9990080, kPlayer, 946001));
}

TEST(WMEffectRegistry, TimedNotYetExpiredStillActive)
{
    auto& r = WMEffectRegistry::Instance();
    r.Register(5406, 9990090, kPlayer, 946001, "dot", "{}", /*sec*/ 3600);
    r.ExpireOverdue();
    EXPECT_TRUE(r.IsActive(9990090, kPlayer, 946001));
}

// The one timing-dependent case: a 1s effect is gone after ExpireOverdue
// once wall-clock passes it. Generous 2s margin keeps it deterministic.
// (Deterministic sub-second expiry would need a clock seam — that is a
// behavior change, out of Phase 0 scope; Python ActiveEffectTracker
// already covers injectable-now expiry logic.)
TEST(WMEffectRegistry, ExpireOverdueRemovesElapsed)
{
    auto& r = WMEffectRegistry::Instance();
    r.Register(5406, 9990100, kPlayer, 946001, "dot", "{}", /*sec*/ 1);
    EXPECT_TRUE(r.IsActive(9990100, kPlayer, 946001));
    std::this_thread::sleep_for(std::chrono::milliseconds(2000));
    uint32 removed = r.ExpireOverdue();
    EXPECT_TRUE(removed >= 1);
    EXPECT_FALSE(r.IsActive(9990100, kPlayer, 946001));
}
