# lint-adapter.ps1
# Windows PowerShell 版本。薄壳：把参数透传给 scripts/lint_adapter.py。
# 默认启用 --check-command --check-help 以覆盖全部检查 (G1/R2/C1/C2)。
# 当 orchestrator 落地后，本脚本将让位给 `python -m orchestrator lint-adapter`。

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false, Position = 0)]
    [string] $AdapterId,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $ExtraArgs
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PyScript = Join-Path $RepoRoot 'scripts\lint_adapter.py'

Write-Host '== lint-adapter (ps1) ==' -ForegroundColor Cyan

$uv = Get-Command -Name 'uv' -ErrorAction SilentlyContinue
if (-not $uv) {
    Write-Host 'FATAL: uv not found in PATH' -ForegroundColor Red
    exit 2
}

$ScriptArgs = @()
if ($AdapterId) { $ScriptArgs += $AdapterId }
$ScriptArgs += '--check-command', '--check-help'
if ($ExtraArgs) { $ScriptArgs += $ExtraArgs }

& uv run --directory $RepoRoot python $PyScript @ScriptArgs
exit $LASTEXITCODE
