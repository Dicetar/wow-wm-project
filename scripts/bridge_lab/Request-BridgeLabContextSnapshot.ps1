param(
    [int]$PlayerGuid = 5406,
    [string]$ContextKind = "nearby",
    [int]$Radius = 40,
    [double]$TimeoutSeconds = 10,
    [double]$PollSeconds = 0.25,
    [string]$CreatedBy = "bridge_lab",
    [switch]$Summary
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Push-Location $RepoRoot
try {
    $Args = @(
        "-m", "wm.context.snapshot",
        "--player-guid", $PlayerGuid,
        "--context-kind", $ContextKind,
        "--radius", $Radius,
        "--timeout-seconds", $TimeoutSeconds,
        "--poll-seconds", $PollSeconds,
        "--created-by", $CreatedBy
    )
    if ($Summary) {
        $Args += "--summary"
    }
    python @Args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
