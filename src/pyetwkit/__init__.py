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

__version__ = "0.1.0"
__author__ = "m96-chan"

from typing import TYPE_CHECKING

# Import core types from Rust extension
try:
    from pyetwkit._core import (
        EtwEvent,
        EtwProvider,
        EtwSession,
        EventFilter,
        SessionStats,
    )
    from pyetwkit._core import raw  # Low-level direct API

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
from pyetwkit.listener import EtwListener
from pyetwkit.streamer import EtwStreamer
from pyetwkit.providers import (
    KernelProvider,
    ProcessProvider,
    NetworkProvider,
    FileProvider,
    RegistryProvider,
)

__all__ = [
    # Version info
    "__version__",
    "__author__",
    # Core types (from Rust)
    "EtwEvent",
    "EtwProvider",
    "EtwSession",
    "EventFilter",
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
