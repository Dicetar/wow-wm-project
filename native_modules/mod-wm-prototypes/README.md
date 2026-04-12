# mod-wm-prototypes

Legacy WM prototype incubator.

This module is no longer the intended implementation path for WM-owned summons or new abilities. It contains older carrier-hijack experiments that were useful for learning core behavior, but they are not isolated enough for stable live use.

## Current status

- state: legacy / experimental
- default: disabled
- intended usage: postmortem reference and scratch-only lab work

Do not extend this module for the main summon lane.

## Why it was demoted

The previous summon experiments reused stock spell IDs such as warlock and ghoul-style summon carriers. That caused multiple failure modes:

- stock summon behavior leaked through
- saved pet rows polluted retests
- normal class summons were unintentionally altered
- some carrier paths produced hostile or otherwise incorrect creatures
- client-facing spell identity was never truly isolated

Those problems are architectural, not just tuning bugs.

## Replacement path

The stable path is now:

- player-facing shell bank:
  - [D:/WOW/wm-project/control/runtime/spell_shell_bank.json](D:/WOW/wm-project/control/runtime/spell_shell_bank.json)
  - [D:/WOW/wm-project/client_patches/wm_spell_shell_bank/README.md](D:/WOW/wm-project/client_patches/wm_spell_shell_bank/README.md)
- native behavior runtime:
  - [D:/WOW/wm-project/native_modules/mod-wm-spells/README.md](D:/WOW/wm-project/native_modules/mod-wm-spells/README.md)
- operator/content surface:
  - [D:/WOW/wm-project/src/wm/content/workbench.py](D:/WOW/wm-project/src/wm/content/workbench.py)

## If you need to inspect the old work

Relevant files:

- [D:/WOW/wm-project/native_modules/mod-wm-prototypes/src/wm_prototype_spell_scripts.cpp](D:/WOW/wm-project/native_modules/mod-wm-prototypes/src/wm_prototype_spell_scripts.cpp)
- [D:/WOW/wm-project/native_modules/mod-wm-prototypes/conf/mod_wm_prototypes.conf.dist](D:/WOW/wm-project/native_modules/mod-wm-prototypes/conf/mod_wm_prototypes.conf.dist)
- [D:/WOW/wm-project/docs/ON_THE_FLY_SPELLS_V1.md](D:/WOW/wm-project/docs/ON_THE_FLY_SPELLS_V1.md)
- [D:/WOW/wm-project/docs/SPELL_SHELL_BANK_V1.md](D:/WOW/wm-project/docs/SPELL_SHELL_BANK_V1.md)

Treat them as historical context, not as an implementation recipe.

For the current success/failure map of the summon lane, see:

- [D:/WOW/wm-project/docs/SUMMON_SPELL_PLATFORM_STATUS.md](D:/WOW/wm-project/docs/SUMMON_SPELL_PLATFORM_STATUS.md)
