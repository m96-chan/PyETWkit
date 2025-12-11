"""Demo: Async ETW API (v1.1 feature)

This example demonstrates the new async API for ETW event streaming,
including typed events, filtering, and concurrent processing.

Run as administrator.
"""

import asyncio

from pyetwkit import (
    AsyncEtwSession,
    EventBatcher,
    EventFilterBuilder,
    ProcessStartEvent,
    to_typed_event,
)


async def demo_basic_async():
    """Basic async event streaming."""
    print("=== Basic Async Streaming ===")
    print("Monitoring DNS events for 5 seconds...\n")

    async with AsyncEtwSession() as session:
        session.add_provider("Microsoft-Windows-DNS-Client", level=5)

        count = 0
        async for event in session.events(timeout=5.0, max_events=20):
            count += 1
            print(f"[{count}] Event {event.event_id}: {event.provider_name}")

    print(f"\nCaptured {count} events")


async def demo_typed_events():
    """Typed events with automatic conversion."""
    print("\n=== Typed Events ===")
    print("Monitoring process events for 10 seconds...\n")
    print("Try starting/stopping programs to see events.\n")

    # Use kernel session for process events (not AsyncEtwSession)
    from pyetwkit._core import KernelSession

    kernel = KernelSession()
    kernel.enable_process()
    kernel.start()

    try:
        for _ in range(50):  # Check up to 50 times
            event = kernel.next_event_timeout(200)
            if event:
                typed = to_typed_event(event)
                if isinstance(typed, ProcessStartEvent):
                    print(f"[PROCESS START] {typed.image_file_name}")
                    print(f"  PID: {typed.process_id}")
                    print(f"  Command: {typed.command_line[:60]}...")
                else:
                    print(f"[{typed.EVENT_NAME or 'Event'}] ID={typed.event_id}")
    finally:
        kernel.stop()


async def demo_filtering():
    """Advanced filtering with EventFilterBuilder."""
    print("\n=== Event Filtering ===")
    print("Filtering DNS events by level...\n")

    # Build a filter
    event_filter = (
        EventFilterBuilder()
        .level_max(4)  # Info and above only
        .build()
    )

    async with AsyncEtwSession() as session:
        session.add_provider("Microsoft-Windows-DNS-Client", level=5)
        session.filter(event_filter)  # Apply filter

        count = 0
        async for event in session.events(timeout=5.0, max_events=10):
            count += 1
            print(f"[Level {event.level}] Event {event.event_id}")

    print(f"\nFiltered to {count} events")


async def demo_callbacks():
    """Event callbacks for async processing."""
    print("\n=== Event Callbacks ===")
    print("Processing events with async callbacks...\n")

    processed = []

    async def log_event(event):
        """Async callback for each event."""
        processed.append(event.event_id)
        print(f"  Callback processed event {event.event_id}")

    async with AsyncEtwSession() as session:
        session.add_provider("Microsoft-Windows-DNS-Client", level=5)
        session.on_event(log_event)  # Register callback

        async for event in session.events(timeout=3.0, max_events=5):
            print(f"Main loop: {event.event_id}")

    print(f"\nCallback processed {len(processed)} events")


async def demo_batching():
    """Batch processing for efficient bulk operations."""
    print("\n=== Event Batching ===")
    print("Collecting events in batches...\n")

    batcher = EventBatcher(batch_size=5, timeout=2.0)

    async with AsyncEtwSession() as session:
        session.add_provider("Microsoft-Windows-DNS-Client", level=5)

        batch_count = 0
        async for batch in batcher.batches(session, max_batches=3):
            batch_count += 1
            print(f"Batch {batch_count}: {len(batch)} events")
            for event in batch:
                print(f"  - Event {event.event_id}")

    print(f"\nProcessed {batch_count} batches")


async def main():
    """Run all demos."""
    print("PyETWkit v1.1 Async API Demo")
    print("=" * 40)
    print("Note: Run as administrator for ETW access")
    print("Generate DNS traffic (e.g., ping example.com) to see events")
    print("=" * 40)

    try:
        await demo_basic_async()
        await demo_filtering()
        await demo_callbacks()
        # await demo_batching()  # Uncomment to test batching
        # await demo_typed_events()  # Uncomment for kernel events

    except PermissionError:
        print("\nError: Administrator privileges required")
        print("Please run this script as administrator")
    except Exception as e:
        print(f"\nError: {e}")


if __name__ == "__main__":
    asyncio.run(main())
