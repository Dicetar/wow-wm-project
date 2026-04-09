from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from wm.repack.models import ModuleRepoMapping


@dataclass(slots=True)
class CatalogEntry:
    key: str
    display_name: str
    aliases: tuple[str, ...]
    repo_url: str | None
    branch: str | None = None
    commit: str | None = None
    status: str = "verified"
    notes: tuple[str, ...] = ()
    update_markers: tuple[str, ...] = ()


class ModuleCatalog:
    def __init__(self) -> None:
        provided = ("Repo URL provided by the user from the repack module list; exact parity commit still needs later pinning.",)
        self._entries: tuple[CatalogEntry, ...] = (
            CatalogEntry(
                key="mod-playerbots",
                display_name="mod-playerbots",
                aliases=("mod-playerbots", "playerbots", "playerbots.conf"),
                repo_url="https://github.com/mod-playerbots/mod-playerbots.git",
                status="verified",
                notes=("Runtime log directly references github.com/mod-playerbots/mod-playerbots.",),
                update_markers=("playerbot", "ai_playerbot", "bot_reset_guild_tracker", "bot_level_brackets"),
            ),
            CatalogEntry("1v1arena", "1v1arena", ("1v1arena", "1v1arena.conf", "mod-1v1-arena"), "https://github.com/azerothcore/mod-1v1-arena.git", status="candidate", notes=provided),
            CatalogEntry("autobalance", "autobalance", ("autobalance", "autobalance.conf", "mod-autobalance"), "https://github.com/azerothcore/mod-autobalance.git", status="candidate", notes=provided),
            CatalogEntry("autorevive", "autorevive", ("autorevive", "autorevive.conf", "mod-auto-revive"), "https://github.com/azerothcore/mod-auto-revive.git", status="candidate", notes=provided),
            CatalogEntry("bgqueuechecker", "bgqueuechecker", ("bgqueuechecker", "bgqueuechecker.conf"), "https://github.com/AnchyDev/BGQueueChecker.git", status="candidate", notes=provided),
            CatalogEntry("breakingnews", "breakingnews", ("breakingnews", "breakingnews.conf"), "https://github.com/azerothcore/mod-breaking-news-override.git", status="candidate", notes=provided),
            CatalogEntry("cfbg", "cfbg", ("cfbg", "cfbg.conf", "mod-cfbg"), "https://github.com/azerothcore/mod-cfbg.git", status="candidate", notes=provided),
            CatalogEntry("challenge-modes", "challenge-modes", ("challenge-modes", "challenge_modes", "challenge_modes.conf"), "https://github.com/ZhengPeiRu21/mod-challenge-modes.git", status="candidate", notes=provided),
            CatalogEntry("desertion-warnings", "desertion-warnings", ("desertion-warnings", "desertion-warnings.conf"), "https://github.com/azerothcore/mod-desertion-warnings.git", status="candidate", notes=provided),
            CatalogEntry("duelreset", "duelreset", ("duelreset", "duelreset.conf", "mod-duel-reset"), "https://github.com/azerothcore/mod-duel-reset.git", status="candidate", notes=provided),
            CatalogEntry("dynamicxp", "dynamicxp", ("dynamicxp", "dynamicxp.conf", "mod-dynamic-xp"), "https://github.com/azerothcore/mod-dynamic-xp.git", status="candidate", notes=provided),
            CatalogEntry("emblem-transfer", "emblem-transfer", ("emblem-transfer", "emblem_transfer", "emblem_transfer.conf"), "https://github.com/azerothcore/mod-emblem-transfer.git", status="candidate", notes=provided),
            CatalogEntry("mod-fly-anywhere", "mod-fly-anywhere", ("mod-fly-anywhere", "fly-anywhere", "fly-anywhere.conf"), "https://github.com/abracadaniel22/mod-fly-anywhere.git", status="candidate", notes=provided),
            CatalogEntry("individual-xp", "individual-xp", ("individual-xp", "individual_xp", "individual_xp.conf"), "https://github.com/azerothcore/mod-individual-xp.git", status="candidate", notes=provided),
            CatalogEntry(
                key="mod-individual-progression",
                display_name="mod-individual-progression",
                aliases=("mod-individual-progression", "individualprogression", "individualprogression.conf"),
                repo_url="https://github.com/ZhengPeiRu21/mod-individual-progression.git",
                status="candidate",
                notes=provided,
                update_markers=("individualprogression", "player_progression", "quest_xp_table", "vanilla_", "tbc_", "wotlk_", "zone_", "dungeon_", "aq_", "naxx40", "ipp_aware"),
            ),
            CatalogEntry("instance-reset", "instance-reset", ("instance-reset", "instance-reset.conf"), "https://github.com/azerothcore/mod-instance-reset.git", status="candidate", notes=provided),
            CatalogEntry("leech", "leech", ("leech", "leech.conf"), "https://github.com/ZhengPeiRu21/mod-leech.git", status="candidate", notes=provided),
            CatalogEntry("low-level-rbg", "low-level-rbg", ("low-level-rbg", "low_level_rbg", "low_level_rbg.conf"), "https://github.com/azerothcore/mod-low-level-rbg.git", status="candidate", notes=provided),
            CatalogEntry("mod-changeablespawnrates", "mod-changeablespawnrates", ("mod-changeablespawnrates", "mod-changeablespawnrates.conf"), "https://github.com/justin-kaufmann/mod-changeablespawnrates.git", status="candidate", notes=provided),
            CatalogEntry("mod-junk-to-gold", "mod-junk-to-gold", ("mod-junk-to-gold", "mod-junk-to-gold.conf", "junk-to-gold"), "https://github.com/noisiver/mod-junk-to-gold.git", status="candidate", notes=provided),
            CatalogEntry("mod-quest-loot-party", "mod-quest-loot-party", ("mod-quest-loot-party", "mod-quest-loot-party.conf"), "https://github.com/pangolp/mod-quest-loot-party.git", status="candidate", notes=("Repo URL recovered from public GitHub search results; exact parity commit still needs later pinning.",)),
            CatalogEntry("mod-rdf-expansion", "mod-rdf-expansion", ("mod-rdf-expansion", "mod-rdf-expansion.conf"), "https://github.com/azerothcore/mod-rdf-expansion.git", status="candidate", notes=provided),
            CatalogEntry("mod-time-is-time", "mod-time-is-time", ("mod-time-is-time", "mod-time_is_time", "mod-time_is_time.conf", "timeistime"), "https://github.com/dunjeon/mod-TimeIsTime.git", status="candidate", notes=provided),
            CatalogEntry("mod-account-mount", "mod-account-mount", ("mod-account-mount", "mod_account_mount", "mod_account_mount.conf"), "https://github.com/azerothcore/mod-account-mounts.git", status="candidate", notes=provided),
            CatalogEntry("mod-achievements", "mod-achievements", ("mod-achievements", "mod_achievements", "mod_achievements.conf"), "https://github.com/azerothcore/mod-account-achievements.git", status="candidate", notes=provided),
            CatalogEntry("mod-ahbot", "mod-ahbot", ("mod-ahbot", "mod_ahbot", "mod_ahbot.conf"), "https://github.com/azerothcore/mod-ah-bot.git", status="candidate", notes=provided, update_markers=("ahbot", "auctionhousebot")),
            CatalogEntry("mod-aq-war-effort", "mod-aq-war-effort", ("mod-aq-war-effort", "mod_aq_war_effort", "mod_aq_war_effort.conf"), "https://github.com/azerothcore/mod-war-effort.git", status="candidate", notes=provided),
            CatalogEntry("mod-boss-announcer", "mod-boss-announcer", ("mod-boss-announcer", "mod_boss_announcer", "mod_boss_announcer.conf"), "https://github.com/azerothcore/mod-boss-announcer.git", status="candidate", notes=provided),
            CatalogEntry("mod-customserver", "mod-customserver", ("mod-customserver", "mod_customserver", "mod_customserver.conf"), "https://github.com/azerothcore/mod-customserver.git", status="candidate", notes=("Repo URL inferred from naming convention; not in the user-provided list.",)),
            CatalogEntry("mod-dead-means-dead", "mod-dead-means-dead", ("mod-dead-means-dead", "mod_dead_means_dead", "mod_dead_means_dead.conf"), "https://github.com/kjack9/mod-dead-means-dead.git", status="candidate", notes=provided),
            CatalogEntry(
                key="mod-dungeon-master",
                display_name="mod-dungeon-master",
                aliases=("mod-dungeon-master", "mod_dungeon_master", "mod_dungeon_master.conf"),
                repo_url="https://github.com/InstanceForge/mod-dungeon-master.git",
                status="candidate",
                notes=("Repo URL recovered from the public Dungeon Master module announcement; exact parity commit still needs later pinning.",),
                update_markers=("dm_", "dungeonmaster"),
            ),
            CatalogEntry("mod-dynamic-loot-rates", "mod-dynamic-loot-rates", ("mod-dynamic-loot-rates", "mod_dynamic_loot_rates", "mod_dynamic_loot_rates.conf"), "https://github.com/hallgaeuer/mod-dynamic-loot-rates.git", status="candidate", notes=provided),
            CatalogEntry("mod-flightmaster-whistle", "mod-flightmaster-whistle", ("mod-flightmaster-whistle", "mod_flightmaster_whistle", "mod_flightmaster_whistle.conf"), "https://github.com/silviu20092/mod-flightmaster-whistle.git", status="candidate", notes=("Repo URL recovered from public GitHub search results; exact parity commit still needs later pinning.",)),
            CatalogEntry("mod-guildhouse", "mod-guildhouse", ("mod-guildhouse", "mod_guildhouse", "mod_guildhouse.conf"), "https://github.com/azerothcore/mod-guildhouse.git", status="candidate", notes=provided),
            CatalogEntry("mod-improved-bank", "mod-improved-bank", ("mod-improved-bank", "mod_improved_bank", "mod_improved_bank.conf"), "https://github.com/silviu20092/mod-improved-bank.git", status="candidate", notes=provided),
            CatalogEntry("mod-learnspells", "mod-learnspells", ("mod-learnspells", "mod_learnspells", "mod_learnspells.conf"), "https://github.com/noisiver/mod-learnspells.git", status="candidate", notes=provided),
            CatalogEntry("mod-moneyforkills", "mod-moneyforkills", ("mod-moneyforkills", "mod_moneyforkills", "mod_moneyforkills.conf"), "https://github.com/azerothcore/mod-money-for-kills.git", status="candidate", notes=provided),
            CatalogEntry(
                key="mod-mythic-plus",
                display_name="mod-mythic-plus",
                aliases=("mod-mythic-plus", "mod_mythic_plus", "mod_mythic_plus.conf"),
                repo_url="https://github.com/silviu20092/mod-mythic-plus.git",
                status="candidate",
                notes=("Repo URL recovered from the public Mythic Plus module repository; exact parity commit still needs later pinning.",),
                update_markers=("mythic_plus", "_mp_"),
            ),
            CatalogEntry("mod-no-hearthstone-cooldown", "mod-no-hearthstone-cooldown", ("mod-no-hearthstone-cooldown", "mod_no_hearthstone_cooldown", "mod_no_hearthstone_cooldown.conf"), "https://github.com/BytesGalore/mod-no-hearthstone-cooldown.git", status="candidate", notes=provided),
            CatalogEntry("mod-npc-beastmaster", "mod-npc-beastmaster", ("mod-npc-beastmaster", "mod_npc_beastmaster", "mod_npc_beastmaster.conf", "npc_beastmaster", "npc_beastmaster.conf"), "https://github.com/azerothcore/mod-npc-beastmaster.git", status="candidate", notes=provided),
            CatalogEntry("mod-npc-enchanter", "mod-npc-enchanter", ("mod-npc-enchanter", "npc_enchanter", "npc_enchanter.conf"), "https://github.com/azerothcore/mod-npc-enchanter.git", status="candidate", notes=provided),
            CatalogEntry("mod-npc-buffer", "mod-npc-buffer", ("mod-npc-buffer", "npc_buffer", "npc_buffer.conf"), "https://github.com/azerothcore/mod-npc-buffer.git", status="candidate", notes=provided),
            CatalogEntry("mod-npc-free-professions", "mod-npc-free-professions", ("mod-npc-free-professions", "mod_npc_free_professions", "mod_npc_free_professions.conf"), "https://github.com/azerothcore/mod-npc-free-professions.git", status="candidate", notes=provided),
            CatalogEntry("mod-ollama-chat", "mod-ollama-chat", ("mod-ollama-chat", "mod_ollama_chat", "mod_ollama_chat.conf"), "https://github.com/DustinHendrickson/mod-ollama-chat.git", status="candidate", notes=provided, update_markers=("ollama",)),
            CatalogEntry("mod-phased-duels", "mod-phased-duels", ("mod-phased-duels", "mod_phased_duels", "mod_phased_duels.conf"), "https://github.com/azerothcore/mod-phased-duels.git", status="candidate", notes=provided),
            CatalogEntry("mod-player-bot-guildhouse", "mod-player-bot-guildhouse", ("mod-player-bot-guildhouse", "mod_player_bot_guildhouse", "mod_player_bot_guildhouse.conf"), "https://github.com/DustinHendrickson/mod-player-bot-guildhouse.git", status="candidate", notes=provided),
            CatalogEntry("mod-player-bot-level-brackets", "mod-player-bot-level-brackets", ("mod-player-bot-level-brackets", "mod_player_bot_level_brackets", "mod_player_bot_level_brackets.conf"), "https://github.com/DustinHendrickson/mod-player-bot-level-brackets.git", status="candidate", notes=provided, update_markers=("bot_level_brackets",)),
            CatalogEntry("mod-player-bot-reset", "mod-player-bot-reset", ("mod-player-bot-reset", "mod_player_bot_reset", "mod_player_bot_reset.conf"), "https://github.com/DustinHendrickson/mod-player-bot-reset.git", status="candidate", notes=("Repo URL recovered from public GitHub search results; exact parity commit still needs later pinning.",)),
            CatalogEntry("mod-pvptitles", "mod-pvptitles", ("mod-pvptitles", "mod_pvptitles", "mod_pvptitles.conf"), "https://github.com/azerothcore/mod-pvp-titles.git", status="candidate", notes=provided),
            CatalogEntry("mod-weather-vibe", "mod-weather-vibe", ("mod-weather-vibe", "mod_weather_vibe", "mod_weather_vibe.conf"), "https://github.com/hermensbas/mod_weather_vibe.git", status="candidate", notes=provided),
            CatalogEntry("mod-weekendbonus", "mod-weekendbonus", ("mod-weekendbonus", "mod_weekendbonus", "mod_weekendbonus.conf"), "https://github.com/noisiver/mod-weekendbonus.git", status="candidate", notes=("Repo URL recovered from public GitHub search results; exact parity commit still needs later pinning.",)),
            CatalogEntry("mod-top-arena", "mod-top-arena", ("mod-top-arena", "modarenatop", "modarenatop.conf"), "https://github.com/azerothcore/mod-top-arena.git", status="candidate", notes=provided),
            CatalogEntry("morphsummon", "morphsummon", ("morphsummon", "morphsummon.conf"), "https://github.com/azerothcore/mod-morphsummon.git", status="candidate", notes=provided),
            CatalogEntry("npc-spectator", "npc-spectator", ("npc-spectator", "npc_spectator", "npc_spectator.conf"), "https://github.com/Gozzim/mod-npc-spectator.git", status="candidate", notes=provided),
            CatalogEntry("npc-subclass", "npc-subclass", ("npc-subclass", "npc_subclass", "npc_subclass.conf"), "https://github.com/xiii-hearts/mod-npc-subclass.git", status="candidate", notes=("Repo URL recovered from public GitHub search results; exact parity commit still needs later pinning.",)),
            CatalogEntry("npc-talent-template", "npc-talent-template", ("npc-talent-template", "npc_talent_template", "npc_talent_template.conf"), "https://github.com/azerothcore/mod-npc-talent-template.git", status="candidate", notes=provided, update_markers=("npc_talent_template",)),
            CatalogEntry("mod-queue-list-cache", "mod-queue-list-cache", ("mod-queue-list-cache", "queuelistcache", "queuelistcache.conf", "queuelistcache"), "https://github.com/azerothcore/mod-queue-list-cache.git", status="candidate", notes=provided),
            CatalogEntry("mod-quick-teleport", "mod-quick-teleport", ("mod-quick-teleport", "quick-teleport", "quick_teleport", "quick_teleport.conf"), "https://github.com/azerothcore/mod-quick-teleport.git", status="candidate", notes=provided),
            CatalogEntry("mod-racial-trait-swap", "mod-racial-trait-swap", ("mod-racial-trait-swap", "racialtraitswap", "racialtraitswap.conf"), "https://github.com/azerothcore/mod-racial-trait-swap.git", status="candidate", notes=provided),
            CatalogEntry("mod-random-enchants", "mod-random-enchants", ("mod-random-enchants", "random-enchants", "random_enchants", "random_enchants.conf"), "https://github.com/azerothcore/mod-random-enchants.git", status="candidate", notes=provided),
            CatalogEntry("mod-reagent-bank", "mod-reagent-bank", ("mod-reagent-bank", "reagent-bank", "reagent_bank", "reagent_bank.conf"), "https://github.com/ZhengPeiRu21/mod-reagent-bank.git", status="candidate", notes=provided),
            CatalogEntry("mod-reward-system", "mod-reward-system", ("mod-reward-system", "reward-system", "reward_system", "reward_system.conf"), "https://github.com/azerothcore/mod-reward-played-time.git", status="candidate", notes=provided),
            CatalogEntry("mod-server-auto-shutdown", "mod-server-auto-shutdown", ("mod-server-auto-shutdown", "serverautoshutdown", "serverautoshutdown.conf"), "https://github.com/azerothcore/mod-server-auto-shutdown.git", status="candidate", notes=provided),
            CatalogEntry("skip-dk-module", "skip-dk-module", ("skip-dk-module", "skip_dk_module", "skip_dk_module.conf"), "https://github.com/azerothcore/mod-skip-dk-starting-area.git", status="candidate", notes=provided, update_markers=("skip_dk",)),
            CatalogEntry("mod-solo-lfg", "mod-solo-lfg", ("mod-solo-lfg", "sololfg", "sololfg.conf"), "https://github.com/azerothcore/mod-solo-lfg.git", status="candidate", notes=provided),
            CatalogEntry("transmog", "transmog", ("transmog", "transmog.conf"), "https://github.com/azerothcore/mod-transmog.git", status="candidate", notes=provided, update_markers=("trasm", "transmog")),
            CatalogEntry("who-logged", "who-logged", ("who-logged", "who-logged.conf"), "https://github.com/azerothcore/mod-who-logged.git", status="candidate", notes=provided),
        )
        user_provided_repo_keys = {
            "1v1arena",
            "autobalance",
            "autorevive",
            "bgqueuechecker",
            "breakingnews",
            "challenge-modes",
            "mod-account-mount",
            "mod-achievements",
            "mod-ahbot",
            "mod-aq-war-effort",
            "mod-boss-announcer",
            "mod-changeablespawnrates",
            "mod-dead-means-dead",
            "mod-dynamic-loot-rates",
            "mod-fly-anywhere",
            "mod-guildhouse",
            "mod-improved-bank",
            "mod-individual-progression",
            "mod-junk-to-gold",
            "mod-learnspells",
            "mod-moneyforkills",
            "mod-no-hearthstone-cooldown",
            "mod-npc-beastmaster",
            "mod-npc-buffer",
            "mod-npc-enchanter",
            "mod-npc-free-professions",
            "mod-ollama-chat",
            "mod-phased-duels",
            "mod-player-bot-guildhouse",
            "mod-player-bot-level-brackets",
            "mod-pvptitles",
            "mod-queue-list-cache",
            "mod-quick-teleport",
            "mod-racial-trait-swap",
            "mod-random-enchants",
            "mod-rdf-expansion",
            "mod-reagent-bank",
            "mod-reward-system",
            "mod-server-auto-shutdown",
            "mod-solo-lfg",
            "mod-time-is-time",
            "mod-top-arena",
            "mod-weather-vibe",
            "morphsummon",
            "npc-spectator",
            "npc-talent-template",
            "skip-dk-module",
            "transmog",
            "who-logged",
            "cfbg",
            "desertion-warnings",
            "duelreset",
            "dynamicxp",
            "emblem-transfer",
            "individual-xp",
            "instance-reset",
            "leech",
            "low-level-rbg",
        }
        for entry in self._entries:
            if entry.key in user_provided_repo_keys and entry.status == "candidate":
                entry.status = "verified"

    @staticmethod
    def _normalize(token: str) -> str:
        return (
            token.lower()
            .replace(".conf", "")
            .replace(".dist", "")
            .replace("_", "-")
            .replace(" ", "-")
        )

    def match_config_file(self, config_name: str) -> ModuleRepoMapping:
        normalized = self._normalize(config_name)
        if "using-configuration-file" in normalized:
            return ModuleRepoMapping(
                key="ignored-runtime-string",
                display_name="ignored-runtime-string",
                config_files=[config_name],
                repo_url=None,
                status="ignored",
                notes=["Runtime log noise, not a real module config."],
            )
        entry = self._find_entry(normalized)
        if entry is not None:
            return self._mapping_from_entry(entry, config_name=config_name)

        if normalized.startswith("mod-"):
            return ModuleRepoMapping(
                key=normalized,
                display_name=normalized,
                config_files=[config_name],
                repo_url=f"https://github.com/azerothcore/{normalized}.git",
                status="candidate",
                notes=["Repo URL is inferred from the AzerothCore naming convention."],
            )

        return ModuleRepoMapping(
            key=normalized,
            display_name=normalized,
            config_files=[config_name],
            repo_url=f"https://github.com/azerothcore/mod-{normalized}.git",
            status="candidate",
            notes=["Repo URL is inferred from the AzerothCore mod naming convention."],
        )

    def attach_update_markers(
        self,
        mappings: dict[str, ModuleRepoMapping],
        update_names: Iterable[str],
    ) -> list[str]:
        unmatched: list[str] = []
        for name in update_names:
            normalized = name.lower()
            target = self._match_update_name(normalized, mappings)
            if target is None:
                unmatched.append(name)
                continue
            if name not in target.matched_updates:
                target.matched_updates.append(name)
        return unmatched

    def _match_update_name(
        self,
        normalized_update: str,
        mappings: dict[str, ModuleRepoMapping],
    ) -> ModuleRepoMapping | None:
        for entry in self._entries:
            for marker in entry.update_markers:
                if marker and marker.lower() in normalized_update:
                    mapping = mappings.get(entry.key)
                    if mapping is None:
                        mapping = self._mapping_from_entry(entry, config_name=None)
                        mappings[entry.key] = mapping
                    return mapping
        return None

    def _find_entry(self, normalized_token: str) -> CatalogEntry | None:
        for entry in self._entries:
            if normalized_token == entry.key:
                return entry
            if normalized_token in {self._normalize(alias) for alias in entry.aliases}:
                return entry
        return None

    @staticmethod
    def _mapping_from_entry(entry: CatalogEntry, *, config_name: str | None) -> ModuleRepoMapping:
        config_files: list[str] = []
        if config_name:
            config_files.append(config_name)
        return ModuleRepoMapping(
            key=entry.key,
            display_name=entry.display_name,
            config_files=config_files,
            repo_url=entry.repo_url,
            branch=entry.branch,
            commit=entry.commit,
            status=entry.status,
            notes=list(entry.notes),
        )
