"""Basic ETW session example.

This example shows how to create a simple ETW session to monitor
DNS client events. Run as administrator.
"""

from pyetwkit._core import EtwProvider, EtwSession


def main():
    # Create a session with a unique name
    session = EtwSession("PyETWkitBasicExample")

    # Add a provider (DNS client is relatively quiet)
    provider = EtwProvider(
        "Microsoft-Windows-DNS-Client",
        "Microsoft-Windows-DNS-Client",
    )
    provider = provider.with_level(4)  # Info level
    session.add_provider(provider)

    # Start the session
    print("Starting ETW session... Press Ctrl+C to stop")
    session.start()

    try:
        event_count = 0
        while True:
            # Wait for events with 1 second timeout
            event = session.next_event_timeout(1000)
            if event is None:
                continue

            event_count += 1
            print(f"[{event.timestamp}] Event {event.event_id}: {event.provider_name}")

            # Show properties if available
            props = event.to_dict().get("properties", {})
            for key, value in list(props.items())[:5]:  # First 5 props
                print(f"  {key}: {value}")

    except KeyboardInterrupt:
        print(f"\nStopping... Captured {event_count} events")
    finally:
        session.stop()


if __name__ == "__main__":
    main()
