from __future__ import annotations

import os
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any, Iterable
import webbrowser

from wm.autoplay.state import AutoplayStateStore
from wm.llm.lmstudio import LmStudioClient, LmStudioSettings
from wm.panel.state import PanelState


DEFAULT_DB_PORT = 33307
DEFAULT_SOAP_PORT = 7879
DEFAULT_PANEL_HOST = "127.0.0.1"
DEFAULT_PANEL_PORT = 8765


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_bridge_lab_root(project_root: Path | None = None) -> Path:
    root = project_root or default_project_root()
    return root.parent / "WM_BridgeLab"


def resolve_python_exe(project_root: Path | None = None) -> str:
    root = project_root or default_project_root()
    venv_python = root / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable or "python"


def resolve_player_guid(project_root: Path | None = None) -> int | None:
    for name in ("WM_PLAYER_GUID", "WM_AUTOPLAY_PLAYER_GUID"):
        value = os.getenv(name)
        if value not in (None, ""):
            try:
                guid = int(value)
            except ValueError:
                continue
            if guid > 0:
                return guid

    root = project_root or default_project_root()
    try:
        status = AutoplayStateStore(root / ".wm-bootstrap" / "state" / "autoplay").load_status()
    except Exception:
        return None
    guid = _nested(status, "active_session", "character_guid")
    try:
        parsed = int(guid)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


@dataclass(frozen=True, slots=True)
class LauncherConfig:
    project_root: Path
    bridge_lab_root: Path
    python_exe: str
    player_guid: int | None = None
    db_port: int = DEFAULT_DB_PORT
    soap_port: int = DEFAULT_SOAP_PORT
    panel_host: str = DEFAULT_PANEL_HOST
    panel_port: int = DEFAULT_PANEL_PORT
    watcher_interval_seconds: float = 1.0
    autoplay_interval_seconds: float = 2.0
    autoplay_lanes: str = "chat"
    autoplay_events_per_tick: int = 1
    reactive_auto_bounty_enabled: bool = True

    @classmethod
    def defaults(cls) -> "LauncherConfig":
        project_root = default_project_root()
        return cls(
            project_root=project_root,
            bridge_lab_root=default_bridge_lab_root(project_root),
            python_exe=resolve_python_exe(project_root),
            player_guid=resolve_player_guid(project_root),
        )

    @property
    def panel_url(self) -> str:
        return f"http://{self.panel_host}:{self.panel_port}"

    @property
    def bridge_config_path(self) -> Path:
        return self.bridge_lab_root / "run" / "configs" / "modules" / "mod_wm_bridge.conf"


@dataclass(frozen=True, slots=True)
class LaunchCommand:
    key: str
    title: str
    argv: tuple[str, ...]
    cwd: Path
    runner_path: Path
    script_lines: tuple[str, ...]

    def as_text(self) -> str:
        return " ".join(self.argv) + "\n" + "\n".join(self.script_lines)


def cmd_quote(value: str | Path | int | float) -> str:
    raw = str(value)
    return '"' + raw.replace('"', '""') + '"'


def _cmd_set(name: str, value: str | Path | int | float) -> str:
    return f'set "{name}={value}"'


def _python_segment(config: LauncherConfig, module: str, *args: str | Path | int | float) -> str:
    rendered = [cmd_quote(config.python_exe), "-m", module]
    rendered.extend(cmd_quote(arg) if _needs_quotes(arg) else str(arg) for arg in args)
    return " ".join(rendered)


def _needs_quotes(value: str | Path | int | float) -> bool:
    text = str(value)
    return not text or any(ch.isspace() for ch in text) or any(ch in text for ch in "&()[]{}^=;!'+,`~")


def _visible_console(
    key: str,
    title: str,
    cwd: Path,
    segments: Iterable[str],
    *,
    runner_root: Path,
) -> LaunchCommand:
    runner_path = runner_root / ".wm-bootstrap" / "state" / "launcher" / f"{key}.bat"
    script_lines = ("@echo off", f"title {title}", *tuple(segments))
    return LaunchCommand(
        key=key,
        title=title,
        argv=("cmd.exe", "/k", str(runner_path)),
        cwd=cwd,
        runner_path=runner_path,
        script_lines=script_lines,
    )


def _runtime_env_segments(config: LauncherConfig) -> list[str]:
    return [
        _cmd_set("PYTHONPATH", "src"),
        _cmd_set("WM_WORLD_DB_PORT", config.db_port),
        _cmd_set("WM_CHAR_DB_PORT", config.db_port),
        _cmd_set("WM_SOAP_PORT", config.soap_port),
        _cmd_set("WM_SOAP_ENABLED", "1"),
    ]


def build_db_command(config: LauncherConfig) -> LaunchCommand:
    script = config.project_root / "start-bridge-lab-mysql.bat"
    return _visible_console(
        "db",
        "WM BridgeLab MySQL",
        config.project_root,
        [
            f"{cmd_quote(script)} -WorkspaceRoot {cmd_quote(config.bridge_lab_root)} -Port {config.db_port}",
        ],
        runner_root=config.project_root,
    )


def build_core_command(config: LauncherConfig) -> LaunchCommand:
    return _visible_console(
        "core",
        "WM BridgeLab Core",
        config.project_root,
        [" ".join(_core_start_command(config, quote_paths=True))],
        runner_root=config.project_root,
    )


def build_server_menu_command(config: LauncherConfig) -> LaunchCommand:
    script = config.project_root / "start-bridge-lab-server.bat"
    return _visible_console(
        "server_menu",
        "WM Server Menu",
        config.project_root,
        [cmd_quote(script)],
        runner_root=config.project_root,
    )


def build_auth_command(config: LauncherConfig) -> LaunchCommand:
    run_dir = config.bridge_lab_root / "run"
    auth_exe = run_dir / "bin" / "authserver.exe"
    return _visible_console(
        "auth",
        "WM Auth Server",
        run_dir,
        [
            f"cd /d {cmd_quote(run_dir)}",
            f"{cmd_quote(auth_exe)} -c configs\\authserver.conf",
        ],
        runner_root=config.project_root,
    )


def build_world_command(config: LauncherConfig) -> LaunchCommand:
    run_dir = config.bridge_lab_root / "run"
    world_exe = run_dir / "bin" / "worldserver.exe"
    return _visible_console(
        "world",
        "WM World Server",
        run_dir,
        [
            f"cd /d {cmd_quote(run_dir)}",
            f"{cmd_quote(world_exe)} -c configs\\worldserver.conf",
        ],
        runner_root=config.project_root,
    )


def build_watcher_command(config: LauncherConfig) -> LaunchCommand:
    args: list[str | Path | int | float] = [
        "--adapter",
        "native_bridge",
        "--mode",
        "apply",
        "--summary",
        "--interval-seconds",
        config.watcher_interval_seconds,
        "--batch-size",
        1,
        "--confirm-live-apply",
        "--print-idle",
    ]
    if config.player_guid is not None:
        args[4:4] = ["--player-guid", config.player_guid]
    return _visible_console(
        "watcher",
        "WM Native Watcher",
        config.project_root,
        [
            *_runtime_env_segments(config),
            _cmd_set("WM_BRIDGE_CONFIG_PATH", config.bridge_config_path),
            _cmd_set("WM_QUEST_GRANT_TRANSPORT", "auto"),
            _cmd_set(
                "WM_REACTIVE_AUTO_BOUNTY_ENABLED",
                "1" if config.reactive_auto_bounty_enabled else "0",
            ),
            f"cd /d {cmd_quote(config.project_root)}",
            _python_segment(config, "wm.events.watch", *args),
        ],
        runner_root=config.project_root,
    )


def build_autoplay_command(config: LauncherConfig) -> LaunchCommand:
    args: list[str | Path | int | float] = [
        "run",
        "--project-root",
        config.project_root,
        "--lab-mysql-port",
        config.db_port,
        "--soap-port",
        config.soap_port,
        "--interval-seconds",
        config.autoplay_interval_seconds,
        "--no-start-watcher",
        "--llm-lanes",
        config.autoplay_lanes,
        "--llm-events-per-tick",
        config.autoplay_events_per_tick,
        "--summary",
    ]
    if config.player_guid is not None:
        args[7:7] = ["--player-guid", config.player_guid]
    return _visible_console(
        "autoplay",
        "WM Autoplay",
        config.project_root,
        [
            *_runtime_env_segments(config),
            f"cd /d {cmd_quote(config.project_root)}",
            _python_segment(config, "wm.autoplay", *args),
        ],
        runner_root=config.project_root,
    )


def build_panel_command(config: LauncherConfig) -> LaunchCommand:
    return _visible_console(
        "panel",
        "WM Panel Server",
        config.project_root,
        [
            _cmd_set("PYTHONPATH", "src"),
            f"cd /d {cmd_quote(config.project_root)}",
            _python_segment(config, "wm.panel", "serve", "--host", config.panel_host, "--port", config.panel_port),
        ],
        runner_root=config.project_root,
    )


def build_start_all_commands(config: LauncherConfig) -> list[LaunchCommand]:
    return [
        build_core_command(config),
    ]


def _core_start_command(config: LauncherConfig, *, quote_paths: bool = False) -> list[str]:
    script = config.project_root / "scripts" / "bridge_lab" / "Start-BridgeLabAll.ps1"

    def path_arg(path: Path) -> str:
        return cmd_quote(path) if quote_paths else str(path)

    args = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        path_arg(script),
        "-ProjectRoot",
        path_arg(config.project_root),
        "-BridgeLabRoot",
        path_arg(config.bridge_lab_root),
    ]
    if config.player_guid is not None:
        args.extend(["-PlayerGuid", str(config.player_guid)])
    args.extend([
        "-Watcher",
        "none",
        "-LabMySqlPort",
        str(config.db_port),
        "-SoapPort",
        str(config.soap_port),
    ])
    return args


def run_core_start(config: LauncherConfig, *, timeout_seconds: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        _core_start_command(config),
        cwd=str(config.project_root),
        env=control_env(config),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )


def build_visible_runtime_commands(config: LauncherConfig) -> dict[str, LaunchCommand]:
    return {
        "core": build_core_command(config),
        "db": build_db_command(config),
        "server_menu": build_server_menu_command(config),
        "auth": build_auth_command(config),
        "world": build_world_command(config),
        "watcher": build_watcher_command(config),
        "autoplay": build_autoplay_command(config),
        "panel": build_panel_command(config),
    }


FORBIDDEN_VISIBLE_RUNTIME_TOKENS = ("WindowStyle Hidden", "/MIN", "start-wm-playable.bat")


def assert_visible_runtime_command(command: LaunchCommand) -> None:
    text = command.as_text()
    for token in FORBIDDEN_VISIBLE_RUNTIME_TOKENS:
        if token.lower() in text.lower():
            raise ValueError(f"{command.key} command contains forbidden hidden-launch token: {token}")


def launch_visible(command: LaunchCommand) -> subprocess.Popen[bytes]:
    assert_visible_runtime_command(command)
    _write_runner(command)
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    return subprocess.Popen(["cmd.exe", "/k", str(command.runner_path)], cwd=str(command.cwd), creationflags=flags)


def _write_runner(command: LaunchCommand) -> None:
    command.runner_path.parent.mkdir(parents=True, exist_ok=True)
    text = "\r\n".join(command.script_lines) + "\r\n"
    command.runner_path.write_text(text, encoding="utf-8")


def control_env(config: LauncherConfig) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "PYTHONPATH": "src",
            "WM_WORLD_DB_PORT": str(config.db_port),
            "WM_CHAR_DB_PORT": str(config.db_port),
            "WM_SOAP_PORT": str(config.soap_port),
            "WM_SOAP_ENABLED": "1",
            "WM_BRIDGE_CONFIG_PATH": str(config.bridge_config_path),
        }
    )
    return env


def run_control_python(config: LauncherConfig, *args: str, timeout_seconds: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [config.python_exe, *args],
        cwd=str(config.project_root),
        env=control_env(config),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )


def _process_count_by_commandline(needles: Iterable[str]) -> int | None:
    needles = [item for item in needles if item]
    if os.name != "nt":
        return None
    script = (
        "$needles=ConvertFrom-Json $env:WM_LAUNCHER_NEEDLES;"
        "if ($needles -is [string]) { $needles=@($needles) };"
        "$items=Get-CimInstance Win32_Process | Where-Object { "
        "$cmd=$_.CommandLine; $cmd -and "
        "(@($needles | Where-Object { $cmd -like ('*' + $_ + '*') }).Count -eq @($needles).Count) "
        "};"
        "$ids=@{}; $items | ForEach-Object { $ids[[int]$_.ProcessId]=$true };"
        "$roots=$items | Where-Object { -not $ids.ContainsKey([int]$_.ParentProcessId) };"
        "($roots | Measure-Object).Count"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            env={**os.environ, "WM_LAUNCHER_NEEDLES": json.dumps(needles)},
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return None
    try:
        return int((result.stdout or "0").strip() or "0")
    except ValueError:
        return None


def _stop_processes_by_commandline(needles: Iterable[str]) -> subprocess.CompletedProcess[str]:
    needles = [item for item in needles if item]
    script = (
        "$needles=ConvertFrom-Json $env:WM_LAUNCHER_NEEDLES;"
        "if ($needles -is [string]) { $needles=@($needles) };"
        "$items=Get-CimInstance Win32_Process | Where-Object { "
        "$cmd=$_.CommandLine; $cmd -and "
        "(@($needles | Where-Object { $cmd -like ('*' + $_ + '*') }).Count -eq @($needles).Count) "
        "};"
        "$items | ForEach-Object { Stop-Process -Id $_.ProcessId -Force };"
        "'stopped=' + (($items | Measure-Object).Count)"
    )
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        env={**os.environ, "WM_LAUNCHER_NEEDLES": json.dumps(needles)},
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def _stop_processes_matching_any(needles: Iterable[str]) -> subprocess.CompletedProcess[str]:
    needles = [item for item in needles if item]
    script = (
        "$needles=ConvertFrom-Json $env:WM_LAUNCHER_NEEDLES;"
        "if ($needles -is [string]) { $needles=@($needles) };"
        "$items=Get-CimInstance Win32_Process | Where-Object { "
        "$cmd=$_.CommandLine; $cmd -and "
        "(@($needles | Where-Object { $cmd -like ('*' + $_ + '*') }).Count -gt 0) "
        "};"
        "$items | ForEach-Object { Stop-Process -Id $_.ProcessId -Force };"
        "'stopped=' + (($items | Measure-Object).Count)"
    )
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        env={**os.environ, "WM_LAUNCHER_NEEDLES": json.dumps(needles)},
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def summarize_launcher_status(config: LauncherConfig) -> dict[str, str]:
    autoplay = AutoplayStateStore(config.project_root / ".wm-bootstrap" / "state" / "autoplay").load_status()
    panel_settings = PanelState(config.project_root / ".wm-bootstrap" / "state" / "control-panel").load_settings()
    llm_model = _first_text(
        _nested(autoplay, "llm", "model"),
        _nested(autoplay, "config", "llm_model"),
        panel_settings.get("model"),
        "(not configured)",
    )
    blockers = list(_nested(autoplay, "readiness", "blockers") or [])
    latest_issue = _latest_issue(autoplay)
    latest_blocker = ", ".join(str(item) for item in blockers[:3]) if blockers else latest_issue or "none"

    watcher_count = _process_count_by_commandline(["wm.events.watch", "native_bridge"])
    autoplay_count = _process_count_by_commandline(["wm.autoplay", "run"])
    panel_count = _process_count_by_commandline(["wm.panel", "serve"])
    auth_count = _process_count_by_commandline(["authserver.exe"])
    world_count = _process_count_by_commandline(["worldserver.exe"])
    if not autoplay_count:
        latest_blocker = "none"

    return {
        "DB": f"BridgeLab MySQL 127.0.0.1:{config.db_port}",
        "SOAP": f"enabled on 127.0.0.1:{config.soap_port}",
        "Auth": _process_label(auth_count),
        "World": _process_label(world_count),
        "Watcher": _process_label(watcher_count),
        "Autoplay": _autoplay_label(autoplay, autoplay_count),
        "LM Studio": f"model={llm_model}",
        "Panel": f"{config.panel_url} ({_process_label(panel_count)})",
        "Player": str(_nested(autoplay, "active_session", "character_guid") or config.player_guid or "(unset)"),
        "Latest Blocker": latest_blocker,
    }


def _nested(raw: dict[str, Any], *keys: str) -> Any:
    current: Any = raw
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _first_text(*values: Any) -> str:
    for value in values:
        if value not in (None, ""):
            return str(value)
    return ""


def _latest_issue(status: dict[str, Any]) -> str | None:
    issues = status.get("issues")
    if not isinstance(issues, list) or not issues:
        return None
    latest = issues[0]
    if not isinstance(latest, dict):
        return str(latest)
    reason = latest.get("reason") or latest.get("error") or latest.get("message")
    return str(reason) if reason not in (None, "") else None


def _process_label(count: int | None) -> str:
    if count is None:
        return "unknown"
    if count <= 0:
        return "not detected"
    return f"running ({count})"


def _autoplay_label(status: dict[str, Any], process_count: int | None) -> str:
    if process_count is not None and process_count <= 0:
        return "not running"
    state = str(status.get("status") or "unknown")
    running = bool(status.get("running"))
    paused = bool(status.get("paused"))
    readiness = "ready" if bool(_nested(status, "readiness", "ok")) else "not ready"
    process = _process_label(process_count)
    if paused:
        return f"paused, {readiness}, {process}"
    if running:
        return f"{state}, {readiness}, {process}"
    return f"{state}, {readiness}, {process}"


def probe_lm_studio(config: LauncherConfig) -> str:
    panel_settings = PanelState(config.project_root / ".wm-bootstrap" / "state" / "control-panel").load_settings()
    settings = LmStudioSettings.from_dict({**panel_settings, "timeout_seconds": 3})
    try:
        models = LmStudioClient(settings).list_models()
    except Exception as exc:
        return f"unreachable: {exc}"
    selected = settings.model or "(not configured)"
    if not models:
        return f"reachable, no models listed, selected={selected}"
    loaded = selected if selected in models else f"{selected} (not in /models)"
    return f"reachable, selected={loaded}, available={len(models)}"


def _panel_state(config: LauncherConfig) -> PanelState:
    return PanelState(config.project_root / ".wm-bootstrap" / "state" / "control-panel")


def _autoplay_store(config: LauncherConfig) -> AutoplayStateStore:
    return AutoplayStateStore(config.project_root / ".wm-bootstrap" / "state" / "autoplay")


def list_lm_studio_models(config: LauncherConfig) -> list[str]:
    panel_settings = _panel_state(config).load_settings()
    settings = LmStudioSettings.from_dict({**panel_settings, "timeout_seconds": 3})
    try:
        return [str(model) for model in LmStudioClient(settings).list_models()]
    except Exception:
        return []


def current_lm_studio_model(config: LauncherConfig) -> str | None:
    autoplay = _autoplay_store(config).load_status()
    panel_settings = _panel_state(config).load_settings()
    for value in (
        _nested(autoplay, "config", "llm_model"),
        _nested(autoplay, "llm", "model"),
        panel_settings.get("model"),
    ):
        if value not in (None, ""):
            return str(value)
    return None


def set_lm_studio_model(config: LauncherConfig, model: str) -> dict[str, Any]:
    """Persist the chosen model the same way the panel does: save it to panel
    settings and push it into the autoplay command store (which takes precedence)."""
    chosen = str(model).strip()
    if not chosen:
        raise ValueError("model must be a non-empty string")
    panel_state = _panel_state(config)
    settings = panel_state.load_settings()
    settings["model"] = chosen
    saved = panel_state.save_settings(settings)
    status = _autoplay_store(config).configure({"llm_model": chosen})
    return {"model": chosen, "panel_settings": saved, "autoplay": status}


class WmLauncherApp:
    def __init__(self, tk_root: Any, config: LauncherConfig) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.ttk = ttk
        self.root = tk_root
        self.config = config
        self.commands = build_visible_runtime_commands(config)
        self.status_vars: dict[str, Any] = {}
        self.output_var = tk.StringVar(value="Ready.")

        self.root.title("WM Launcher")
        self.root.geometry("820x520")
        self.root.minsize(760, 460)

        frame = ttk.Frame(self.root, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        title = ttk.Label(frame, text="World Master Launcher", font=("Segoe UI", 16, "bold"))
        title.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))

        rows = ["DB", "SOAP", "Auth", "World", "Watcher", "Autoplay", "LM Studio", "Panel", "Player", "Latest Blocker"]
        for index, label in enumerate(rows, start=1):
            ttk.Label(frame, text=label).grid(row=index, column=0, sticky="nw", padx=(0, 12), pady=2)
            value = tk.StringVar(value="checking...")
            self.status_vars[label] = value
            ttk.Label(frame, textvariable=value, wraplength=560).grid(row=index, column=1, columnspan=3, sticky="ew", pady=2)

        model_frame = ttk.Frame(frame)
        model_frame.grid(row=11, column=0, columnspan=4, sticky="ew", pady=(12, 0))
        model_frame.columnconfigure(1, weight=1)
        ttk.Label(model_frame, text="Model").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.model_var = tk.StringVar(value="")
        self.model_combo = ttk.Combobox(model_frame, textvariable=self.model_var, state="readonly", values=[])
        self.model_combo.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(model_frame, text="Refresh Models", command=self.refresh_models).grid(
            row=0, column=2, sticky="ew", padx=3
        )
        ttk.Button(model_frame, text="Set Model", command=self.set_model).grid(row=0, column=3, sticky="ew", padx=3)

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=12, column=0, columnspan=4, sticky="ew", pady=(14, 8))
        for col in range(4):
            button_frame.columnconfigure(col, weight=1)

        buttons = [
            ("Start Core", self.start_core),
            ("Run Doctor", self.run_doctor),
            ("Start Panel", lambda: self.launch_once("panel", ["wm.panel", "serve"])),
            ("Open Panel", self.open_panel),
            ("Start Watcher", lambda: self.launch_once("watcher", ["wm.events.watch", "native_bridge"])),
            ("Stop Watcher", self.stop_watcher),
            ("Start Autoplay", lambda: self.launch_once("autoplay", ["wm.autoplay", "run"])),
            ("Pause/Resume Autoplay", self.toggle_autoplay_pause),
            ("Stop Autoplay", self.stop_autoplay),
            ("Close Aux Windows", self.close_aux_windows),
            ("Refresh Status", self.refresh_status),
        ]
        for index, (text, command) in enumerate(buttons):
            row = index // 4
            col = index % 4
            ttk.Button(button_frame, text=text, command=command).grid(row=row, column=col, sticky="ew", padx=3, pady=3)

        ttk.Label(frame, textvariable=self.output_var, wraplength=760, justify="left").grid(
            row=13, column=0, columnspan=4, sticky="ew", pady=(8, 0)
        )

        self.refresh_status()
        self.refresh_models()

    def refresh_models(self) -> None:
        def worker() -> None:
            models = list_lm_studio_models(self.config)
            current = current_lm_studio_model(self.config)

            def apply() -> None:
                values = list(models)
                if current and current not in values:
                    values = [current, *values]
                self.model_combo["values"] = values
                if current:
                    self.model_var.set(current)
                elif values:
                    self.model_var.set(values[0])
                if models:
                    self.output_var.set(
                        f"Loaded {len(models)} model(s). Current: {current or '(not configured)'}"
                    )
                else:
                    self.output_var.set("LM Studio unreachable or no models listed.")

            self.root.after(0, apply)

        threading.Thread(target=worker, daemon=True).start()

    def set_model(self) -> None:
        model = (self.model_var.get() or "").strip()
        if not model:
            self.output_var.set("Pick a model first.")
            return
        self.output_var.set(f"Setting model to {model}...")

        def worker() -> None:
            try:
                set_lm_studio_model(self.config, model)
                message = f"Model set to {model}."
            except Exception as exc:
                message = f"Set model failed: {exc}"
            self.root.after(0, lambda: self.output_var.set(message))
            self.root.after(600, self.refresh_status)

        threading.Thread(target=worker, daemon=True).start()

    def launch_key(self, key: str) -> None:
        command = self.commands[key]
        try:
            launch_visible(command)
        except Exception as exc:
            self.output_var.set(f"{command.title} launch failed: {exc}")
            return
        self.output_var.set(f"{command.title} window launched.")
        self.root.after(1200, self.refresh_status)

    def launch_once(self, key: str, needles: list[str]) -> None:
        running = _process_count_by_commandline(needles)
        if running and running > 0:
            self.output_var.set(f"{self.commands[key].title} is already running ({running}).")
            self.refresh_status()
            return
        self.launch_key(key)

    def start_all(self) -> None:
        self.start_core()

    def start_core(self) -> None:
        auth_running = _process_count_by_commandline(["authserver.exe"])
        world_running = _process_count_by_commandline(["worldserver.exe"])
        if auth_running and world_running:
            self.output_var.set("BridgeLab core is already running.")
            self.refresh_status()
            return
        self._run_background("core start", lambda: run_core_start(self.config, timeout_seconds=180))

    def start_auth_world(self) -> None:
        self.start_core()

    def open_panel(self) -> None:
        webbrowser.open(self.config.panel_url)
        self.output_var.set(f"Panel requested at {self.config.panel_url}.")

    def toggle_autoplay_pause(self) -> None:
        status = AutoplayStateStore(self.config.project_root / ".wm-bootstrap" / "state" / "autoplay").load_status()
        command = "resume" if status.get("paused") else "pause"
        self._run_background(
            f"autoplay {command}",
            lambda: run_control_python(self.config, "-m", "wm.autoplay", command, "--summary"),
        )

    def stop_autoplay(self) -> None:
        def worker() -> subprocess.CompletedProcess[str]:
            result = run_control_python(self.config, "-m", "wm.autoplay", "stop", "--summary")
            _stop_processes_matching_any(["wm.autoplay run", "launcher\\autoplay.bat"])
            return result

        self._run_background("autoplay stop", worker)

    def stop_watcher(self) -> None:
        def worker() -> subprocess.CompletedProcess[str]:
            stop_script = self.config.project_root / "stop-bridge-lab-watch.bat"
            if stop_script.exists():
                subprocess.run(
                    [str(stop_script)],
                    cwd=str(self.config.project_root),
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
            return _stop_processes_matching_any(["wm.events.watch", "launcher\\watcher.bat"])

        self._run_background("watcher stop", worker)

    def close_aux_windows(self) -> None:
        def worker() -> subprocess.CompletedProcess[str]:
            run_control_python(self.config, "-m", "wm.autoplay", "stop", "--summary")
            return _stop_processes_matching_any(
                [
                    "wm.autoplay run",
                    "wm.events.watch",
                    "wm.panel serve",
                    "launcher\\autoplay.bat",
                    "launcher\\watcher.bat",
                    "launcher\\panel.bat",
                    "start-wm-panel-app",
                ]
            )

        self._run_background("close aux windows", worker)

    def run_doctor(self) -> None:
        self._run_background(
            "doctor",
            lambda: run_control_python(self.config, "-m", "wm.doctor", "--summary", timeout_seconds=30),
        )

    def refresh_status(self) -> None:
        def worker() -> None:
            try:
                status = summarize_launcher_status(self.config)
                lm = probe_lm_studio(self.config)
                status["LM Studio"] = lm
            except Exception as exc:
                self.root.after(0, lambda: self.output_var.set(f"Status refresh failed: {exc}"))
                return

            def apply() -> None:
                for key, value in status.items():
                    if key in self.status_vars:
                        self.status_vars[key].set(value)
                self.output_var.set("Status refreshed.")

            self.root.after(0, apply)

        threading.Thread(target=worker, daemon=True).start()

    def _run_background(self, label: str, fn: Any) -> None:
        self.output_var.set(f"Running {label}...")

        def worker() -> None:
            try:
                result = fn()
                output = (getattr(result, "stdout", "") or getattr(result, "stderr", "") or "").strip()
                code = getattr(result, "returncode", 0)
                message = f"{label} exit={code}"
                if output:
                    message += f": {output[-700:]}"
            except Exception as exc:
                message = f"{label} failed: {exc}"
            self.root.after(0, lambda: self.output_var.set(message))
            self.root.after(800, self.refresh_status)

        threading.Thread(target=worker, daemon=True).start()


def main(argv: list[str] | None = None) -> int:
    import argparse
    import tkinter as tk

    parser = argparse.ArgumentParser(prog="python -m wm.launcher", description="Open the visible local WM launcher.")
    parser.add_argument("--project-root", type=Path, default=default_project_root())
    parser.add_argument("--bridge-lab-root", type=Path)
    parser.add_argument("--python-exe")
    parser.add_argument("--player-guid", type=int, default=None)
    parser.add_argument("--db-port", type=int, default=DEFAULT_DB_PORT)
    parser.add_argument("--soap-port", type=int, default=DEFAULT_SOAP_PORT)
    parser.add_argument("--panel-host", default=DEFAULT_PANEL_HOST)
    parser.add_argument("--panel-port", type=int, default=DEFAULT_PANEL_PORT)
    args = parser.parse_args(argv)

    project_root = args.project_root.resolve()
    config = LauncherConfig(
        project_root=project_root,
        bridge_lab_root=(args.bridge_lab_root or default_bridge_lab_root(project_root)).resolve(),
        python_exe=args.python_exe or resolve_python_exe(project_root),
        player_guid=args.player_guid or resolve_player_guid(project_root),
        db_port=args.db_port,
        soap_port=args.soap_port,
        panel_host=args.panel_host,
        panel_port=args.panel_port,
    )

    root = tk.Tk()
    WmLauncherApp(root, config)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
