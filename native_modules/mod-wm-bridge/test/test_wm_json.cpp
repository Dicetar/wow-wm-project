#include "wm_test.h"
#include "wm_bridge_json.h"

using WmBridge::EscapeForJson;

// Characterization of the CANONICAL escaper (= old common.cpp behavior,
// which is the correct one). Where the old action_queue.cpp escaper
// differed, the difference is the documented Phase 0B bugfix; the old
// (wrong) output is noted in a comment next to the assertion.

TEST(EscapeForJson, EmptyIsEmpty)
{
    EXPECT_TRUE(EscapeForJson("") == "");
}

TEST(EscapeForJson, PlainAsciiPassthrough)
{
    EXPECT_TRUE(EscapeForJson("hello world 123") == "hello world 123");
}

TEST(EscapeForJson, QuoteEscaped)
{
    EXPECT_TRUE(EscapeForJson("a\"b") == "a\\\"b");
}

TEST(EscapeForJson, BackslashEscaped)
{
    EXPECT_TRUE(EscapeForJson("a\\b") == "a\\\\b");
}

TEST(EscapeForJson, NewlineCrTab)
{
    EXPECT_TRUE(EscapeForJson("\n") == "\\n");
    EXPECT_TRUE(EscapeForJson("\r") == "\\r");
    EXPECT_TRUE(EscapeForJson("\t") == "\\t");
}

TEST(EscapeForJson, BackspaceFormfeedEscaped)
{
    // Canonical: \b and \f are escaped.
    // OLD action_queue.cpp produced a single space for both (bug).
    EXPECT_TRUE(EscapeForJson("\b") == "\\b");
    EXPECT_TRUE(EscapeForJson("\f") == "\\f");
}

TEST(EscapeForJson, OtherControlBecomesSpace)
{
    std::string in;
    in.push_back('\x01');
    in.push_back('\x1f');
    EXPECT_TRUE(EscapeForJson(in) == "  ");
}

TEST(EscapeForJson, Utf8BytesPassthrough)
{
    // "cafe" + U+00E9 (e-acute) = 63 61 66 C3 A9. Canonical keeps the
    // multi-byte sequence intact. OLD action_queue.cpp turned C3 and A9
    // into spaces ("caf  ") because it iterated signed char (bug).
    std::string cafe;
    cafe += "caf";
    cafe.push_back(static_cast<char>(0xC3));
    cafe.push_back(static_cast<char>(0xA9));
    std::string out = EscapeForJson(cafe);
    EXPECT_TRUE(out.size() == 5);
    EXPECT_TRUE(static_cast<unsigned char>(out[3]) == 0xC3);
    EXPECT_TRUE(static_cast<unsigned char>(out[4]) == 0xA9);
}

TEST(EscapeForJson, CombinedMatrix)
{
    std::string in = "x\"y\\z\n\t";
    EXPECT_TRUE(EscapeForJson(in) == "x\\\"y\\\\z\\n\\t");
}
