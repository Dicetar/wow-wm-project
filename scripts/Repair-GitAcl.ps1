[CmdletBinding()]
param(
    [string]$WorkspaceRoot = "",
    [switch]$SkipGitProcessStop
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[Repair-GitAcl] $Message"
}

function Remove-OrphanSidAces {
    param([Parameter(Mandatory = $true)][string]$Path)

    $resolved = (Resolve-Path $Path).Path
    $acl = Get-Acl -LiteralPath $resolved
    $removed = 0

    foreach ($rule in @($acl.Access)) {
        $identity = $rule.IdentityReference.Value
        if ($identity -match '^S-1-5-21-\d+-\d+-\d+-\d+$') {
            $acl.RemoveAccessRuleSpecific($rule) | Out-Null
            $removed += 1
        }
    }

    if ($removed -gt 0) {
        try {
            Set-Acl -LiteralPath $resolved -AclObject $acl
        } catch {
            Write-Step "Could not rewrite ACL on ${resolved}: $($_.Exception.Message)"
            return -1
        }
    }

    return $removed
}

function Assert-NoDenyAces {
    param([Parameter(Mandatory = $true)][string]$Path)

    $resolved = (Resolve-Path $Path).Path
    $acl = Get-Acl -LiteralPath $resolved
    $deny = @($acl.Access | Where-Object { $_.AccessControlType -eq "Deny" })
    if ($deny.Count -gt 0) {
        $lines = $deny | ForEach-Object { "$($_.IdentityReference.Value): $($_.FileSystemRights)" }
        throw "Deny ACE remains on ${resolved}: $($lines -join '; ')"
    }
}

function Assert-IndexLockWritable {
    param([Parameter(Mandatory = $true)][string]$GitDir)

    $lockPath = Join-Path $GitDir "index.lock"
    if (Test-Path -LiteralPath $lockPath) {
        throw "Refusing to overwrite existing Git lock: $lockPath"
    }
    New-Item -Path $lockPath -ItemType File -ErrorAction Stop | Out-Null
    Remove-Item -LiteralPath $lockPath -Force -ErrorAction Stop
}

if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    $scriptRoot = $PSScriptRoot
    if ([string]::IsNullOrWhiteSpace($scriptRoot)) {
        $scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
    }
    $WorkspaceRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
} else {
    $WorkspaceRoot = (Resolve-Path $WorkspaceRoot).Path
}

Set-Location -LiteralPath $WorkspaceRoot
$gitDir = Join-Path $WorkspaceRoot ".git"
if (-not (Test-Path -LiteralPath $gitDir -PathType Container)) {
    throw "No .git directory found under $WorkspaceRoot"
}
$account = "$env:USERDOMAIN\$env:USERNAME"

if (-not $SkipGitProcessStop) {
    Write-Step "Stopping active git* processes so ACL changes are not immediately rewritten."
    try {
        $gitProcesses = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -like "git*" })
    } catch {
        Write-Step "CIM process inspection failed: $($_.Exception.Message); falling back to Get-Process git*."
        $gitProcesses = @(Get-Process git* -ErrorAction SilentlyContinue | ForEach-Object {
            [pscustomobject]@{ Name = $_.ProcessName; ProcessId = $_.Id }
        })
    }
    foreach ($process in $gitProcesses) {
        try {
            Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
            Write-Step "Stopped $($process.Name) pid=$($process.ProcessId)"
        } catch {
            Write-Step "Could not stop $($process.Name) pid=$($process.ProcessId): $($_.Exception.Message)"
        }
    }
}

Write-Step "Removing orphan SID ACEs from workspace root."
$removedRoot = Remove-OrphanSidAces -Path $WorkspaceRoot
Write-Step "Removed $removedRoot orphan SID ACE(s) from workspace root."

Write-Step "Removing orphan SID ACEs from .git root."
$removedGit = Remove-OrphanSidAces -Path $gitDir
Write-Step "Removed $removedGit orphan SID ACE(s) from .git."

Write-Step "Refreshing .git root inheritance."
icacls $gitDir /inheritance:e | Out-Null

Write-Step "Granting $account inheritable full control on .git."
icacls $gitDir /grant:r "${account}:(OI)(CI)F" | Out-Null
icacls $gitDir /grant:r "BUILTIN\Administrators:(OI)(CI)F" | Out-Null
icacls $gitDir /grant:r "NT AUTHORITY\SYSTEM:(OI)(CI)F" | Out-Null

Write-Step "Removing any orphan SID ACEs that flowed back onto .git root."
$removedGitAfterGrant = Remove-OrphanSidAces -Path $gitDir
Write-Step "Removed $removedGitAfterGrant orphan SID ACE(s) from .git after grant."

Write-Step "Verifying no DENY ACEs remain on .git and index."
Assert-NoDenyAces -Path $gitDir
Assert-NoDenyAces -Path (Join-Path $gitDir "index")

Write-Step "Verifying .git/index.lock is writable."
Assert-IndexLockWritable -GitDir $gitDir

Write-Step "Disabling Git fsmonitor for this repo."
git config core.fsmonitor false

Write-Step "Verifying git status does not recreate DENY ACEs."
git status --short | Out-Null
Assert-NoDenyAces -Path $gitDir
Assert-NoDenyAces -Path (Join-Path $gitDir "index")

Write-Step "Verifying git add --refresh succeeds."
git add --refresh .

Write-Step "Running final orphan SID cleanup after Git verification."
Remove-OrphanSidAces -Path $WorkspaceRoot | Out-Null
Remove-OrphanSidAces -Path $gitDir | Out-Null
Assert-NoDenyAces -Path $gitDir
Assert-NoDenyAces -Path (Join-Path $gitDir "index")

Write-Step "Git ACL repair completed."
