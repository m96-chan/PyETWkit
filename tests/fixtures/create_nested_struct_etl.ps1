# Create a sample ETL file containing events with nested structure properties.
# Run as Administrator.
#
# Microsoft-Windows-Kernel-Process, which sample.etl uses, has no struct-typed
# properties, so it cannot cover the TDH struct path. Kernel-Processor-Power
# emits core-parking events carrying several structs (Group, OldPark, NewPark,
# ... each { Number, Affinity }) and fires continuously on an idle machine, so a
# fraction of a second is enough.
#
# The Algorithm keyword (0x20) is what selects those events; the wider keyword
# masks add hundreds of KB of unrelated telemetry without adding a struct.

$OutputPath = "$PSScriptRoot\nested_struct.etl"
$SessionName = "PyETWkitNestedStructSession"

logman stop $SessionName -ets 2>$null | Out-Null
Remove-Item $OutputPath -ErrorAction SilentlyContinue

# Small buffers keep the fixture near the size of sample.etl; ETL files are
# written a whole buffer at a time, so this is what bounds the file.
logman create trace $SessionName -o $OutputPath -ets `
    -p "Microsoft-Windows-Kernel-Processor-Power" 0x20 0xff `
    -bs 4 -nb 2 2

Start-Sleep -Milliseconds 120

logman stop $SessionName -ets

Write-Host "Created nested-struct ETL file: $OutputPath"
Write-Host "File size: $((Get-Item $OutputPath).Length) bytes"
