-- WM Enchanting Stone per-item upgrade persistence.

CREATE TABLE IF NOT EXISTS `wm_item_stat_upgrade` (
  `ItemGuid` int unsigned NOT NULL,
  `UpgradeLevel` tinyint unsigned NOT NULL DEFAULT 0,
  `UpdatedAt` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`ItemGuid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
