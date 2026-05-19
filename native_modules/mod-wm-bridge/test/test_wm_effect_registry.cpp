#include "wm_test.h"
#include "wm_effect_registry.h"

using WmBridge::WMEffectRegistry;

TEST(WMEffectRegistry, IsActiveFalseWhenUnregistered)
{
    auto& r = WMEffectRegistry::Instance();
    EXPECT_FALSE(r.IsActive(/*guid*/ 9990001, /*player*/ true, /*spell*/ 946001));
}
