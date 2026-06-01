from __future__ import annotations

from pathlib import Path

from wm.launcher import FORBIDDEN_VISIBLE_RUNTIME_TOKENS
from wm.launcher import LauncherConfig
from wm.launcher import build_autoplay_command
from wm.launcher import build_start_all_commands
from wm.launcher import build_visible_runtime_commands
from wm.launcher import build_watcher_command


def _config(tmp_path: Path) -> LauncherConfig:
    project = tmp_path / "wm-project"
    lab = tmp_path / "WM_BridgeLab"
    project.mkdir()
    lab.mkdir()
    return LauncherConfig(
        project_root=project,
        bridge_lab_root=lab,
        python_exe=str(project / ".venv" / "Scripts" / "python.exe"),
        player_guid=5408,
    )


def test_visible_runtime_commands_use_cmd_windows(tmp_path: Path):
    commands = build_visible_runtime_commands(_config(tmp_path))

    assert {"core", "db", "server_menu", "auth", "world", "watcher", "autoplay", "panel"} <= set(commands)
    for command in commands.values():
        assert command.argv[0].lower() == "cmd.exe"
        assert command.argv[1].lower() == "/k"
        assert command.title.startswith("WM ")


def test_core_command_starts_bridge_lab_without_watcher(tmp_path: Path):
    command = build_visible_runtime_commands(_config(tmp_path))["core"]
    rendered = command.as_text()

    assert "Start-BridgeLabAll.ps1" in rendered
    assert "-Watcher none" in rendered
    assert "wm.events.watch" not in rendered
    assert "wm.autoplay" not in rendered
    assert "Start-Process" not in rendered


def test_watcher_enables_reactive_auto_bounty_by_default(tmp_path: Path):
    rendered = build_watcher_command(_config(tmp_path)).as_text()

    assert 'set "WM_REACTIVE_AUTO_BOUNTY_ENABLED=1"' in rendered


def test_watcher_can_disable_reactive_auto_bounty(tmp_path: Path):
    config = _config(tmp_path)
    config = LauncherConfig(
        project_root=config.project_root,
        bridge_lab_root=config.bridge_lab_root,
        python_exe=config.python_exe,
        player_guid=config.player_guid,
        reactive_auto_bounty_enabled=False,
    )
    rendered = build_watcher_command(config).as_text()

    assert 'set "WM_REACTIVE_AUTO_BOUNTY_ENABLED=0"' in rendered


def test_autoplay_launches_python_directly_instead_of_hidden_helper(tmp_path: Path):
    command = build_autoplay_command(_config(tmp_path))
    rendered = command.as_text()

    assert "wm.autoplay" in rendered
    assert "--no-start-watcher" in rendered
    assert "start-wm-playable.bat" not in rendered
    assert "WindowStyle Hidden" not in rendered
    assert "/MIN" not in rendered


def test_start_all_runtime_commands_do_not_hide_or_minimize(tmp_path: Path):
    commands = build_start_all_commands(_config(tmp_path))
    rendered = "\n".join(command.as_text() for command in commands)

    for token in FORBIDDEN_VISIBLE_RUNTIME_TOKENS:
        assert token.lower() not in rendered.lower()
    assert "Start-BridgeLabAll.ps1" in rendered
    assert "wm.events.watch" not in rendered
    assert "wm.autoplay" not in rendered
