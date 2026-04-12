param(
    [string]$WorkspaceRoot = "D:\WOW\WM_BridgeLab",
    [string]$Configuration = "RelWithDebInfo",
    [int]$GracefulWaitSeconds = 20,
    [int]$ForceAfterSeconds = 5
)

$ErrorActionPreference = "Stop"

function Set-ConfigValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Key,
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Config file not found: $Path"
    }

    $content = Get-Content -LiteralPath $Path -Raw
    $escapedKey = [regex]::Escape($Key)
    $line = "$Key = $Value"
    $pattern = "(?m)^\s*$escapedKey\s*=.*$"
    $regex = [regex]::new($pattern)

    if ($regex.IsMatch($content)) {
        $content = $regex.Replace($content, $line, 1)
    } else {
        $content = $content.TrimEnd() + "`r`n" + $line + "`r`n"
    }

    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($Path, $content, $utf8NoBom)
}

function Get-LabWorldProcess {
    param([string]$ExecutablePath)

    return Get-Process worldserver -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -ieq $ExecutablePath } |
        Select-Object -First 1
}

$buildExe = Join-Path $WorkspaceRoot ("build\bin\" + $Configuration + "\worldserver.exe")
$runRoot = Join-Path $WorkspaceRoot "run"
$runExe = Join-Path $runRoot "bin\worldserver.exe"
$spellsConfig = Join-Path $runRoot "configs\modules\mod_wm_spells.conf"

foreach ($required in @($buildExe, $runExe, $spellsConfig)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required path not found: $required"
    }
}
Set-ConfigValue -Path $spellsConfig -Key "WmSpells.Enable" -Value "1"
Set-ConfigValue -Path $spellsConfig -Key "WmSpells.BoneboundServant.Enable" -Value "1"
Set-ConfigValue -Path $spellsConfig -Key "WmSpells.BoneboundServant.ShellSpellIds" -Value '"940000"'
Write-Host "bridge_lab_shell_module=mod-wm-spells shell_spell_ids=940000"

$existing = Get-LabWorldProcess -ExecutablePath $runExe
if ($null -ne $existing) {
    $gracefulRequested = $false
    if ($existing.MainWindowHandle -ne 0) {
        try {
            $gracefulRequested = $existing.CloseMainWindow()
        } catch {
            $gracefulRequested = $false
        }
    }

    if ($gracefulRequested) {
        Write-Host "bridge_lab_worldserver_shutdown=graceful_requested pid=$($existing.Id)"
        $deadline = (Get-Date).AddSeconds([Math]::Max(1, $GracefulWaitSeconds))
        while ((Get-Date) -lt $deadline) {
            Start-Sleep -Milliseconds 500
            if (-not (Get-LabWorldProcess -ExecutablePath $runExe)) {
                break
            }
        }
    }

    $existing = Get-LabWorldProcess -ExecutablePath $runExe
    if ($null -ne $existing) {
        Write-Host "bridge_lab_worldserver_shutdown=force pid=$($existing.Id)"
        Stop-Process -Id $existing.Id -Force
        Start-Sleep -Seconds ([Math]::Max(1, $ForceAfterSeconds))
    }
}

Copy-Item -LiteralPath $buildExe -Destination $runExe -Force
Write-Host "bridge_lab_worldserver_copied=true source=$buildExe destination=$runExe"

$started = Start-Process -FilePath $runExe -WorkingDirectory $runRoot -ArgumentList "-c", "configs\worldserver.conf" -PassThru
Start-Sleep -Seconds 2

Write-Host "bridge_lab_worldserver_started=true pid=$($started.Id) exe=$runExe"
