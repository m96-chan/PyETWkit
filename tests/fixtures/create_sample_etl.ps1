# Create a minimal sample ETL file for testing
# Run as Administrator

$OutputPath = "$PSScriptRoot\sample.etl"
$SessionName = "PyETWkitTestSession"

# Stop if session exists
logman stop $SessionName -ets 2>$null

# Create a short trace session
logman create trace $SessionName -o $OutputPath -ets -p "Microsoft-Windows-Kernel-Process" 0x10 0xFF

# Wait a bit to capture some events
Start-Sleep -Seconds 2

# Generate some process events by starting a simple process
Start-Process -FilePath "cmd.exe" -ArgumentList "/c echo test" -NoNewWindow -Wait

# Wait for events to be written
Start-Sleep -Seconds 1

# Stop the session
logman stop $SessionName -ets

Write-Host "Created sample ETL file: $OutputPath"
Write-Host "File size: $((Get-Item $OutputPath).Length) bytes"
