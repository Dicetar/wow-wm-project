#pragma once

// Zero-dependency, gtest-API-compatible micro test harness.
// Phase 0 standalone inner loop. The TEST / EXPECT_* surface mirrors
// GoogleTest so porting onto the core unit_tests target later (Task 0A.3)
// is a mechanical `#include` swap.

#include <functional>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace wmtest
{
    struct TestCase
    {
        std::string suite;
        std::string name;
        std::function<void()> fn;
    };

    inline std::vector<TestCase>& registry()
    {
        static std::vector<TestCase> r;
        return r;
    }

    inline int& currentFailures()
    {
        static int f = 0;
        return f;
    }

    struct Registrar
    {
        Registrar(char const* suite, char const* name, std::function<void()> fn)
        {
            registry().push_back({suite, name, std::move(fn)});
        }
    };

    inline int runAll()
    {
        int passed = 0;
        int failed = 0;
        for (auto& tc : registry())
        {
            currentFailures() = 0;
            try
            {
                tc.fn();
            }
            catch (std::exception const& e)
            {
                std::cout << "  threw: " << e.what() << "\n";
                currentFailures() += 1;
            }
            catch (...)
            {
                std::cout << "  threw: unknown\n";
                currentFailures() += 1;
            }

            if (currentFailures() == 0)
            {
                std::cout << "[PASS] " << tc.suite << "." << tc.name << "\n";
                ++passed;
            }
            else
            {
                std::cout << "[FAIL] " << tc.suite << "." << tc.name << "\n";
                ++failed;
            }
        }

        std::cout << "\n"
                  << passed << " passed, " << failed << " failed, "
                  << registry().size() << " total\n";
        return failed;
    }
}

#define TEST(suite, name)                                                     \
    static void wmtest_##suite##_##name();                                    \
    static ::wmtest::Registrar wmtest_reg_##suite##_##name(                    \
        #suite, #name, wmtest_##suite##_##name);                              \
    static void wmtest_##suite##_##name()

#define WM_FAIL_(msg)                                                         \
    do                                                                        \
    {                                                                         \
        ::wmtest::currentFailures() += 1;                                      \
        std::cout << "  " << __FILE__ << ":" << __LINE__ << "  " << msg        \
                  << "\n";                                                     \
    } while (0)

#define EXPECT_TRUE(x)                                                        \
    do                                                                        \
    {                                                                         \
        if (!(x))                                                             \
            WM_FAIL_("EXPECT_TRUE(" #x ")");                                   \
    } while (0)

#define EXPECT_FALSE(x)                                                       \
    do                                                                        \
    {                                                                         \
        if ((x))                                                              \
            WM_FAIL_("EXPECT_FALSE(" #x ")");                                  \
    } while (0)

#define EXPECT_EQ(a, b)                                                       \
    do                                                                        \
    {                                                                         \
        auto _va = (a);                                                       \
        auto _vb = (b);                                                       \
        if (!(_va == _vb))                                                     \
        {                                                                     \
            std::ostringstream _os;                                           \
            _os << "EXPECT_EQ(" #a ", " #b ")  got " << _va << " vs " << _vb;  \
            WM_FAIL_(_os.str());                                              \
        }                                                                     \
    } while (0)

#define EXPECT_NE(a, b)                                                       \
    do                                                                        \
    {                                                                         \
        auto _va = (a);                                                       \
        auto _vb = (b);                                                       \
        if (!(_va != _vb))                                                     \
            WM_FAIL_("EXPECT_NE(" #a ", " #b ")");                             \
    } while (0)
