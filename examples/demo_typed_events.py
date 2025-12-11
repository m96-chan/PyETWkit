"""Demo: Typed Events (v1.1 feature)

This example demonstrates strongly-typed event classes that provide
IDE autocomplete and type checking for ETW events.

Run as administrator.
"""

from pyetwkit import (
    ImageLoadEvent,
    ProcessStartEvent,
    ProcessStopEvent,
    ThreadStartEvent,
    TypedEvent,
    to_typed_event,
)
from pyetwkit._core import KernelSession


def demo_process_events():
    """Monitor process events with typed classes."""
    print("=== Typed Process Events ===")
    print("Monitoring for 15 seconds... Start/stop programs to see events.\n")

    session = KernelSession()
    session.enable_process()
    session.enable_thread()
    session.enable_image_load()
    session.start()

    try:
        process_starts = 0
        process_stops = 0
        thread_starts = 0
        image_loads = 0

        for _ in range(150):  # ~15 seconds
            event = session.next_event_timeout(100)
            if event is None:
                continue

            # Convert to typed event
            typed = to_typed_event(event)

            if isinstance(typed, ProcessStartEvent):
                process_starts += 1
                print("[PROCESS START]")
                print(f"  PID: {typed.process_id}")
                print(f"  Image: {typed.image_file_name}")
                print(f"  Parent PID: {typed.parent_process_id}")
                if typed.command_line:
                    cmd = typed.command_line[:80]
                    print(f"  Command: {cmd}{'...' if len(typed.command_line) > 80 else ''}")
                print()

            elif isinstance(typed, ProcessStopEvent):
                process_stops += 1
                print(f"[PROCESS STOP] PID={typed.process_id} Exit={typed.exit_code}")

            elif isinstance(typed, ThreadStartEvent):
                thread_starts += 1
                # Only show first few
                if thread_starts <= 5:
                    print(f"[THREAD START] PID={typed.process_id} TID={typed.thread_id}")

            elif isinstance(typed, ImageLoadEvent):
                image_loads += 1
                # Only show DLLs, not all modules
                if image_loads <= 10 and typed.image_name:
                    print(f"[IMAGE LOAD] {typed.image_name}")

        print("\n=== Summary ===")
        print(f"Process starts: {process_starts}")
        print(f"Process stops: {process_stops}")
        print(f"Thread starts: {thread_starts}")
        print(f"Image loads: {image_loads}")

    finally:
        if session.is_running():
            session.stop()


def demo_typed_event_dict():
    """Show typed event serialization."""
    print("\n=== Typed Event Serialization ===\n")

    # Create a sample event
    event = ProcessStartEvent(
        process_id=1234,
        thread_id=5678,
        event_id=1,
        image_file_name="notepad.exe",
        command_line="notepad.exe C:\\file.txt",
        parent_process_id=1000,
        session_id=1,
    )

    print("ProcessStartEvent instance:")
    print(f"  image_file_name: {event.image_file_name}")
    print(f"  command_line: {event.command_line}")
    print(f"  parent_process_id: {event.parent_process_id}")

    print("\nAs dictionary:")
    d = event.to_dict()
    for key, value in d.items():
        print(f"  {key}: {value}")


def demo_custom_typed_event():
    """Show how to create custom typed events."""
    print("\n=== Custom Typed Events ===\n")

    from dataclasses import dataclass
    from typing import ClassVar

    from pyetwkit.typed_events import register_event_type

    @dataclass
    class MyCustomEvent(TypedEvent):
        """Custom event for a specific provider."""

        PROVIDER_NAME: ClassVar[str] = "My-Custom-Provider"
        EVENT_ID: ClassVar[int] = 100
        EVENT_NAME: ClassVar[str] = "CustomEvent"

        custom_field: str = ""
        custom_value: int = 0

        @classmethod
        def from_event(cls, event):
            props = event.to_dict().get("properties", {})
            return cls(
                timestamp=event.timestamp,
                process_id=event.process_id,
                thread_id=event.thread_id,
                event_id=event.event_id,
                opcode=event.opcode,
                level=event.level,
                custom_field=props.get("CustomField", ""),
                custom_value=props.get("CustomValue", 0),
            )

    # Register the custom event type
    register_event_type(
        provider_guid="{00000000-0000-0000-0000-000000000000}",
        event_id=100,
        event_class=MyCustomEvent,
        provider_name="My-Custom-Provider",
    )

    print("Registered custom event type: MyCustomEvent")
    print("  Provider: My-Custom-Provider")
    print("  Event ID: 100")
    print("\nCustom events will now be auto-converted by to_typed_event()")


def main():
    """Run demos."""
    print("PyETWkit v1.1 Typed Events Demo")
    print("=" * 40)
    print("Note: Run as administrator")
    print("=" * 40)

    try:
        demo_typed_event_dict()
        demo_custom_typed_event()
        demo_process_events()

    except PermissionError:
        print("\nError: Administrator privileges required")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
