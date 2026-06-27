# check-env.ps1
# Windows PowerShell 版本，对应 scripts/check-env.sh
# 仅给出提示，不强制；orchestrator 自身只用 Python。

$ErrorActionPreference = 'Continue'

Write-Host '== Language runtime check (Windows) ==' -ForegroundColor Cyan

function Test-Runtime {
    param(
        [Parameter(Mandatory = $true)] [string] $Name,
        [Parameter(Mandatory = $true)] [string[]] $Commands
    )
    foreach ($cmd in $Commands) {
        $found = Get-Command -Name $cmd -ErrorAction SilentlyContinue
        if ($found) {
            Write-Host ("  [OK]   {0,-10} -> {1}" -f $Name, $found.Source) -ForegroundColor Green
            return
        }
    }
    $cmdlist = ($Commands -join ', ')
    Write-Host ("  [MISS] {0,-10} (looking for: {1})" -f $Name, $cmdlist) -ForegroundColor Yellow
}

Test-Runtime -Name 'Python'   -Commands @('python', 'python3', 'py')
Test-Runtime -Name 'uv'       -Commands @('uv')
Test-Runtime -Name 'Node'     -Commands @('node', 'node.exe')
Test-Runtime -Name 'Java'     -Commands @('java', 'java.exe')
Test-Runtime -Name 'Go'       -Commands @('go', 'go.exe')
Test-Runtime -Name 'Rust'     -Commands @('cargo', 'cargo.exe')
Test-Runtime -Name '.NET'     -Commands @('dotnet', 'dotnet.exe')
Test-Runtime -Name 'C++'      -Commands @('cmake', 'g++', 'cl')
Test-Runtime -Name 'Ruby'     -Commands @('ruby', 'ruby.exe')
Test-Runtime -Name 'Kotlin'   -Commands @('kotlin', 'kotlinc', 'kotlin.exe')

Write-Host ''
Write-Host 'Tip: missing runtimes will not fail this check, but their adapters will be skipped at run time.' -ForegroundColor DarkGray
