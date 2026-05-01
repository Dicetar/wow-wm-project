from __future__ import annotations

from pathlib import Path
import json
import unittest


class BridgeLabAhBotMarketTests(unittest.TestCase):
    def test_sources_lock_uses_auction_bot_plus_fork(self) -> None:
        sources = json.loads(Path("bootstrap/sources.lock.json").read_text(encoding="utf-8"))
        ahbot = next(module for module in sources["modules"] if module["key"] == "mod-ahbot")

        self.assertEqual(ahbot["repo_url"], "https://github.com/NathanHandley/mod-ah-bot.git")
        self.assertEqual(ahbot["commit"], "1822d96072a5168a775551fa5017ec947c9fbf7b")
        self.assertEqual(ahbot["target_path"], "src/modules/mod-ahbot")

    def test_configure_runtime_enables_shared_ahbot_market(self) -> None:
        script = Path("scripts/bridge_lab/Configure-BridgeLabRuntime.ps1").read_text(encoding="utf-8")

        expected = (
            'Set-ConfigValue -Path $worldConfig -Key "AllowTwoSide.Interaction.Auction" -Value "1"',
            'Set-ConfigValue -Path $worldConfig -Key "Rate.Auction.Deposit" -Value "0.5"',
            'Set-ConfigValue -Path $worldConfig -Key "Rate.Auction.Cut" -Value "0.5"',
            "Ensure-AhBotPlusConfigFile -Path $ahbotConfig -DistPath $ahbotDistConfig",
            'Write-Host "bridge_lab_ahbot_config_rebased=true backup=$backupPath dist=$DistPath"',
            'Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.EnableSeller" -Value "true"',
            'Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.Buyer.Enabled" -Value "true"',
            'Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.GUIDs" -Value "1"',
            'Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.Alliance.MinItems" -Value "0"',
            'Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.Horde.MinItems" -Value "0"',
            'Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.Neutral.MinItems" -Value "40000"',
            'Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.Neutral.MaxItems" -Value "40000"',
            'Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.BuyoutVariationReducePercent" -Value "0.30"',
            'Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.BuyoutVariationAddPercent" -Value "0.20"',
            'Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.BidVariationLowReducePercent" -Value "0.30"',
            'Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.Buyer.BuyCandidatesPerBuyCycle" -Value "25:75"',
            'Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.Buyer.AcceptablePriceModifier" -Value "1.20"',
            'Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.AdvancedListingRules.UseDropRates.Enabled" -Value "true"',
            'Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.DisabledCustomItemIDs" -Value "900000-999999"',
            'Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.EnableBuyer" -Value "1"',
            'Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.UseBuyPriceForSeller" -Value "1"',
            'Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.UseMarketPriceForSeller" -Value "1"',
            'Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.Account" -Value "1"',
            'Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.GUID" -Value "1"',
            'Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.ItemsPerCycle" -Value "2000"',
            'Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.ConsiderOnlyBotAuctions" -Value "1"',
            'Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.ElapsingTimeClass" -Value "0"',
            'Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.VendorItems" -Value "0"',
            'Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.OtherItems" -Value "0"',
            'Set-ConfigValue -Path $ahbotConfig -Key "AuctionHouseBot.ProfessionItems" -Value "0"',
        )

        for snippet in expected:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, script)

        self.assertIn('"Generic", "Recipe", "Quiver", "Quest", "Key", "Misc", "Glyph"', script)
        self.assertIn("AuctionHouseBot.ListProportion.Category$category.Quality$quality", script)
        self.assertIn('"AuctionHouseBot.ListProportion.CategoryArmor.QualityUncommon" = "24"', script)
        self.assertIn('"AuctionHouseBot.ListProportion.CategoryTradeGood.QualityNormal" = "35"', script)

    def test_repack_baseline_uses_same_auction_bot_plus_profile(self) -> None:
        script = Path("scripts/repack/Apply-LatestBaselineConfigDefaults.ps1").read_text(encoding="utf-8")

        expected = (
            '"AuctionHouseBot.GUIDs"                           = "$AhbotGuid"',
            '"AuctionHouseBot.EnableSeller"                    = "true"',
            '"AuctionHouseBot.EnableBuyer"                     = "1"',
            '"AuctionHouseBot.Buyer.Enabled"                   = "true"',
            '"AuctionHouseBot.Neutral.MinItems"                = "40000"',
            '"AuctionHouseBot.Neutral.MaxItems"                = "40000"',
            '"AuctionHouseBot.BuyoutVariationReducePercent"    = "0.30"',
            '"AuctionHouseBot.BuyoutVariationAddPercent"       = "0.20"',
            '"AuctionHouseBot.BidVariationLowReducePercent"    = "0.30"',
            '"AuctionHouseBot.Buyer.AcceptablePriceModifier"   = "1.20"',
            '"AuctionHouseBot.AdvancedListingRules.UseDropRates.Enabled" = "true"',
            '"AuctionHouseBot.DisabledCustomItemIDs"           = "900000-999999"',
            '"AuctionHouseBot.VendorItems"                     = "0"',
            '"AuctionHouseBot.OtherItems"                      = "0"',
            '"AuctionHouseBot.DisableKeys"                     = "1"',
        )

        for snippet in expected:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, script)

        self.assertIn("AuctionHouseBot.ListProportion.Category$category.Quality$quality", script)
        self.assertIn('"AuctionHouseBot.ListProportion.CategoryGlyph.QualityNormal" = "12"', script)

    def test_start_script_applies_ahbot_market_sql(self) -> None:
        script = Path("scripts/bridge_lab/Start-BridgeLabAll.ps1").read_text(encoding="utf-8")

        self.assertIn("[switch]$SkipBridgeLabAhBotMarketSql", script)
        self.assertIn('Join-Path $ProjectRoot "sql\\bootstrap\\bridge_lab_ahbot_market.sql"', script)
        self.assertIn("if (-not $SkipBridgeLabAhBotMarketSql.IsPresent)", script)
        self.assertIn('-Database "acore_world"', script)
        self.assertIn("-SqlPath $bridgeLabAhBotMarketSql", script)

    def test_ahbot_market_sql_pins_shared_neutral_stock_and_prices(self) -> None:
        sql = Path("sql/bootstrap/bridge_lab_ahbot_market.sql").read_text(encoding="utf-8")

        self.assertIn("(7, 'Neutral', 40000, 40000)", sql)
        self.assertIn("WHERE auctionhouse IN (2, 6);", sql)
        self.assertIn("WHERE auctionhouse = 7;", sql)
        self.assertIn("minitems = 40000", sql)
        self.assertIn("maxitems = 40000", sql)
        self.assertIn("INSERT IGNORE INTO mod_auctionhousebot_disabled_items (item)", sql)
        self.assertIn("WHERE BuyPrice < 2", sql)
        self.assertIn("AND SellPrice < 2", sql)
        self.assertIn("OR class IN (12, 13, 15)", sql)
        self.assertIn("OR entry >= 900000", sql)
        self.assertIn("OR name LIKE '%Deprecated%'", sql)

        for quality in ("grey", "white", "green", "blue", "purple", "orange", "yellow"):
            with self.subTest(quality=quality):
                self.assertIn(f"minprice{quality} = 70", sql)
                self.assertIn(f"maxprice{quality} = 120", sql)
                self.assertIn(f"minbidprice{quality} = 70", sql)
                self.assertIn(f"maxbidprice{quality} = 100", sql)

    def test_neutral_distribution_still_sums_to_full_market(self) -> None:
        sql = Path("sql/bootstrap/bridge_lab_ahbot_market.sql").read_text(encoding="utf-8")
        percent_values = {
            "percentgreytradegoods": 0,
            "percentwhitetradegoods": 27,
            "percentgreentradegoods": 12,
            "percentbluetradegoods": 10,
            "percentpurpletradegoods": 1,
            "percentorangetradegoods": 0,
            "percentyellowtradegoods": 0,
            "percentgreyitems": 0,
            "percentwhiteitems": 10,
            "percentgreenitems": 30,
            "percentblueitems": 8,
            "percentpurpleitems": 2,
            "percentorangeitems": 0,
            "percentyellowitems": 0,
        }

        for column, value in percent_values.items():
            with self.subTest(column=column):
                self.assertIn(f"{column} = {value}", sql)
        self.assertEqual(sum(percent_values.values()), 100)
