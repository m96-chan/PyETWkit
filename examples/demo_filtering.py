"""Demo: Event Filtering (v1.1 feature)

This example demonstrates the fluent filtering API for efficient
event selection based on various criteria.

Run as administrator.
"""

from pyetwkit import (
    EventFilterBuilder,
    event_id_filter,
    level_filter,
)
from pyetwkit._core import EtwProvider, EtwSession


def demo_basic_filtering():
    """Basic filter by event ID."""
    print("=== Basic Event ID Filter ===")

    # Create a simple filter
    filter = event_id_filter(1, 2, 3)

    print("Filter: event_id in [1, 2, 3]")
    print("Listening for 5 seconds...\n")

    session = EtwSession("FilterDemo1")
    provider = EtwProvider.dns_client().level(5)
    session.add_provider(provider)
    session.start()

    try:
        matched = 0
        total = 0
        for _ in range(50):
            event = session.next_event_timeout(100)
            if event:
                total += 1
                if filter(event):
                    matched += 1
                    print(f"  Matched: Event {event.event_id}")
                else:
                    print(f"  Filtered out: Event {event.event_id}")

        print(f"\nMatched {matched}/{total} events")

    finally:
        session.stop()


def demo_builder_api():
    """Fluent builder API for complex filters."""
    print("\n=== Fluent Filter Builder ===")

    # Build a complex filter with chaining
    filter = (
        EventFilterBuilder()
        .level_max(4)  # Info and below
        .exclude_event_ids([1001, 1002])  # Exclude noisy events
        .build()
    )

    print("Filter:")
    print("  - Level <= 4 (Info)")
    print("  - Exclude event IDs 1001, 1002")
    print("\nListening for 5 seconds...\n")

    session = EtwSession("FilterDemo2")
    provider = EtwProvider.dns_client().level(5)
    session.add_provider(provider)
    session.start()

    try:
        for _ in range(50):
            event = session.next_event_timeout(100)
            if event and filter(event):
                print(f"  Event {event.event_id} (level={event.level})")

    finally:
        session.stop()


def demo_property_filtering():
    """Filter by event properties."""
    print("\n=== Property Filtering ===")

    # This filter would match events where QueryName contains "google"
    filter = (
        EventFilterBuilder()
        .property_contains("QueryName", "example")
        .build()
    )

    print("Filter: QueryName contains 'example'")
    print("Tip: Run 'ping example.com' to generate matching events")
    print("\nListening for 10 seconds...\n")

    session = EtwSession("FilterDemo3")
    provider = EtwProvider.dns_client().level(5)
    session.add_provider(provider)
    session.start()

    try:
        for _ in range(100):
            event = session.next_event_timeout(100)
            if event:
                props = event.to_dict().get("properties", {})
                query_name = props.get("QueryName", "")
                if filter(event):
                    print(f"  MATCH: {query_name}")
                elif query_name:
                    print(f"  Skip: {query_name}")

    finally:
        session.stop()


def demo_combined_filters():
    """Combine multiple filters."""
    print("\n=== Combined Filters ===")

    # Create two filters and combine them
    level_f = level_filter(4)
    event_f = event_id_filter(3006, 3008)  # DNS query/response

    # Combine with AND
    combined = level_f & event_f

    print("Filter: level <= 4 AND event_id in [3006, 3008]")
    print("Listening for 5 seconds...\n")

    session = EtwSession("FilterDemo4")
    provider = EtwProvider.dns_client().level(5)
    session.add_provider(provider)
    session.start()

    try:
        for _ in range(50):
            event = session.next_event_timeout(100)
            if event and combined(event):
                print(f"  Matched: Event {event.event_id}")

    finally:
        session.stop()


def demo_custom_predicate():
    """Custom filter with arbitrary logic."""
    print("\n=== Custom Predicate Filter ===")

    # Custom filter function
    def my_filter(event):
        # Only events from processes with even PIDs
        return event.process_id % 2 == 0

    filter = (
        EventFilterBuilder()
        .custom(my_filter)
        .level_max(4)
        .build()
    )

    print("Filter: Even PID AND level <= 4")
    print("Listening for 5 seconds...\n")

    session = EtwSession("FilterDemo5")
    provider = EtwProvider.dns_client().level(5)
    session.add_provider(provider)
    session.start()

    try:
        for _ in range(50):
            event = session.next_event_timeout(100)
            if event and filter(event):
                print(f"  Matched: PID {event.process_id} Event {event.event_id}")

    finally:
        session.stop()


def demo_filter_summary():
    """Summary of available filter methods."""
    print("\n=== Available Filter Methods ===\n")

    methods = [
        ("event_id(id)", "Exact event ID match"),
        ("event_ids([ids])", "Match any of the event IDs"),
        ("exclude_event_ids([ids])", "Exclude specific event IDs"),
        ("process_id(pid)", "Exact process ID match"),
        ("process_ids([pids])", "Match any of the process IDs"),
        ("thread_id(tid)", "Exact thread ID match"),
        ("provider_name(name)", "Exact provider name match"),
        ("provider_contains(sub)", "Provider name contains substring"),
        ("level(n)", "Exact level match"),
        ("level_max(n)", "Level <= n (less severe)"),
        ("level_min(n)", "Level >= n (more severe)"),
        ("opcode(n)", "Exact opcode match"),
        ("opcodes([ops])", "Match any opcode"),
        ("property_equals(k, v)", "Property equals value"),
        ("property_contains(k, v)", "Property contains substring"),
        ("property_startswith(k, v)", "Property starts with prefix"),
        ("property_endswith(k, v)", "Property ends with suffix"),
        ("property_regex(k, pat)", "Property matches regex"),
        ("property_gt(k, v)", "Property > value"),
        ("property_lt(k, v)", "Property < value"),
        ("custom(fn)", "Custom predicate function"),
        ("match_any()", "Switch to OR mode"),
        ("match_all()", "Switch to AND mode (default)"),
    ]

    for method, desc in methods:
        print(f"  .{method:<30} {desc}")

    print("\nCombining filters:")
    print("  filter1 & filter2  # AND")
    print("  filter1 | filter2  # OR")


def main():
    """Run demos."""
    print("PyETWkit v1.1 Filtering Demo")
    print("=" * 40)
    print("Note: Run as administrator")
    print("Generate DNS traffic to see events")
    print("=" * 40)

    try:
        demo_filter_summary()
        demo_basic_filtering()
        demo_builder_api()
        demo_combined_filters()
        # demo_property_filtering()  # Uncomment and ping example.com
        # demo_custom_predicate()

    except PermissionError:
        print("\nError: Administrator privileges required")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
