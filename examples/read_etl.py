"""Read ETL file example.

This example shows how to read events from an ETL
(Event Trace Log) file.
"""

import sys
from pathlib import Path

from pyetwkit._core import EtlReader


def main():
    if len(sys.argv) < 2:
        print("Usage: python read_etl.py <etl_file>")
        print("\nTo create an ETL file:")
        print("  logman start mytrace -p Microsoft-Windows-DNS-Client -o trace.etl -ets")
        print("  ping example.com")
        print("  logman stop mytrace -ets")
        sys.exit(1)

    etl_path = Path(sys.argv[1])
    if not etl_path.exists():
        print(f"File not found: {etl_path}")
        sys.exit(1)

    print(f"Reading ETL file: {etl_path}")

    reader = EtlReader(str(etl_path))
    event_count = 0
    provider_stats: dict[str, int] = {}

    for event in reader.events():
        event_count += 1

        # Track provider statistics
        provider = event.provider_name or str(event.provider_id)
        provider_stats[provider] = provider_stats.get(provider, 0) + 1

        # Show first 10 events in detail
        if event_count <= 10:
            print(f"\n[Event {event_count}]")
            print(f"  Timestamp: {event.timestamp}")
            print(f"  Provider: {provider}")
            print(f"  Event ID: {event.event_id}")

            props = event.to_dict().get("properties", {})
            for key, value in list(props.items())[:3]:
                print(f"  {key}: {value}")

    print("\n=== Summary ===")
    print(f"Total events: {event_count}")
    print("\nEvents by provider:")
    for provider, count in sorted(provider_stats.items(), key=lambda x: -x[1]):
        print(f"  {provider}: {count}")


if __name__ == "__main__":
    main()
