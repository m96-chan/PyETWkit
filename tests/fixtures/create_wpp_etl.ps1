# Create a sample ETL file containing WPP events, plus the .tmf needed to decode
# them. Run as Administrator.
#
# WPP events carry no schema. Their format strings live in a .tmf generated from
# the emitting binary's PDB, so a fixture is only useful together with its .tmf --
# both are committed.
#
# Needs the Windows SDK (tracewpp.exe, tracepdb.exe) and MSVC (cl.exe), so unlike
# the other fixture scripts this one cannot run on a bare machine. That is why
# the artifacts are committed rather than generated on demand.

$ErrorActionPreference = "Stop"

$SdkBin = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin" -Directory |
    Where-Object { Test-Path "$($_.FullName)\x64\tracewpp.exe" } |
    Sort-Object Name -Descending | Select-Object -First 1
if ($null -eq $SdkBin) { throw "tracewpp.exe not found; install the Windows SDK" }
$Tools = "$($SdkBin.FullName)\x64"
$WppConfig = "$($SdkBin.FullName)\WppConfig\Rev1"

$VcVars = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
if (-not (Test-Path $VcVars)) { throw "vcvars64.bat not found; install the MSVC build tools" }

$Work = Join-Path $env:TEMP "pyetwkit-wpp-fixture"
Remove-Item $Work -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $Work | Out-Null

# The provider. The control GUID is what the trace session enables; the trace
# GUID that names the .tmf is derived per source file by WPP itself.
@'
#include <windows.h>
#include <stdio.h>

#define WPP_CONTROL_GUIDS                                              \
    WPP_DEFINE_CONTROL_GUID(                                           \
        PyEtwKitWppTest,                                               \
        (A9B4C1D2, 3E5F, 4A6B, 8C7D, 9E0F1A2B3C4D),                    \
        WPP_DEFINE_BIT(TEST_ALL))

#include "wpptest.tmh"

int main(void)
{
    WPP_INIT_TRACING(L"PyEtwKitWppTest");
    for (int i = 0; i < 3; i++) {
        DoTraceMessage(TEST_ALL,
                       "wpp probe seq=%d name=%s value=0x%x",
                       i, "core-state", 0x50C0 + i);
    }
    WPP_CLEANUP();
    printf("emitted 3 WPP events\n");
    return 0;
}
'@ | Set-Content -Encoding utf8 "$Work\wpptest.c"

Push-Location $Work
try {
    & "$Tools\tracewpp.exe" -cfgdir:"$WppConfig" -odir:"$Work" wpptest.c
    cmd /c "`"$VcVars`" >nul 2>&1 && cl /nologo /Zi /W3 /Fe:wpptest.exe /Fd:wpptest.pdb wpptest.c advapi32.lib"

    New-Item -ItemType Directory -Force "$Work\tmf" | Out-Null
    & "$Tools\tracepdb.exe" -f wpptest.pdb -p "$Work\tmf"

    $SessionName = "PyETWkitWppFixture"
    logman stop $SessionName -ets 2>$null | Out-Null
    logman create trace $SessionName -o "$Work\wpp.etl" -ets `
        -p "{A9B4C1D2-3E5F-4A6B-8C7D-9E0F1A2B3C4D}" 0xffffffff 0xff -bs 4 -nb 2 2
    .\wpptest.exe
    Start-Sleep -Milliseconds 300
    logman stop $SessionName -ets
}
finally { Pop-Location }

Copy-Item "$Work\wpp.etl" "$PSScriptRoot\wpp.etl" -Force
New-Item -ItemType Directory -Force "$PSScriptRoot\wpp_tmf" | Out-Null
Remove-Item "$PSScriptRoot\wpp_tmf\*.tmf" -Force -ErrorAction SilentlyContinue
Copy-Item "$Work\tmf\*.tmf" "$PSScriptRoot\wpp_tmf\" -Force

Write-Host "Created: $PSScriptRoot\wpp.etl ($((Get-Item "$PSScriptRoot\wpp.etl").Length) bytes)"
Get-ChildItem "$PSScriptRoot\wpp_tmf" | ForEach-Object { Write-Host "Created: $($_.FullName)" }

# Independent check, using Microsoft's own formatter rather than ours.
& "$Tools\tracefmt.exe" "$PSScriptRoot\wpp.etl" -p "$PSScriptRoot\wpp_tmf" -o "$Work\fmt.txt" -nosummary
Get-Content "$Work\fmt.txt"
