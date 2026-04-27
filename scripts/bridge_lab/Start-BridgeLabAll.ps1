param(
    [string]$ProjectRoot = "D:\WOW\wm-project",
    [string]$BridgeLabRoot = "D:\WOW\WM_BridgeLab",
    [int]$PlayerGuid = 5406,
    [int]$LabMySqlPort = 33307,
    [int]$WorldServerPort = 8095,
    [int]$SoapPort = 7879,
    [string]$DataDir = "D:\WOW\Azerothcore_WoTLK_Rebuild\run\data",
    [ValidateSet("auto-bounty", "native", "none")]
    [string]$Watcher = "auto-bounty",
    [switch]$RestartWorldServer,
    [switch]$ConfigureRuntime,
    [switch]$SkipConfigure,
    [switch]$ResetBountyRules,
    [switch]$KeepExistingEventBacklog,
    [switch]$DisableRandomEnchantOnKill,
    [switch]$SkipPlayerbotsDatabaseSync,
    [switch]$ConfigOnly,
    [switch]$PrintIdle,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Resolve-ExistingPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Label was not found: $Path"
    }

    return (Resolve-Path -LiteralPath $Path).Path
}

function Get-ExecutableProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProcessName,
        [Parameter(Mandatory = $true)]
        [string]$ExecutablePath
    )

    return Get-Process $ProcessName -ErrorAction SilentlyContinue |
        Where-Object {
            try {
                $_.Path -ieq $ExecutablePath
            } catch {
                $false
            }
        } |
        Select-Object -First 1
}

function Invoke-BridgeLabScript {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [string[]]$Arguments = @()
    )

    $powershellExe = Join-Path $PSHOME "powershell.exe"
    $command = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $Path) + $Arguments

    if ($DryRun.IsPresent) {
        Write-Host "dry_run_script=$Path args=$($Arguments -join ' ')"
        return
    }

    & $powershellExe @command
    if ($LASTEXITCODE -ne 0) {
        throw "BridgeLab helper failed with exit code $LASTEXITCODE`: $Path"
    }
}

function Read-ConfigText {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $bytes = [System.IO.File]::ReadAllBytes($Path)
    $utf8Strict = [System.Text.UTF8Encoding]::new($false, $true)
    try {
        return $utf8Strict.GetString($bytes)
    } catch {
        return [System.Text.Encoding]::Default.GetString($bytes)
    }
}

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

    $content = Read-ConfigText -Path $Path
    $escapedKey = [regex]::Escape($Key)
    $line = "$Key = $Value"
    $pattern = "(?m)^\s*$escapedKey\s*=.*$"
    $regex = [regex]::new($pattern)
    $originalContent = $content

    if ($regex.IsMatch($content)) {
        $content = $regex.Replace($content, $line, 1)
    } else {
        $content = $content.TrimEnd() + "`r`n" + $line + "`r`n"
    }

    if ($content -ne $originalContent) {
        if ($DryRun.IsPresent) {
            Write-Host "dry_run_config_update=$Path key=$Key value=$Value"
            return
        }

        $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
        [System.IO.File]::WriteAllText($Path, $content, $utf8NoBom)
    }
}

function Sync-PlayerbotsDatabaseInfo {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ConfigPath,
        [Parameter(Mandatory = $true)]
        [int]$Port
    )

    if (-not (Test-Path -LiteralPath $ConfigPath)) {
        Write-Host "bridge_lab_playerbots_db_sync=false reason=missing_config path=$ConfigPath"
        return
    }

    $playerbotsDb = """127.0.0.1;$Port;acore;acore;acore_playerbots"""
    Set-ConfigValue -Path $ConfigPath -Key "PlayerbotsDatabaseInfo" -Value $playerbotsDb
    Write-Host "bridge_lab_playerbots_db_sync=true path=$ConfigPath port=$Port"
}

function Start-LabServerProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$ProcessName,
        [Parameter(Mandatory = $true)]
        [string]$ExecutablePath,
        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,
        [Parameter(Mandatory = $true)]
        [string]$ConfigPath
    )

    $existing = Get-ExecutableProcess -ProcessName $ProcessName -ExecutablePath $ExecutablePath
    if ($null -ne $existing) {
        Write-Host "bridge_lab_$($Name)_started=true already_running=true pid=$($existing.Id)"
        return
    }

    if ($DryRun.IsPresent) {
        Write-Host "dry_run_start=$Name exe=$ExecutablePath config=$ConfigPath"
        return
    }

    $process = Start-Process -FilePath $ExecutablePath -WorkingDirectory $WorkingDirectory -ArgumentList "-c", $ConfigPath -PassThru
    Start-Sleep -Seconds 2
    if ($process.HasExited) {
        throw "BridgeLab $Name exited during startup with exit code $($process.ExitCode)."
    }

    Write-Host "bridge_lab_$($Name)_started=true pid=$($process.Id) exe=$ExecutablePath"
}

$ProjectRoot = Resolve-ExistingPath -Path $ProjectRoot -Label "Project root"
$BridgeLabRoot = Resolve-ExistingPath -Path $BridgeLabRoot -Label "BridgeLab root"

$runDir = Join-Path $BridgeLabRoot "run"
$binDir = Join-Path $runDir "bin"
$authExe = Join-Path $binDir "authserver.exe"
$worldExe = Join-Path $binDir "worldserver.exe"
$authConfig = Join-Path $runDir "configs\authserver.conf"
$worldConfig = Join-Path $runDir "configs\worldserver.conf"
$playerbotsConfig = Join-Path $runDir "configs\modules\playerbots.conf"
$runtimeGuard = Join-Path $runDir "helpers\Test-RuntimeDllGuard.ps1"
$dllLock = Join-Path $BridgeLabRoot "state\runtime-dlls.lock.json"

$startMySqlScript = Resolve-ExistingPath -Path (Join-Path $ProjectRoot "scripts\bridge_lab\Start-BridgeLabMySql.ps1") -Label "Start-BridgeLabMySql.ps1"
$configureScript = Resolve-ExistingPath -Path (Join-Path $ProjectRoot "scripts\bridge_lab\Configure-BridgeLabRuntime.ps1") -Label "Configure-BridgeLabRuntime.ps1"
$syncRealmlistScript = Resolve-ExistingPath -Path (Join-Path $ProjectRoot "scripts\bridge_lab\Sync-BridgeLabRealmlist.ps1") -Label "Sync-BridgeLabRealmlist.ps1"
$restartWorldScript = Resolve-ExistingPath -Path (Join-Path $ProjectRoot "scripts\bridge_lab\Restart-BridgeLabWorldServer.ps1") -Label "Restart-BridgeLabWorldServer.ps1"
$startNativeWatchScript = Resolve-ExistingPath -Path (Join-Path $ProjectRoot "scripts\bridge_lab\Start-BridgeLabNativeWatch.ps1") -Label "Start-BridgeLabNativeWatch.ps1"
$startAutoBountyScript = Resolve-ExistingPath -Path (Join-Path $ProjectRoot "scripts\bridge_lab\Start-BridgeLabAutoBounty.ps1") -Label "Start-BridgeLabAutoBounty.ps1"

Resolve-ExistingPath -Path $runDir -Label "BridgeLab run directory" | Out-Null
Resolve-ExistingPath -Path $authExe -Label "BridgeLab authserver.exe" | Out-Null
Resolve-ExistingPath -Path $worldExe -Label "BridgeLab worldserver.exe" | Out-Null
Resolve-ExistingPath -Path $authConfig -Label "BridgeLab authserver.conf" | Out-Null
Resolve-ExistingPath -Path $worldConfig -Label "BridgeLab worldserver.conf" | Out-Null

if ($ConfigureRuntime.IsPresent -and -not $SkipConfigure.IsPresent) {
    Invoke-BridgeLabScript -Path $configureScript -Arguments @(
        "-WorkspaceRoot", $BridgeLabRoot,
        "-LabMySqlPort", ([string]$LabMySqlPort),
        "-WorldServerPort", ([string]$WorldServerPort),
        "-SoapPort", ([string]$SoapPort),
        "-DataDir", $DataDir,
        "-WmSpellsPlayerGuidAllowList", ([string]$PlayerGuid),
        "-UpdatePlayerbotsDatabaseInfo"
    )
}

if (-not $SkipConfigure.IsPresent -and -not $SkipPlayerbotsDatabaseSync.IsPresent) {
    Sync-PlayerbotsDatabaseInfo -ConfigPath $playerbotsConfig -Port $LabMySqlPort
}

if ($ConfigOnly.IsPresent) {
    Write-Host "bridge_lab_config_only=true project=$ProjectRoot lab=$BridgeLabRoot mysql_port=$LabMySqlPort world_port=$WorldServerPort soap_port=$SoapPort"
    return
}

if (Test-Path -LiteralPath $runtimeGuard) {
    Invoke-BridgeLabScript -Path $runtimeGuard -Arguments @(
        "-BinRoot", $binDir,
        "-LockPath", $dllLock
    )
}

Invoke-BridgeLabScript -Path $startMySqlScript -Arguments @(
    "-WorkspaceRoot", $BridgeLabRoot,
    "-Port", ([string]$LabMySqlPort)
)

Invoke-BridgeLabScript -Path $syncRealmlistScript -Arguments @(
    "-WorkspaceRoot", $BridgeLabRoot,
    "-MySqlPort", ([string]$LabMySqlPort)
)

Start-LabServerProcess `
    -Name "authserver" `
    -ProcessName "authserver" `
    -ExecutablePath $authExe `
    -WorkingDirectory $runDir `
    -ConfigPath "configs\authserver.conf"

if ($RestartWorldServer.IsPresent) {
    Invoke-BridgeLabScript -Path $restartWorldScript -Arguments @(
        "-WorkspaceRoot", $BridgeLabRoot
    )
} else {
    Start-LabServerProcess `
        -Name "worldserver" `
        -ProcessName "worldserver" `
        -ExecutablePath $worldExe `
        -WorkingDirectory $runDir `
        -ConfigPath "configs\worldserver.conf"
}

if ($Watcher -eq "auto-bounty") {
    $autoArgs = @(
        "-WorkspaceRoot", $ProjectRoot,
        "-BridgeLabRoot", $BridgeLabRoot,
        "-PlayerGuid", ([string]$PlayerGuid),
        "-Mode", "apply",
        "-LabMySqlPort", ([string]$LabMySqlPort),
        "-SoapPort", ([string]$SoapPort)
    )
    if (-not $ResetBountyRules.IsPresent) {
        $autoArgs += "-KeepExistingBountyRules"
    }
    if ($KeepExistingEventBacklog.IsPresent) {
        $autoArgs += "-KeepExistingEventBacklog"
    }
    if (-not $DisableRandomEnchantOnKill.IsPresent) {
        $autoArgs += "-EnableRandomEnchantOnKill"
    }
    if ($PrintIdle.IsPresent) {
        $autoArgs += "-PrintIdle"
    }

    Invoke-BridgeLabScript -Path $startAutoBountyScript -Arguments $autoArgs
} elseif ($Watcher -eq "native") {
    $nativeArgs = @(
        "-WorkspaceRoot", $ProjectRoot,
        "-BridgeLabRoot", $BridgeLabRoot,
        "-PlayerGuid", ([string]$PlayerGuid),
        "-Mode", "apply",
        "-LabMySqlPort", ([string]$LabMySqlPort),
        "-SoapPort", ([string]$SoapPort),
        "-ArmFromEnd",
        "-MarkExistingEvaluatedOnArm"
    )
    if ($PrintIdle.IsPresent) {
        $nativeArgs += "-PrintIdle"
    }

    Invoke-BridgeLabScript -Path $startNativeWatchScript -Arguments $nativeArgs
} else {
    Write-Host "bridge_lab_watcher_started=false reason=disabled"
}

Write-Host "bridge_lab_all_started=true project=$ProjectRoot lab=$BridgeLabRoot player_guid=$PlayerGuid mysql_port=$LabMySqlPort world_port=$WorldServerPort soap_port=$SoapPort watcher=$Watcher"
