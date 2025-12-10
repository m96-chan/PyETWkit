"""
Type stubs for the native Rust extension.

These stubs provide type hints when the native extension is not available
(e.g., during documentation generation or type checking without building).
"""

from __future__ import annotations

from typing import Any


class EtwEvent:
    """ETW event data.

    Represents a parsed ETW event with all its properties and metadata.
    """

    @property
    def provider_id(self) -> str:
        """Provider GUID as string."""
        ...

    @property
    def provider_name(self) -> str | None:
        """Provider name (if known)."""
        ...

    @property
    def event_id(self) -> int:
        """Event ID."""
        ...

    @property
    def version(self) -> int:
        """Event version."""
        ...

    @property
    def opcode(self) -> int:
        """Event opcode."""
        ...

    @property
    def level(self) -> int:
        """Event level (0=Always to 5=Verbose)."""
        ...

    @property
    def keywords(self) -> int:
        """Event keywords bitmask."""
        ...

    @property
    def process_id(self) -> int:
        """Process ID that generated the event."""
        ...

    @property
    def thread_id(self) -> int:
        """Thread ID that generated the event."""
        ...

    @property
    def timestamp(self) -> str:
        """Timestamp as ISO 8601 string."""
        ...

    @property
    def timestamp_unix(self) -> int:
        """Timestamp as Unix timestamp (seconds)."""
        ...

    @property
    def timestamp_ns(self) -> int:
        """Timestamp as Unix timestamp (nanoseconds)."""
        ...

    @property
    def activity_id(self) -> str | None:
        """Activity ID for event correlation."""
        ...

    @property
    def related_activity_id(self) -> str | None:
        """Related activity ID."""
        ...

    @property
    def task(self) -> int:
        """Event task ID."""
        ...

    @property
    def channel(self) -> int:
        """Event channel."""
        ...

    @property
    def properties(self) -> dict[str, Any]:
        """Event properties as a dictionary."""
        ...

    def get(self, name: str) -> Any | None:
        """Get a property by name."""
        ...

    def get_string(self, name: str) -> str | None:
        """Get a property as string."""
        ...

    def get_u32(self, name: str) -> int | None:
        """Get a property as unsigned 32-bit integer."""
        ...

    def get_u64(self, name: str) -> int | None:
        """Get a property as unsigned 64-bit integer."""
        ...

    def has_property(self, name: str) -> bool:
        """Check if a property exists."""
        ...

    @property
    def stack_trace(self) -> list[int] | None:
        """Stack trace addresses (if captured)."""
        ...

    def to_json(self) -> str:
        """Convert to JSON string."""
        ...

    def to_json_pretty(self) -> str:
        """Convert to pretty JSON string."""
        ...


class EtwProvider:
    """ETW provider configuration.

    Defines which provider to trace and how to filter events.
    """

    def __init__(self, guid: str, name: str | None = None) -> None:
        """Create a provider from GUID string.

        Args:
            guid: Provider GUID as string (e.g., "22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716")
            name: Optional provider name for display purposes.
        """
        ...

    @staticmethod
    def kernel_process() -> EtwProvider:
        """Create a provider for kernel process events."""
        ...

    @staticmethod
    def dns_client() -> EtwProvider:
        """Create a provider for DNS client events."""
        ...

    @staticmethod
    def powershell() -> EtwProvider:
        """Create a provider for PowerShell events."""
        ...

    @property
    def guid(self) -> str:
        """Provider GUID."""
        ...

    @property
    def name(self) -> str | None:
        """Provider name."""
        ...

    def level(self, level: int) -> EtwProvider:
        """Set trace level (0=Always to 5=Verbose)."""
        ...

    def keywords_any(self, keywords: int) -> EtwProvider:
        """Set keywords (any match)."""
        ...

    def keywords_all(self, keywords: int) -> EtwProvider:
        """Set keywords (all must match)."""
        ...

    def event_ids(self, ids: list[int]) -> EtwProvider:
        """Filter by specific event IDs."""
        ...

    def process_id(self, pid: int) -> EtwProvider:
        """Filter by process ID."""
        ...

    def stack_trace(self, enabled: bool) -> EtwProvider:
        """Enable stack trace capture."""
        ...


class EtwSession:
    """ETW trace session.

    Low-level session management. Prefer EtwListener or EtwStreamer for most uses.
    """

    def __init__(self, name: str | None = None) -> None:
        """Create a new session."""
        ...

    @staticmethod
    def with_config(
        name: str | None = None,
        buffer_size_kb: int = 64,
        min_buffers: int = 64,
        max_buffers: int = 128,
        channel_capacity: int = 10000,
    ) -> EtwSession:
        """Create a session with custom configuration."""
        ...

    def add_provider(self, provider: EtwProvider) -> None:
        """Add a provider to the session."""
        ...

    def start(self) -> None:
        """Start the session."""
        ...

    def stop(self) -> None:
        """Stop the session."""
        ...

    def next_event(self) -> EtwEvent | None:
        """Get the next event (blocking)."""
        ...

    def next_event_timeout(self, timeout_ms: int) -> EtwEvent | None:
        """Get the next event with timeout."""
        ...

    def try_next_event(self) -> EtwEvent | None:
        """Try to get the next event (non-blocking)."""
        ...

    def stats(self) -> SessionStats:
        """Get session statistics."""
        ...

    def is_running(self) -> bool:
        """Check if session is running."""
        ...

    @property
    def name(self) -> str | None:
        """Session name."""
        ...


class EventFilter:
    """Event filter configuration."""

    def __init__(self) -> None:
        """Create a new empty filter."""
        ...

    def event_ids(self, ids: list[int]) -> EventFilter:
        """Filter by event IDs."""
        ...

    def opcodes(self, opcodes: list[int]) -> EventFilter:
        """Filter by opcodes."""
        ...

    def process_id(self, pid: int) -> EventFilter:
        """Filter by process ID."""
        ...

    def process_name(self, name: str) -> EventFilter:
        """Filter by process name (substring match)."""
        ...

    def exclude_event_ids(self, ids: list[int]) -> EventFilter:
        """Exclude specific event IDs."""
        ...

    def matches(self, event_id: int, opcode: int) -> bool:
        """Check if the filter matches."""
        ...


class SessionStats:
    """Session statistics."""

    @property
    def events_received(self) -> int:
        """Number of events received."""
        ...

    @property
    def events_processed(self) -> int:
        """Number of events processed."""
        ...

    @property
    def events_lost(self) -> int:
        """Number of events lost."""
        ...

    @property
    def buffers_lost(self) -> int:
        """Number of buffers lost."""
        ...

    @property
    def buffers_read(self) -> int:
        """Number of buffers read."""
        ...

    @property
    def buffer_size_kb(self) -> int:
        """Buffer size in KB."""
        ...

    @property
    def buffers_allocated(self) -> int:
        """Number of buffers allocated."""
        ...

    @property
    def duration_secs(self) -> float:
        """Session duration in seconds."""
        ...

    @property
    def events_per_second(self) -> float:
        """Events per second."""
        ...

    def has_loss(self) -> bool:
        """Check if any events were lost."""
        ...

    def loss_percentage(self) -> float:
        """Get loss percentage."""
        ...

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        ...
