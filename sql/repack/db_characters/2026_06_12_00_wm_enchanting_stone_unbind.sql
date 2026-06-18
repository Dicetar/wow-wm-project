-- WM reusable system consumables are global/unbound; clear soulbound from existing copies.
UPDATE item_instance
SET flags = flags & 4294967294
WHERE itemEntry IN (910007, 910008, 910009, 910014, 910015)
  AND (flags & 1) <> 0;
