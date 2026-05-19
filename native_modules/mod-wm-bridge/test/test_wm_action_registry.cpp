#include "wm_test.h"
#include "wm_bridge_action_registry.h"

using WmBridge::ActionRegistry;

namespace
{
    bool HandlerA(uint64, uint32, std::string const&, std::string const&) { return true; }
    bool HandlerB(uint64, uint32, std::string const&, std::string const&) { return true; }
}

TEST(ActionRegistry, FindMissingReturnsNull)
{
    ActionRegistry r;
    EXPECT_TRUE(r.Find("nope") == nullptr);
    EXPECT_FALSE(r.Has("nope"));
}

TEST(ActionRegistry, RegisterThenFind)
{
    ActionRegistry r;
    r.Register("a", &HandlerA);
    EXPECT_TRUE(r.Find("a") == &HandlerA);
    EXPECT_TRUE(r.Has("a"));
    EXPECT_TRUE(r.Size() == 1);
}

TEST(ActionRegistry, NullAndEmptyIgnored)
{
    ActionRegistry r;
    r.Register("a", nullptr);
    r.Register("", &HandlerA);
    EXPECT_TRUE(r.Size() == 0);
}

TEST(ActionRegistry, LastRegistrationWins)
{
    ActionRegistry r;
    r.Register("a", &HandlerA);
    r.Register("a", &HandlerB);
    EXPECT_TRUE(r.Find("a") == &HandlerB);
    EXPECT_TRUE(r.Size() == 1);
}

TEST(ActionRegistry, KindsListsAll)
{
    ActionRegistry r;
    r.Register("a", &HandlerA);
    r.Register("b", &HandlerB);
    auto kinds = r.Kinds();
    EXPECT_TRUE(kinds.size() == 2);
    bool hasA = false, hasB = false;
    for (auto const& k : kinds)
    {
        if (k == "a") hasA = true;
        if (k == "b") hasB = true;
    }
    EXPECT_TRUE(hasA);
    EXPECT_TRUE(hasB);
}

TEST(ActionRegistry, DispatchInvokesHandler)
{
    ActionRegistry r;
    r.Register("a", &HandlerA);
    WmBridge::ActionHandler h = r.Find("a");
    EXPECT_TRUE(h != nullptr);
    EXPECT_TRUE(h(1, 2, "a", "{}"));
}
