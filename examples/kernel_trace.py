"""Kernel ETW trace example.

This example shows how to monitor kernel events like process
creation and termination. Run as administrator.
"""

from pyetwkit._core import KernelSession


def main():
    # Create kernel session with process tracking
    session = KernelSession()
    session.enable_process()  # Enable process events

    print("Starting kernel trace for process events... Press Ctrl+C to stop")
    session.start()

    try:
        event_count = 0
        while True:
            event = session.next_event_timeout(1000)
            if event is None:
                continue

            event_count += 1
            props = event.to_dict().get("properties", {})

            # Show process events
            if event.event_id == 1:  # Process Start
                print(f"[PROCESS START] PID: {props.get('ProcessId')}")
                print(f"  Image: {props.get('ImageFileName')}")
                print(f"  CommandLine: {props.get('CommandLine', 'N/A')}")
            elif event.event_id == 2:  # Process End
                print(f"[PROCESS END] PID: {props.get('ProcessId')}")
            else:
                print(f"[Event {event.event_id}] {event.provider_name}")

    except KeyboardInterrupt:
        print(f"\nStopping... Captured {event_count} events")
    finally:
        if session.is_running():
            session.stop()


if __name__ == "__main__":
    main()
