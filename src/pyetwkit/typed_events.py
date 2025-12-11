"""Typed ETW events based on provider schemas.

This module provides strongly-typed event classes generated from
ETW provider manifests, enabling IDE autocomplete and type checking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar

from pyetwkit._core import EtwEvent


@dataclass
class TypedEvent:
    """Base class for typed ETW events.

    Provides common event properties and conversion from raw EtwEvent.
    """

    # Class-level metadata
    PROVIDER_NAME: ClassVar[str] = ""
    PROVIDER_GUID: ClassVar[str] = ""
    EVENT_ID: ClassVar[int] = 0
    EVENT_NAME: ClassVar[str] = ""

    # Common event properties
    timestamp: datetime = field(default_factory=datetime.now)
    process_id: int = 0
    thread_id: int = 0
    event_id: int = 0
    opcode: int = 0
    level: int = 0

    @classmethod
    def from_event(cls, event: EtwEvent) -> TypedEvent:
        """Create a typed event from a raw EtwEvent."""
        return cls(
            timestamp=event.timestamp,
            process_id=event.process_id,
            thread_id=event.thread_id,
            event_id=event.event_id,
            opcode=event.opcode,
            level=event.level,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "provider_name": self.PROVIDER_NAME,
            "event_name": self.EVENT_NAME,
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "process_id": self.process_id,
            "thread_id": self.thread_id,
        }


# ============================================================================
# Microsoft-Windows-Kernel-Process events
# ============================================================================


@dataclass
class ProcessStartEvent(TypedEvent):
    """Process start event (Event ID 1).

    Fired when a new process is created.
    """

    PROVIDER_NAME: ClassVar[str] = "Microsoft-Windows-Kernel-Process"
    PROVIDER_GUID: ClassVar[str] = "{22FB2CD6-0E7B-422B-A0C7-2FAD1FD0E716}"
    EVENT_ID: ClassVar[int] = 1
    EVENT_NAME: ClassVar[str] = "ProcessStart"

    # Process-specific properties
    image_file_name: str = ""
    command_line: str = ""
    parent_process_id: int = 0
    session_id: int = 0
    create_time: datetime | None = None
    flags: int = 0

    @classmethod
    def from_event(cls, event: EtwEvent) -> ProcessStartEvent:
        """Create from raw event."""
        props = event.to_dict().get("properties", {})
        return cls(
            timestamp=event.timestamp,
            process_id=event.process_id,
            thread_id=event.thread_id,
            event_id=event.event_id,
            opcode=event.opcode,
            level=event.level,
            image_file_name=props.get("ImageFileName", ""),
            command_line=props.get("CommandLine", ""),
            parent_process_id=props.get("ParentProcessId", 0),
            session_id=props.get("SessionId", 0),
            flags=props.get("Flags", 0),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        d = super().to_dict()
        d.update(
            {
                "image_file_name": self.image_file_name,
                "command_line": self.command_line,
                "parent_process_id": self.parent_process_id,
                "session_id": self.session_id,
            }
        )
        return d


@dataclass
class ProcessStopEvent(TypedEvent):
    """Process stop event (Event ID 2).

    Fired when a process exits.
    """

    PROVIDER_NAME: ClassVar[str] = "Microsoft-Windows-Kernel-Process"
    PROVIDER_GUID: ClassVar[str] = "{22FB2CD6-0E7B-422B-A0C7-2FAD1FD0E716}"
    EVENT_ID: ClassVar[int] = 2
    EVENT_NAME: ClassVar[str] = "ProcessStop"

    image_file_name: str = ""
    exit_code: int = 0
    exit_time: datetime | None = None

    @classmethod
    def from_event(cls, event: EtwEvent) -> ProcessStopEvent:
        """Create from raw event."""
        props = event.to_dict().get("properties", {})
        return cls(
            timestamp=event.timestamp,
            process_id=event.process_id,
            thread_id=event.thread_id,
            event_id=event.event_id,
            opcode=event.opcode,
            level=event.level,
            image_file_name=props.get("ImageFileName", ""),
            exit_code=props.get("ExitCode", 0),
        )


@dataclass
class ThreadStartEvent(TypedEvent):
    """Thread start event (Event ID 3)."""

    PROVIDER_NAME: ClassVar[str] = "Microsoft-Windows-Kernel-Process"
    EVENT_ID: ClassVar[int] = 3
    EVENT_NAME: ClassVar[str] = "ThreadStart"

    start_address: int = 0
    win32_start_address: int = 0
    sub_process_tag: int = 0

    @classmethod
    def from_event(cls, event: EtwEvent) -> ThreadStartEvent:
        """Create from raw event."""
        props = event.to_dict().get("properties", {})
        return cls(
            timestamp=event.timestamp,
            process_id=event.process_id,
            thread_id=event.thread_id,
            event_id=event.event_id,
            opcode=event.opcode,
            level=event.level,
            start_address=props.get("StartAddr", 0),
            win32_start_address=props.get("Win32StartAddr", 0),
            sub_process_tag=props.get("SubProcessTag", 0),
        )


@dataclass
class ThreadStopEvent(TypedEvent):
    """Thread stop event (Event ID 4)."""

    PROVIDER_NAME: ClassVar[str] = "Microsoft-Windows-Kernel-Process"
    EVENT_ID: ClassVar[int] = 4
    EVENT_NAME: ClassVar[str] = "ThreadStop"

    @classmethod
    def from_event(cls, event: EtwEvent) -> ThreadStopEvent:
        """Create from raw event."""
        return cls(
            timestamp=event.timestamp,
            process_id=event.process_id,
            thread_id=event.thread_id,
            event_id=event.event_id,
            opcode=event.opcode,
            level=event.level,
        )


@dataclass
class ImageLoadEvent(TypedEvent):
    """Image/DLL load event (Event ID 5)."""

    PROVIDER_NAME: ClassVar[str] = "Microsoft-Windows-Kernel-Process"
    EVENT_ID: ClassVar[int] = 5
    EVENT_NAME: ClassVar[str] = "ImageLoad"

    image_base: int = 0
    image_size: int = 0
    image_name: str = ""
    image_checksum: int = 0

    @classmethod
    def from_event(cls, event: EtwEvent) -> ImageLoadEvent:
        """Create from raw event."""
        props = event.to_dict().get("properties", {})
        return cls(
            timestamp=event.timestamp,
            process_id=event.process_id,
            thread_id=event.thread_id,
            event_id=event.event_id,
            opcode=event.opcode,
            level=event.level,
            image_base=props.get("ImageBase", 0),
            image_size=props.get("ImageSize", 0),
            image_name=props.get("ImageName", ""),
            image_checksum=props.get("ImageChecksum", 0),
        )


# ============================================================================
# Microsoft-Windows-DNS-Client events
# ============================================================================


@dataclass
class DnsQueryEvent(TypedEvent):
    """DNS query event."""

    PROVIDER_NAME: ClassVar[str] = "Microsoft-Windows-DNS-Client"
    PROVIDER_GUID: ClassVar[str] = "{1C95126E-7EEA-49A9-A3FE-A378B03DDB4D}"
    EVENT_ID: ClassVar[int] = 3006
    EVENT_NAME: ClassVar[str] = "DnsQuery"

    query_name: str = ""
    query_type: int = 0
    query_options: int = 0
    server_list: str = ""
    is_network_query: bool = False
    network_query_index: int = 0
    interface_index: int = 0

    @classmethod
    def from_event(cls, event: EtwEvent) -> DnsQueryEvent:
        """Create from raw event."""
        props = event.to_dict().get("properties", {})
        return cls(
            timestamp=event.timestamp,
            process_id=event.process_id,
            thread_id=event.thread_id,
            event_id=event.event_id,
            opcode=event.opcode,
            level=event.level,
            query_name=props.get("QueryName", ""),
            query_type=props.get("QueryType", 0),
            query_options=props.get("QueryOptions", 0),
            server_list=props.get("ServerList", ""),
            is_network_query=props.get("IsNetworkQuery", False),
        )


@dataclass
class DnsResponseEvent(TypedEvent):
    """DNS response event."""

    PROVIDER_NAME: ClassVar[str] = "Microsoft-Windows-DNS-Client"
    EVENT_ID: ClassVar[int] = 3008
    EVENT_NAME: ClassVar[str] = "DnsResponse"

    query_name: str = ""
    query_type: int = 0
    query_status: int = 0
    query_results: str = ""

    @classmethod
    def from_event(cls, event: EtwEvent) -> DnsResponseEvent:
        """Create from raw event."""
        props = event.to_dict().get("properties", {})
        return cls(
            timestamp=event.timestamp,
            process_id=event.process_id,
            thread_id=event.thread_id,
            event_id=event.event_id,
            opcode=event.opcode,
            level=event.level,
            query_name=props.get("QueryName", ""),
            query_type=props.get("QueryType", 0),
            query_status=props.get("QueryStatus", 0),
            query_results=props.get("QueryResults", ""),
        )


# ============================================================================
# Network events
# ============================================================================


@dataclass
class TcpConnectEvent(TypedEvent):
    """TCP connection event."""

    PROVIDER_NAME: ClassVar[str] = "Microsoft-Windows-Kernel-Network"
    EVENT_ID: ClassVar[int] = 10
    EVENT_NAME: ClassVar[str] = "TcpConnect"

    local_address: str = ""
    local_port: int = 0
    remote_address: str = ""
    remote_port: int = 0

    @classmethod
    def from_event(cls, event: EtwEvent) -> TcpConnectEvent:
        """Create from raw event."""
        props = event.to_dict().get("properties", {})
        return cls(
            timestamp=event.timestamp,
            process_id=event.process_id,
            thread_id=event.thread_id,
            event_id=event.event_id,
            opcode=event.opcode,
            level=event.level,
            local_address=props.get("LocalAddress", ""),
            local_port=props.get("LocalPort", 0),
            remote_address=props.get("RemoteAddress", ""),
            remote_port=props.get("RemotePort", 0),
        )


@dataclass
class TcpDisconnectEvent(TypedEvent):
    """TCP disconnect event."""

    PROVIDER_NAME: ClassVar[str] = "Microsoft-Windows-Kernel-Network"
    EVENT_ID: ClassVar[int] = 11
    EVENT_NAME: ClassVar[str] = "TcpDisconnect"

    local_address: str = ""
    local_port: int = 0
    remote_address: str = ""
    remote_port: int = 0

    @classmethod
    def from_event(cls, event: EtwEvent) -> TcpDisconnectEvent:
        """Create from raw event."""
        props = event.to_dict().get("properties", {})
        return cls(
            timestamp=event.timestamp,
            process_id=event.process_id,
            thread_id=event.thread_id,
            event_id=event.event_id,
            opcode=event.opcode,
            level=event.level,
            local_address=props.get("LocalAddress", ""),
            local_port=props.get("LocalPort", 0),
            remote_address=props.get("RemoteAddress", ""),
            remote_port=props.get("RemotePort", 0),
        )


# ============================================================================
# Event type registry and conversion
# ============================================================================


# Registry of typed events by (provider_guid, event_id)
EVENT_TYPE_REGISTRY: dict[tuple[str, int], type[TypedEvent]] = {
    # Kernel Process
    ("{22FB2CD6-0E7B-422B-A0C7-2FAD1FD0E716}", 1): ProcessStartEvent,
    ("{22FB2CD6-0E7B-422B-A0C7-2FAD1FD0E716}", 2): ProcessStopEvent,
    ("{22FB2CD6-0E7B-422B-A0C7-2FAD1FD0E716}", 3): ThreadStartEvent,
    ("{22FB2CD6-0E7B-422B-A0C7-2FAD1FD0E716}", 4): ThreadStopEvent,
    ("{22FB2CD6-0E7B-422B-A0C7-2FAD1FD0E716}", 5): ImageLoadEvent,
    # DNS Client
    ("{1C95126E-7EEA-49A9-A3FE-A378B03DDB4D}", 3006): DnsQueryEvent,
    ("{1C95126E-7EEA-49A9-A3FE-A378B03DDB4D}", 3008): DnsResponseEvent,
    # Kernel Network
    ("{7DD42A49-5329-4832-8DFD-43D979153A88}", 10): TcpConnectEvent,
    ("{7DD42A49-5329-4832-8DFD-43D979153A88}", 11): TcpDisconnectEvent,
}

# Registry by provider name and event id (for convenience)
EVENT_TYPE_BY_NAME: dict[tuple[str, int], type[TypedEvent]] = {
    ("Microsoft-Windows-Kernel-Process", 1): ProcessStartEvent,
    ("Microsoft-Windows-Kernel-Process", 2): ProcessStopEvent,
    ("Microsoft-Windows-Kernel-Process", 3): ThreadStartEvent,
    ("Microsoft-Windows-Kernel-Process", 4): ThreadStopEvent,
    ("Microsoft-Windows-Kernel-Process", 5): ImageLoadEvent,
    ("Microsoft-Windows-DNS-Client", 3006): DnsQueryEvent,
    ("Microsoft-Windows-DNS-Client", 3008): DnsResponseEvent,
    ("Microsoft-Windows-Kernel-Network", 10): TcpConnectEvent,
    ("Microsoft-Windows-Kernel-Network", 11): TcpDisconnectEvent,
}


def to_typed_event(event: EtwEvent) -> TypedEvent:
    """Convert a raw EtwEvent to its typed equivalent.

    Args:
        event: Raw EtwEvent from the ETW session

    Returns:
        TypedEvent subclass if a matching type is registered,
        otherwise a generic TypedEvent

    Example:
        >>> for raw_event in session.events():
        ...     event = to_typed_event(raw_event)
        ...     if isinstance(event, ProcessStartEvent):
        ...         print(f"Process started: {event.image_file_name}")
    """
    # Try by provider GUID first
    provider_id = str(event.provider_id) if event.provider_id else ""
    key = (provider_id.upper(), event.event_id)
    event_class = EVENT_TYPE_REGISTRY.get(key)

    if event_class is None and event.provider_name:
        # Try by provider name
        key = (event.provider_name, event.event_id)
        event_class = EVENT_TYPE_BY_NAME.get(key)

    if event_class is not None:
        return event_class.from_event(event)

    # Fall back to generic TypedEvent
    return TypedEvent.from_event(event)


def register_event_type(
    provider_guid: str,
    event_id: int,
    event_class: type[TypedEvent],
    provider_name: str | None = None,
) -> None:
    """Register a custom typed event class.

    Args:
        provider_guid: Provider GUID (with braces)
        event_id: Event ID
        event_class: TypedEvent subclass
        provider_name: Optional provider name for name-based lookup
    """
    EVENT_TYPE_REGISTRY[(provider_guid.upper(), event_id)] = event_class
    if provider_name:
        EVENT_TYPE_BY_NAME[(provider_name, event_id)] = event_class


__all__ = [
    # Base class
    "TypedEvent",
    # Process events
    "ProcessStartEvent",
    "ProcessStopEvent",
    "ThreadStartEvent",
    "ThreadStopEvent",
    "ImageLoadEvent",
    # DNS events
    "DnsQueryEvent",
    "DnsResponseEvent",
    # Network events
    "TcpConnectEvent",
    "TcpDisconnectEvent",
    # Conversion functions
    "to_typed_event",
    "register_event_type",
    # Registry
    "EVENT_TYPE_REGISTRY",
    "EVENT_TYPE_BY_NAME",
]
