"""Re-export native extension module.

This module re-exports all symbols from the native Rust extension (pyetwkit_core)
to provide a consistent import path within the pyetwkit package.
"""

# Re-export everything from the native extension
from pyetwkit_core import *  # noqa: F401, F403
from pyetwkit_core import (
    # Enable properties
    EnableProperty,
    # ETL Reader
    EtlReader,
    EtwEvent,
    EtwProvider,
    EtwSession,
    EventFilter,
    # Schema
    EventSchema,
    KernelFlags,
    # Kernel
    KernelSession,
    PropertyInfo,
    ProviderDetails,
    ProviderInfo,
    SchemaCache,
    SessionStats,
    get_provider_info,
    # Discovery
    list_providers,
    search_providers,
)

# Try to import raw submodule
try:
    from pyetwkit_core import raw
except ImportError:
    raw = None  # type: ignore

__all__ = [
    "EtwEvent",
    "EtwProvider",
    "EtwSession",
    "EventFilter",
    "SessionStats",
    "list_providers",
    "search_providers",
    "get_provider_info",
    "ProviderInfo",
    "ProviderDetails",
    "EtlReader",
    "EnableProperty",
    "EventSchema",
    "PropertyInfo",
    "SchemaCache",
    "KernelSession",
    "KernelFlags",
    "raw",
]
