"""Provider profiles example.

This example shows how to use pre-configured provider profiles
to quickly set up monitoring for common scenarios.
"""

from pyetwkit._core import EtwProvider, EtwSession
from pyetwkit.profiles import get_profile, list_profiles


def main():
    # List available profiles
    print("=== Available Profiles ===")
    profiles = list_profiles()
    for p in profiles:
        print(f"\n{p.name}: {p.description}")
        print(f"  Providers ({len(p.providers)}):")
        for prov in p.providers[:3]:  # Show first 3
            print(f"    - {prov.name}")
        if len(p.providers) > 3:
            print(f"    ... and {len(p.providers) - 3} more")

    # Use a profile
    print("\n=== Using 'network' profile ===")
    network_profile = get_profile("network")
    if network_profile is None:
        print("Network profile not found")
        return

    session = EtwSession("PyETWkitProfileExample")

    for pc in network_profile.providers:
        provider = EtwProvider(pc.guid or pc.name, pc.name)
        provider = provider.with_level(4)
        session.add_provider(provider)
        print(f"Added provider: {pc.name}")

    print("\nStarting session... Press Ctrl+C to stop")
    session.start()

    try:
        event_count = 0
        while True:
            event = session.next_event_timeout(1000)
            if event is None:
                continue

            event_count += 1
            print(f"[{event.provider_name}] Event {event.event_id}")

    except KeyboardInterrupt:
        print(f"\nStopping... Captured {event_count} events")
    finally:
        session.stop()


if __name__ == "__main__":
    main()
