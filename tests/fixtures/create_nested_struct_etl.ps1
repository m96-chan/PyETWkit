# Create a sample ETL file containing events with nested structure properties.
# Run as Administrator.
#
# This deliberately uses a TraceLogging provider defined right here rather than
# a Windows one. A TraceLogging event carries its own schema inside the event,
# so the resulting ETL decodes identically on any machine. A manifest provider
# does not: decoding needs that manifest installed and of a matching version, so
# a fixture captured from, say, Kernel-Processor-Power decodes on the machine
# that recorded it and yields nothing in CI on a different Windows build. That
# is not hypothetical -- it is why this script exists in this form.
#
# Windows ships the C# compiler used below (.NET Framework 4.x), so this needs
# no toolchain beyond a stock machine.

$OutputPath = "$PSScriptRoot\nested_struct.etl"
$SessionName = "PyETWkitNestedStructSession"

$source = @'
using System;
using System.Diagnostics.Tracing;

public static class NestedStructEmitter
{
    public static Guid ProviderGuid()
    {
        using (EventSource es = new EventSource("PyETWkit-NestedStruct"))
        {
            return es.Guid;
        }
    }

    public static void Emit()
    {
        using (EventSource es = new EventSource("PyETWkit-NestedStruct"))
        {
            for (int i = 0; i < 3; i++)
            {
                es.Write("CoreState", new
                {
                    Label = "core-state",
                    Sequence = i,
                    Park = new { Number = 7, Affinity = 0x50C0 },
                    Unpark = new { Number = 9, Affinity = 0x000F },
                });
                System.Threading.Thread.Sleep(40);
            }
        }
    }
}
'@

Add-Type -TypeDefinition $source -Language CSharp

$guid = [NestedStructEmitter]::ProviderGuid()
Write-Host "Provider GUID: $guid"

logman stop $SessionName -ets 2>$null | Out-Null
Remove-Item $OutputPath -ErrorAction SilentlyContinue

# Small buffers keep the fixture tiny; ETL files are written a whole buffer at a
# time, so this is what bounds the file size.
logman create trace $SessionName -o $OutputPath -ets -p "{$guid}" 0xffffffffffffffff 0xff -bs 4 -nb 2 2

[NestedStructEmitter]::Emit()
Start-Sleep -Milliseconds 200

logman stop $SessionName -ets

Write-Host "Created nested-struct ETL file: $OutputPath"
Write-Host "File size: $((Get-Item $OutputPath).Length) bytes"
