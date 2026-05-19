#include "wm_bridge_json.h"

#include <sstream>

namespace WmBridge
{
    std::string EscapeForJson(std::string const& value)
    {
        std::ostringstream out;
        for (unsigned char ch : value)
        {
            switch (ch)
            {
                case '\\':
                    out << "\\\\";
                    break;
                case '"':
                    out << "\\\"";
                    break;
                case '\b':
                    out << "\\b";
                    break;
                case '\f':
                    out << "\\f";
                    break;
                case '\n':
                    out << "\\n";
                    break;
                case '\r':
                    out << "\\r";
                    break;
                case '\t':
                    out << "\\t";
                    break;
                default:
                    if (ch < 0x20)
                    {
                        out << ' ';
                    }
                    else
                    {
                        out << static_cast<char>(ch);
                    }
                    break;
            }
        }

        return out.str();
    }
}
