# Build the WPP provider in wpp_provider/, capture its events, and produce the
# .tmf needed to decode them. Run as Administrator.
#
# WPP events carry no schema. Their format strings live in a .tmf generated from
# the emitting binary's PDB, so a capture is only useful together with one --
# which is why both wpp.etl and wpp_tmf/ are committed.
#
# Needs the Windows SDK (tracewpp.exe, tracepdb.exe, tracefmt.exe) and MSVC
# (cl.exe), so unlike the other fixture scripts this cannot run on a bare
# machine. CI has all of it and uses this script to exercise decoding from a
# freshly built PDB, which is the one route the committed fixture cannot cover:
# WPP derives the trace GUID from the source file's full path, so a build
# anywhere else produces a different GUID and cannot decode the committed
# capture.
#
#   .\create_wpp_etl.ps1                      # refresh the committed fixture
#   .\create_wpp_etl.ps1 -OutputDir C:\tmp\w  # build somewhere else, e.g. in CI

[CmdletBinding()]
param(
    # Where wpp.etl, wpp_tmf\ and (with -IncludePdb) the PDB are written.
    [string] $OutputDir = $PSScriptRoot,
    # Copy the PDB out too. Not wanted for the committed fixture, where it would
    # be a 7 MB binary to cover one extra TDH context value.
    [switch] $IncludePdb
)

$ErrorActionPreference = "Stop"

# tracewpp, tracepdb and logman all write progress to stderr, which with
# ErrorActionPreference=Stop would abort the script on a successful run. Judge
# them by their exit code instead.
# Arguments come as one array rather than as remaining arguments: PowerShell
# would otherwise bind a switch like -p to its own common parameters.
function Invoke-Native {
    param([string] $Exe, [string[]] $Arguments = @())
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Exe @Arguments 2>&1 | ForEach-Object { Write-Host "  $_" }
        if ($LASTEXITCODE -ne 0) { throw "$Exe exited with $LASTEXITCODE" }
    }
    finally { $ErrorActionPreference = $previous }
}

$SdkBin = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin" -Directory -ErrorAction SilentlyContinue |
    Where-Object { Test-Path "$($_.FullName)\x64\tracewpp.exe" } |
    Sort-Object Name -Descending | Select-Object -First 1
if ($null -eq $SdkBin) { throw "tracewpp.exe not found; install the Windows SDK" }
$Tools = "$($SdkBin.FullName)\x64"
$WppConfig = "$($SdkBin.FullName)\WppConfig\Rev1"
Write-Host "Using SDK tools: $Tools"

# vswhere is the supported way to find an install and is present wherever
# Visual Studio or the build tools are, CI runners included.
$VsWhere = "C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path $VsWhere)) { throw "vswhere.exe not found; install the MSVC build tools" }
$VsRoot = & $VsWhere -latest -products * `
    -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 `
    -property installationPath
if ([string]::IsNullOrWhiteSpace($VsRoot)) { throw "no MSVC C++ toolset found" }
$VcVars = Join-Path $VsRoot "VC\Auxiliary\Build\vcvars64.bat"
if (-not (Test-Path $VcVars)) { throw "vcvars64.bat not found under $VsRoot" }
Write-Host "Using MSVC: $VcVars"

# WPP bakes the source file's full path into the trace GUID, so the build has to
# happen in a stable directory rather than a temp one, or the committed .tmf
# would stop matching the committed capture.
$Build = Join-Path $PSScriptRoot "wpp_provider"
if (-not (Test-Path "$Build\wpptest.c")) { throw "wpp_provider\wpptest.c is missing" }

Push-Location $Build
try {
    Invoke-Native "$Tools\tracewpp.exe" @("-cfgdir:$WppConfig", "-odir:$Build", "wpptest.c")
    cmd /c "`"$VcVars`" >nul 2>&1 && cl /nologo /Zi /W3 /Fe:wpptest.exe /Fd:wpptest.pdb wpptest.c advapi32.lib"

    $Tmf = Join-Path $Build "tmf"
    New-Item -ItemType Directory -Force $Tmf | Out-Null
    Get-ChildItem "$Tmf\*.tmf" -ErrorAction SilentlyContinue | Remove-Item -Force
    Invoke-Native "$Tools\tracepdb.exe" @("-f", "wpptest.pdb", "-p", $Tmf)

    $Etl = Join-Path $Build "wpp.etl"
    $SessionName = "PyETWkitWppFixture"
    logman stop $SessionName -ets 2>$null | Out-Null
    if (Test-Path $Etl) { Remove-Item $Etl -Force }
    Invoke-Native "logman" @("create", "trace", $SessionName, "-o", $Etl, "-ets",
        "-p", "{A9B4C1D2-3E5F-4A6B-8C7D-9E0F1A2B3C4D}", "0xffffffff", "0xff", "-bs", "4", "-nb", "2", "2")
    Invoke-Native (Join-Path $Build "wpptest.exe")
    Start-Sleep -Milliseconds 300
    Invoke-Native "logman" @("stop", $SessionName, "-ets")
}
finally { Pop-Location }

New-Item -ItemType Directory -Force $OutputDir | Out-Null
$TmfOut = Join-Path $OutputDir "wpp_tmf"
New-Item -ItemType Directory -Force $TmfOut | Out-Null
Get-ChildItem "$TmfOut\*.tmf" -ErrorAction SilentlyContinue | Remove-Item -Force

Copy-Item "$Build\wpp.etl" (Join-Path $OutputDir "wpp.etl") -Force
Copy-Item "$Build\tmf\*.tmf" $TmfOut -Force
if ($IncludePdb) { Copy-Item "$Build\wpptest.pdb" (Join-Path $OutputDir "wpptest.pdb") -Force }

Write-Host "ETL: $(Join-Path $OutputDir 'wpp.etl') ($((Get-Item (Join-Path $OutputDir 'wpp.etl')).Length) bytes)"
Get-ChildItem $TmfOut | ForEach-Object { Write-Host "TMF: $($_.FullName)" }
if ($IncludePdb) { Write-Host "PDB: $(Join-Path $OutputDir 'wpptest.pdb')" }

# Independent check, using Microsoft's own formatter rather than ours. The
# expected strings in the tests come from here.
Write-Host "`ntracefmt says:"
$FmtOut = Join-Path $Build "fmt.txt"
Invoke-Native "$Tools\tracefmt.exe" @((Join-Path $OutputDir "wpp.etl"), "-p", $TmfOut, "-o", $FmtOut, "-nosummary")
Get-Content $FmtOut
