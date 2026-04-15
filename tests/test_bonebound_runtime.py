import unittest
from pathlib import Path


class BoneboundRuntimeStaticTests(unittest.TestCase):
    def test_omega_final_health_is_applied_after_stat_recalculation(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        runtime = repo_root.joinpath(
            "native_modules",
            "mod-wm-spells",
            "src",
            "wm_spell_runtime.cpp",
        ).read_text(encoding="utf-8")
        helper_start = runtime.index("void ApplyBoneboundOmegaRuntime")
        helper_end = runtime.index("WmSpells::BoneboundBehaviorConfig DefaultBoneboundBehaviorConfig")
        helper = runtime[helper_start:helper_end]

        self.assertLess(helper.index("ApplyOwnerTransferBonuses(omega"), helper.index("ApplyOmegaHealth("))
        self.assertLess(helper.index("ApplyOmegaHealth("), helper.index("omega->SetBaseWeaponDamage"))
        self.assertIn("ResolveOmegaMaxHealth(alphaPet, config)", helper)
        self.assertNotIn("omega->SetMaxHealth(alphaPet->GetMaxHealth())", runtime)


if __name__ == "__main__":
    unittest.main()
