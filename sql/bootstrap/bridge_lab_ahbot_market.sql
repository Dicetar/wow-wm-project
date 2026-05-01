-- BridgeLab AHBot shared market profile.
-- Shared faction auction routes faction auctioneers to Neutral, so only Neutral
-- should carry stock. Alliance/Horde rows stay present but disabled.

START TRANSACTION;

INSERT INTO mod_auctionhousebot (auctionhouse, name, minitems, maxitems)
VALUES
    (2, 'Alliance', 0, 0),
    (6, 'Horde', 0, 0),
    (7, 'Neutral', 40000, 40000)
ON DUPLICATE KEY UPDATE
    name = VALUES(name);

UPDATE mod_auctionhousebot
SET
    minpricegrey = 70,
    maxpricegrey = 120,
    minpricewhite = 70,
    maxpricewhite = 120,
    minpricegreen = 70,
    maxpricegreen = 120,
    minpriceblue = 70,
    maxpriceblue = 120,
    minpricepurple = 70,
    maxpricepurple = 120,
    minpriceorange = 70,
    maxpriceorange = 120,
    minpriceyellow = 70,
    maxpriceyellow = 120,
    minbidpricegrey = 70,
    maxbidpricegrey = 100,
    minbidpricewhite = 70,
    maxbidpricewhite = 100,
    minbidpricegreen = 70,
    maxbidpricegreen = 100,
    minbidpriceblue = 70,
    maxbidpriceblue = 100,
    minbidpricepurple = 70,
    maxbidpricepurple = 100,
    minbidpriceorange = 70,
    maxbidpriceorange = 100,
    minbidpriceyellow = 70,
    maxbidpriceyellow = 100
WHERE auctionhouse IN (2, 6, 7);

UPDATE mod_auctionhousebot
SET
    minitems = 0,
    maxitems = 0
WHERE auctionhouse IN (2, 6);

UPDATE mod_auctionhousebot
SET
    minitems = 40000,
    maxitems = 40000,
    percentgreytradegoods = 0,
    percentwhitetradegoods = 27,
    percentgreentradegoods = 12,
    percentbluetradegoods = 10,
    percentpurpletradegoods = 1,
    percentorangetradegoods = 0,
    percentyellowtradegoods = 0,
    percentgreyitems = 0,
    percentwhiteitems = 10,
    percentgreenitems = 30,
    percentblueitems = 8,
    percentpurpleitems = 2,
    percentorangeitems = 0,
    percentyellowitems = 0
WHERE auctionhouse = 7;

INSERT IGNORE INTO mod_auctionhousebot_disabled_items (item)
SELECT entry
FROM item_template
WHERE BuyPrice < 2
  AND SellPrice < 2
UNION
SELECT entry
FROM item_template
WHERE Quality = 0
   OR class IN (12, 13, 15)
   OR entry >= 900000
   OR name LIKE '%Deprecated%'
   OR name LIKE '%TEST%'
   OR name LIKE '%NPC Equip%';

COMMIT;
