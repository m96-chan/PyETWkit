"""
PyETWkit - High-performance ETW consumer library for Python

A powerful and Pythonic library for consuming Windows ETW (Event Tracing for Windows)
events, built on top of ferrisetw (Rust) with pyo3 bindings.

Example usage:
    >>> from pyetwkit import EtwListener, EtwProvider
    >>>
    >>> # Create a listener for DNS events
    >>> provider = EtwProvider.dns_client()
    >>> with EtwListener(providers=[provider]) as listener:
    ...     for event in listener.events(timeout=10.0):
    ...         print(f"{event.timestamp}: {event.event_id}")

For async usage:
    >>> from pyetwkit import EtwStreamer, EtwProvider
    >>>
    >>> async def monitor_dns():
    ...     provider = EtwProvider.dns_client()
    ...     async with EtwStreamer(providers=[provider]) as streamer:
    ...         async for event in streamer:
    ...             print(f"{event.timestamp}: {event.event_id}")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

__version__ = "3.0.2"
__author__ = "m96-chan"

# Import core types from Rust extension
try:
    from pyetwkit._core import (
        EtwEvent,
        EtwProvider,
        EtwSession,
        EventFilter,
        SessionStats,
        raw,  # Low-level direct API
    )

    _CORE_AVAILABLE = True
except ImportError:
    _CORE_AVAILABLE = False
    # Provide stub types for type checking and documentation
    if TYPE_CHECKING:
        from pyetwkit._stubs import (
            EtwEvent,
            EtwProvider,
            EtwSession,
            EventFilter,
            SessionStats,
        )

# Import high-level Python APIs
# v1.1: Enhanced APIs
# Re-export KernelFlags and KernelSession from _core
import contextlib

from pyetwkit.async_api import AsyncEtwSession, EventBatcher, gather_events, stream_to_queue

# v3.0: Correlation Engine
from pyetwkit.correlation import (
    CorrelationConfig,
    CorrelationEngine,
    CorrelationGroup,
    CorrelationKeyType,
)

# v3.0: Dashboard
from pyetwkit.dashboard import Dashboard, DashboardConfig, EventSerializer, WebSocketHandler

# v3.0: OTLP Exporter
from pyetwkit.exporters import (
    ExportMode,
    OtlpExporter,
    OtlpExporterConfig,
    OtlpFileExporter,
    SpanMapper,
)
from pyetwkit.filtering import (
    EventFilter,
    EventFilterBuilder,
    event_id_filter,
    level_filter,
    process_filter,
    property_filter,
    provider_filter,
)
from pyetwkit.listener import EtwListener

# v2.0: Manifest-based typed events
from pyetwkit.manifest import (
    EventDefinition,
    FieldDefinition,
    ManifestCache,
    ManifestParser,
    ProviderManifest,
    TypedEventFactory,
)

# v2.0: Multi-session support
from pyetwkit.multi_session import MultiSession
from pyetwkit.providers import (
    FileProvider,
    KernelProvider,
    NetworkProvider,
    ProcessProvider,
    RegistryProvider,
)

# v3.0: Recording & Replay
from pyetwkit.recording import (
    CompressionType,
    EtwpackHeader,
    EtwpackIndex,
    Player,
    Recorder,
    RecorderConfig,
    convert_etl_to_etwpack,
)

# v2.0: Rust-side filtering
from pyetwkit.rust_filter import RustEventFilter
from pyetwkit.streamer import EtwStreamer
from pyetwkit.typed_events import (
    DnsQueryEvent,
    DnsResponseEvent,
    ImageLoadEvent,
    ProcessStartEvent,
    ProcessStopEvent,
    TcpConnectEvent,
    TcpDisconnectEvent,
    ThreadStartEvent,
    ThreadStopEvent,
    TypedEvent,
    to_typed_event,
)

with contextlib.suppress(ImportError):
    from pyetwkit._core import KernelFlags, KernelSession

__all__ = [
    # Version info
    "__version__",
    "__author__",
    # Core types (from Rust)
    "EtwEvent",
    "EtwProvider",
    "EtwSession",
    "SessionStats",
    # High-level APIs
    "EtwListener",
    "EtwStreamer",
    # Pre-configured providers
    "KernelProvider",
    "ProcessProvider",
    "NetworkProvider",
    "FileProvider",
    "RegistryProvider",
    # Low-level API
    "raw",
    # v1.1: Async API
    "AsyncEtwSession",
    "EventBatcher",
    "gather_events",
    "stream_to_queue",
    # v1.1: Filtering
    "EventFilter",
    "EventFilterBuilder",
    "event_id_filter",
    "level_filter",
    "process_filter",
    "property_filter",
    "provider_filter",
    # v1.1: Typed events
    "TypedEvent",
    "ProcessStartEvent",
    "ProcessStopEvent",
    "ThreadStartEvent",
    "ThreadStopEvent",
    "ImageLoadEvent",
    "DnsQueryEvent",
    "DnsResponseEvent",
    "TcpConnectEvent",
    "TcpDisconnectEvent",
    "to_typed_event",
    # v2.0: Multi-session
    "MultiSession",
    "KernelFlags",
    "KernelSession",
    # v2.0: Rust-side filtering
    "RustEventFilter",
    # v2.0: Manifest-based typed events
    "ManifestParser",
    "ProviderManifest",
    "EventDefinition",
    "FieldDefinition",
    "TypedEventFactory",
    "ManifestCache",
    # v3.0: Dashboard
    "Dashboard",
    "DashboardConfig",
    "EventSerializer",
    "WebSocketHandler",
    # v3.0: Correlation Engine
    "CorrelationEngine",
    "CorrelationConfig",
    "CorrelationGroup",
    "CorrelationKeyType",
    # v3.0: Recording & Replay
    "Recorder",
    "Player",
    "RecorderConfig",
    "EtwpackHeader",
    "EtwpackIndex",
    "CompressionType",
    "convert_etl_to_etwpack",
    # v3.0: OTLP Exporter
    "OtlpExporter",
    "OtlpExporterConfig",
    "OtlpFileExporter",
    "SpanMapper",
    "ExportMode",
]


def is_available() -> bool:
    """Check if the native extension is available.

    Returns:
        True if the Rust extension is loaded, False otherwise.
    """
    return _CORE_AVAILABLE


def check_admin() -> bool:
    """Check if the current process has administrator privileges.

    ETW operations require administrator privileges on Windows.

    Returns:
        True if running with admin privileges, False otherwise.
    """
    import ctypes

    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False
