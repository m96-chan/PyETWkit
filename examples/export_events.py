"""Export ETW events to various formats.

This example shows how to capture events and export them
to CSV, JSON, and Parquet formats.
"""

import sys
from pathlib import Path

from pyetwkit._core import EtwProvider, EtwSession
from pyetwkit.export import to_csv, to_json, to_jsonl


def main():
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    session = EtwSession("PyETWkitExportExample")

    provider = EtwProvider.dns_client().level(4)
    session.add_provider(provider)

    print("Capturing events for 10 seconds...")
    session.start()

    events = []
    try:
        import time

        start_time = time.time()
        while time.time() - start_time < 10:
            event = session.next_event_timeout(1000)
            if event:
                events.append(event)
                print(f"Captured event {len(events)}: {event.event_id}")

    except KeyboardInterrupt:
        pass
    finally:
        session.stop()

    if not events:
        print("No events captured. Try generating DNS traffic:")
        print("  ping example.com")
        sys.exit(0)

    print(f"\nCaptured {len(events)} events")

    # Export to various formats
    csv_path = output_dir / "events.csv"
    to_csv(events, csv_path)
    print(f"Exported to {csv_path}")

    json_path = output_dir / "events.json"
    to_json(events, json_path, indent=2)
    print(f"Exported to {json_path}")

    jsonl_path = output_dir / "events.jsonl"
    to_jsonl(events, jsonl_path)
    print(f"Exported to {jsonl_path}")

    print("\nExport complete!")


if __name__ == "__main__":
    main()
