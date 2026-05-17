from __future__ import annotations

import runpy
import sys

# Curated discovery catalog grouped by area. This is for `wm --list` only;
# dispatch works for any importable `wm.*` module, so the catalog drifting
# out of date degrades discovery, never execution.
CATALOG: dict[str, list[tuple[str, str]]] = {
    "control": [
        ("control.inspect", "Inspect what an event can trigger"),
        ("control.new", "Build a manual control proposal"),
        ("control.validate", "Validate a control proposal"),
        ("control.apply", "Dry-run or apply a control proposal"),
        ("control.audit", "Inspect wm_control_proposal audit rows"),
        ("control.scene_play", "Play a bundled scene through the coordinator"),
        ("control.manual_grant_quest", "Manual quest-grant proposal shortcut"),
        ("control.manual_announce", "Manual announce proposal shortcut"),
        ("control.manual_noop", "Manual observe-only proposal shortcut"),
    ],
    "events": [
        ("events.watch", "Run the live event watcher"),
    ],
    "reactive": [
        ("reactive.install_bounty", "Install a reusable reactive bounty"),
        ("reactive.auto_bounty", "Manage the opt-in dynamic auto-bounty lane"),
    ],
    "content": [
        ("content.release", "Render/plan/packet a content release spec"),
        ("content.playcycle", "Run a managed content playcycle"),
        ("content.preflight", "Arc-specific release preflight checks"),
        ("content.workbench", "Managed item/spell/shell workbench"),
    ],
    "quests": [
        ("quests.publish", "Publish a managed quest"),
        ("quests.live_publish", "Live-publish a quest"),
        ("quests.rollback", "Roll back a published quest"),
        ("quests.edit_live", "Edit a live quest"),
        ("quests.generate_bounty", "Generate a bounty quest draft"),
        ("quests.context_builder", "Build quest generation context"),
    ],
    "items": [
        ("items.publish", "Publish a managed item"),
        ("items.live_publish", "Live-publish an item"),
        ("items.rollback", "Roll back a published item"),
    ],
    "spells": [
        ("spells.publish", "Publish a managed spell"),
        ("spells.live_publish", "Live-publish a spell"),
        ("spells.rollback", "Roll back a published spell"),
        ("spells.client_patch", "Build/install the client spell patch"),
        ("spells.server_dbc", "Materialize server Spell.dbc rows"),
        ("spells.shell_audit", "Audit a shell-bank spell"),
        ("spells.shield_proficiency", "Grant scoped combat proficiencies"),
        ("spells.summon_release", "Fast Bonebound Alpha release submitter"),
        ("spells.broug_guard", "Broug guard arc tooling"),
        ("spells.broug_lightness", "Broug lightness arc tooling"),
        ("spells.export_patch_plan", "Export a client patch plan"),
    ],
    "arcs": [
        ("arcs.factory", "Arc + reward factory"),
        ("arcs.scaffold", "Scaffold a new arc's standard files/gates"),
    ],
    "character": [
        ("character.journey", "Inspect/apply the personal journey spine"),
    ],
    "context": [
        ("context.builder", "Build a deterministic context pack"),
        ("context.snapshot", "Request a native context snapshot"),
    ],
    "subjects": [
        ("subjects.inspect", "Inspect a resolved subject card"),
    ],
    "journal": [
        ("journal.inspect", "Inspect journal rows for a player/subject"),
    ],
    "candidates": [
        ("candidates.release_pack", "Build a release-candidate pack (supported lane)"),
        ("candidates.demo", "V1 candidate demo (baseline)"),
        ("candidates.demo_ranked_v4", "V4 ranked candidate demo (canonical)"),
    ],
    "sources": [
        ("sources.native_bridge.configure", "Configure native bridge player scope"),
        ("sources.native_bridge.actions_cli", "Submit/scope native bridge actions"),
        ("sources.native_bridge.player_marker", "Discover/scope a player by marker aura"),
    ],
    "bridge_lab": [
        ("bridge_lab.release_gate", "Print the ordered BridgeLab release plan"),
    ],
    "live": [
        ("live.proof_packet", "Print live proof steps for an arc"),
    ],
    "reserved": [
        ("reserved.commands", "Reserved-slot allocator commands"),
        ("reserved.seed", "Seed reserved id ranges"),
    ],
}


def _print_catalog() -> None:
    print("wm - World Master CLI\n")
    print("Usage:")
    print("  wm <command> [args...]      run an entrypoint (e.g. `wm control.inspect --event-id 1`)")
    print("  wm --list                   show this catalog")
    print()
    print("Any importable `wm.*` module also dispatches, e.g. `wm targets.demo_runtime_profile`.")
    print("Equivalent to `python -m wm.<command>`.\n")
    for area, entries in CATALOG.items():
        print(f"{area}:")
        for name, desc in entries:
            print(f"  {name:<38} {desc}")
        print()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help", "--list", "list"}:
        _print_catalog()
        return 0

    name = argv[0]
    rest = argv[1:]
    module = name if name.startswith("wm.") else f"wm.{name}"

    # runpy executes the module exactly as `python -m <module>` would,
    # so any existing __main__ guard / package __main__.py keeps working.
    sys.argv = [module, *rest]
    try:
        runpy.run_module(module, run_name="__main__", alter_sys=True)
    except ImportError as exc:
        # runpy wraps a missing target module in ImportError (not always
        # ModuleNotFoundError). Only treat it as "unknown command" when the
        # failing module is the dispatch target itself, not a transitive import.
        if module in str(exc):
            print(f"wm: unknown command '{name}'. Run `wm --list` for available commands.", file=sys.stderr)
            return 2
        raise
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
