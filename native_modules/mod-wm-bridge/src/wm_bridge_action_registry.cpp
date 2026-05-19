#include "wm_bridge_action_registry.h"

namespace WmBridge
{
    void ActionRegistry::Register(std::string const& kind, ActionHandler fn)
    {
        if (kind.empty() || fn == nullptr)
        {
            return;
        }

        m_handlers[kind] = fn;
    }

    ActionHandler ActionRegistry::Find(std::string const& kind) const
    {
        auto it = m_handlers.find(kind);
        return it == m_handlers.end() ? nullptr : it->second;
    }

    bool ActionRegistry::Has(std::string const& kind) const
    {
        return m_handlers.find(kind) != m_handlers.end();
    }

    std::vector<std::string> ActionRegistry::Kinds() const
    {
        std::vector<std::string> kinds;
        kinds.reserve(m_handlers.size());
        for (auto const& entry : m_handlers)
        {
            kinds.push_back(entry.first);
        }

        return kinds;
    }

    std::size_t ActionRegistry::Size() const
    {
        return m_handlers.size();
    }
}
