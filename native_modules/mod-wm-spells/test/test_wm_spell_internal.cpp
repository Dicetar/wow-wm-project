#include "wm_test.h"
#include "wm_spell_internal.h"

// Phase 0E.1 characterization of the SHARED JSON config extractors
// (now in WmSpells::detail after the 0E.3 extraction). These assertions
// encode the CURRENT behavior verbatim — the regression net for the
// remaining 0E family moves. Pure std::regex logic; no engine.

using namespace WmSpells::detail;

TEST(ExtractJsonString, PresentSimple)
{
    auto v = ExtractJsonString("{\"name\":\"Bonebound\"}", "name");
    EXPECT_TRUE(v.has_value());
    EXPECT_TRUE(*v == "Bonebound");
}

TEST(ExtractJsonString, AbsentIsNullopt)
{
    EXPECT_FALSE(ExtractJsonString("{\"other\":\"x\"}", "name").has_value());
}

TEST(ExtractJsonString, WhitespaceAroundColon)
{
    auto v = ExtractJsonString("{ \"name\" :   \"Echo Restorer\" }", "name");
    EXPECT_TRUE(v.has_value());
    EXPECT_TRUE(*v == "Echo Restorer");
}

TEST(ExtractJsonString, EmptyStringValue)
{
    auto v = ExtractJsonString("{\"name\":\"\"}", "name");
    EXPECT_TRUE(v.has_value());
    EXPECT_TRUE(*v == "");
}

TEST(ExtractJsonString, FirstMatchWins)
{
    auto v = ExtractJsonString("{\"k\":\"a\",\"k\":\"b\"}", "k");
    EXPECT_TRUE(v.has_value());
    EXPECT_TRUE(*v == "a");
}

TEST(ExtractJsonUInt, PositiveInteger)
{
    auto v = ExtractJsonUInt("{\"creature_entry\":920100}", "creature_entry");
    EXPECT_TRUE(v.has_value());
    EXPECT_TRUE(*v == 920100u);
}

TEST(ExtractJsonUInt, NegativeClampsToZero)
{
    // Current behavior: a negative integer is clamped to 0u (not nullopt).
    auto v = ExtractJsonUInt("{\"x\":-5}", "x");
    EXPECT_TRUE(v.has_value());
    EXPECT_TRUE(*v == 0u);
}

TEST(ExtractJsonUInt, AbsentIsNullopt)
{
    EXPECT_FALSE(ExtractJsonUInt("{\"y\":1}", "x").has_value());
}

TEST(ExtractJsonUInt, MatchesIntegerPartOfDecimal)
{
    // Pattern is (-?\d+); for "3.5" it matches the leading "3".
    auto v = ExtractJsonUInt("{\"n\":3.5}", "n");
    EXPECT_TRUE(v.has_value());
    EXPECT_TRUE(*v == 3u);
}

TEST(ExtractJsonFloat, DecimalValue)
{
    auto v = ExtractJsonFloat("{\"scale\":0.005}", "scale");
    EXPECT_TRUE(v.has_value());
    EXPECT_TRUE(*v > 0.0049f && *v < 0.0051f);
}

TEST(ExtractJsonFloat, IntegerAsFloat)
{
    auto v = ExtractJsonFloat("{\"r\":35}", "r");
    EXPECT_TRUE(v.has_value());
    EXPECT_TRUE(*v > 34.99f && *v < 35.01f);
}

TEST(ExtractJsonFloat, NegativeDecimal)
{
    auto v = ExtractJsonFloat("{\"o\":-2.25}", "o");
    EXPECT_TRUE(v.has_value());
    EXPECT_TRUE(*v < -2.24f && *v > -2.26f);
}

TEST(ExtractJsonBool, TrueAndFalse)
{
    auto t = ExtractJsonBool("{\"persist\":true}", "persist");
    auto f = ExtractJsonBool("{\"persist\":false}", "persist");
    EXPECT_TRUE(t.has_value() && *t == true);
    EXPECT_TRUE(f.has_value() && *f == false);
}

TEST(ExtractJsonBool, AbsentIsNullopt)
{
    EXPECT_FALSE(ExtractJsonBool("{\"persist\":1}", "persist").has_value());
}

TEST(ExtractJsonUIntArray, ParsesNumbers)
{
    auto v = ExtractJsonUIntArray("{\"ids\":[18842, 22800,19909]}", "ids");
    EXPECT_TRUE(v.has_value());
    EXPECT_TRUE(v->size() == 3);
    EXPECT_TRUE((*v)[0] == 18842u);
    EXPECT_TRUE((*v)[1] == 22800u);
    EXPECT_TRUE((*v)[2] == 19909u);
}

TEST(ExtractJsonUIntArray, EmptyArrayIsEmptyVector)
{
    auto v = ExtractJsonUIntArray("{\"ids\":[]}", "ids");
    EXPECT_TRUE(v.has_value());
    EXPECT_TRUE(v->empty());
}

TEST(ExtractJsonUIntArray, AbsentIsNullopt)
{
    EXPECT_FALSE(ExtractJsonUIntArray("{\"other\":[1]}", "ids").has_value());
}
