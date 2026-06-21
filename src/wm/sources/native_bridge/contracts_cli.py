"""Lint native action payload-contract coverage (offline, CI-able).

Reports how many of the registered native action kinds have an enforceable
payload contract, lists the gaps, and fails (exit 1) on orphan contracts
(a contract for a kind that is not registered) since that is a real defect.
"""

from __future__ import annotations

import argparse
import json
import sys

from wm.sources.native_bridge.payload_contract import audit_contract_coverage
from wm.sources.native_bridge.action_kinds import NATIVE_ACTION_KIND_BY_ID

_FREEFORM_OK = {"context_snapshot_request"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wm native.contracts", description="Audit native payload-contract coverage.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    cov = audit_contract_coverage()
    debug_uncontracted = [k for k in cov.uncontracted if NATIVE_ACTION_KIND_BY_ID[k].category == "debug"]
    product_unimplemented = [
        k for k in cov.uncontracted
        if NATIVE_ACTION_KIND_BY_ID[k].category != "debug" and not NATIVE_ACTION_KIND_BY_ID[k].implemented
    ]
    impl_gap = [
        k for k in cov.implemented_without_contract
        if k not in _FREEFORM_OK and NATIVE_ACTION_KIND_BY_ID[k].category != "debug"
    ]

    if args.json:
        print(json.dumps({
            **cov.to_dict(),
            "debug_uncontracted": debug_uncontracted,
            "product_unimplemented": product_unimplemented,
            "implemented_contract_gap": impl_gap,
        }, indent=2))
    else:
        print(f"native action kinds   : {cov.total_kinds}")
        print(f"contracted            : {len(cov.contracted)}")
        print(f"uncontracted          : {len(cov.uncontracted)}")
        print(f"orphan contracts      : {cov.orphan_contracts or '(none)'}")
        print(f"implemented w/o contr.: {impl_gap or '(none, debug/freeform excluded)'}")
        if debug_uncontracted:
            print(f"\ndebug/freeform kinds ({len(debug_uncontracted)}; contracts intentionally optional):")
            for k in debug_uncontracted:
                print(f"  - {k}")
        if product_unimplemented:
            print(f"\nforward-declared product kinds ({len(product_unimplemented)}; no executor, no contract):")
            for k in product_unimplemented:
                print(f"  - {k}")

    # Orphans or implemented-without-contract are real defects; backlog is not.
    return 1 if (cov.orphan_contracts or impl_gap) else 0


if __name__ == "__main__":
    sys.exit(main())
