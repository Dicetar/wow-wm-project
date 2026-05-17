"""Living World Memory features (grand plan Phase C).

Each feature is pure composition of proven primitives:
`trigger -> Python decision/state -> typed native action / shell -> client tier`.
Scaffolds are deterministic and dry-run only; nothing here mutates game state
or calls the coordinator. Native verbs they compose may still be
`not_implemented` in C++ (lab-gated) without affecting plan validity.
"""
