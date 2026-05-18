from __future__ import annotations

import json
import unittest

from wm.living.catalog import (
    WILD_FEATURES,
    build_wild_feature_catalog,
    dry_run_all,
    main,
    validate_wild_catalog,
)
from wm.sources.native_bridge.action_kinds import NATIVE_ACTION_KIND_BY_ID


class WildCatalogTests(unittest.TestCase):
    def test_all_verbs_are_registered(self) -> None:
        for f in WILD_FEATURES:
            for v in f.verbs:
                self.assertIn(v, NATIVE_ACTION_KIND_BY_ID, f"{f.key} -> {v}")

    def test_validate_clean(self) -> None:
        self.assertEqual(validate_wild_catalog(), [])

    def test_catalog_shape_and_live_ready_honest(self) -> None:
        cat = build_wild_feature_catalog()
        self.assertEqual(cat["count"], len(WILD_FEATURES))
        by = {e["key"]: e for e in cat["entries"]}
        self.assertTrue(by["living.rumor"]["live_ready"])  # announce-only
        self.assertFalse(by["living.nemesis"]["live_ready"])  # Batch 1 C++ pending
        self.assertEqual(cat["live_ready_count"], sum(1 for e in cat["entries"] if e["live_ready"]))

    def test_dry_run_all_every_plan_contract_clean(self) -> None:
        res = dry_run_all()
        self.assertTrue(res["ok"], res)
        # Every wild feature's representative trigger is eligible and clean.
        self.assertTrue(all(r["eligible"] for r in res["results"]), res)
        self.assertEqual(len(res["results"]), len(WILD_FEATURES))

    def test_cli_list_validate_dryrun(self) -> None:
        self.assertEqual(main(["--validate"]), 0)
        self.assertEqual(main(["--dry-run-all"]), 0)
        self.assertEqual(main(["--json"]), 0)

    def test_catalog_json_serializable(self) -> None:
        json.dumps(build_wild_feature_catalog())


if __name__ == "__main__":
    unittest.main()
