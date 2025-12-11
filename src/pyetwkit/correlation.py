"""Event Correlation Engine (v3.0.0 - #50).

This module provides automatic event correlation from different ETW providers
using shared identifiers (PID, TID, Handle, SessionID) to build unified activity timelines.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


class CorrelationKeyType(Enum):
    """Types of correlation keys."""

    PID = "pid"
    TID = "tid"
    HANDLE = "handle"
    SESSION_ID = "session_id"
    CONNECTION_ID = "connection_id"


@dataclass
class CorrelationConfig:
    """Configuration for the CorrelationEngine."""

    time_window_ms: int = 1000
    max_events: int = 10000
    enable_handle_tracking: bool = True


@dataclass
class CorrelationGroup:
    """A group of correlated events.

    Represents events that are related by a shared correlation key
    such as PID, TID, or Handle.
    """

    key_type: str
    key_value: int | str
    events: list[Any] = field(default_factory=list)

    def timeline(self) -> list[Any]:
        """Get events sorted by timestamp.

        Returns:
            List of events in chronological order.
        """
        return sorted(self.events, key=lambda e: getattr(e, "timestamp", datetime.min))

    @property
    def pid(self) -> int | None:
        """Get the PID if this is a PID-based group."""
        if self.key_type == "pid":
            return int(self.key_value) if isinstance(self.key_value, (int, str)) else None
        return None


class CorrelationEngine:
    """Engine for correlating ETW events from multiple providers.

    Automatically links events by shared identifiers like PID, TID, and Handle
    to build unified activity timelines.

    Example:
        >>> engine = CorrelationEngine()
        >>> engine.add_provider("Microsoft-Windows-Kernel-Process")
        >>> engine.add_provider("Microsoft-Windows-Kernel-Network")
        >>>
        >>> for event in session.events():
        ...     engine.add_event(event)
        >>>
        >>> for group in engine.correlated_groups():
        ...     print(f"Activity for PID {group.pid}:")
        ...     for event in group.timeline():
        ...         print(f"  [{event.timestamp}] {event.provider_name}")
    """

    def __init__(self, config: CorrelationConfig | None = None) -> None:
        """Initialize the CorrelationEngine.

        Args:
            config: Optional correlation configuration.
        """
        self._config = config or CorrelationConfig()
        self._providers: list[str] = []
        self._events: list[Any] = []
        self._by_pid: dict[int, list[Any]] = defaultdict(list)
        self._by_tid: dict[int, list[Any]] = defaultdict(list)
        self._by_handle: dict[int, list[Any]] = defaultdict(list)

    @property
    def providers(self) -> list[str]:
        """Get the list of providers."""
        return list(self._providers)

    @property
    def event_count(self) -> int:
        """Get the total number of events."""
        return len(self._events)

    def add_provider(self, provider_guid: str) -> CorrelationEngine:
        """Add a provider to correlate.

        Args:
            provider_guid: Provider GUID string.

        Returns:
            Self for method chaining.
        """
        self._providers.append(provider_guid)
        return self

    def add_event(self, event: Any) -> None:
        """Add an event to the correlation engine.

        Args:
            event: ETW event to add.
        """
        self._events.append(event)

        # Index by PID
        pid = getattr(event, "process_id", None)
        if pid is not None:
            self._by_pid[pid].append(event)

        # Index by TID
        tid = getattr(event, "thread_id", None)
        if tid is not None:
            self._by_tid[tid].append(event)

        # Index by Handle if present
        if self._config.enable_handle_tracking:
            props = getattr(event, "properties", {})
            handle = props.get("handle") or props.get("Handle")
            if handle is not None:
                self._by_handle[handle].append(event)

        # Trim if over max_events
        if len(self._events) > self._config.max_events:
            self._trim_events()

    def _trim_events(self) -> None:
        """Trim old events to stay within max_events limit."""
        # Remove oldest events
        excess = len(self._events) - self._config.max_events
        if excess > 0:
            old_events = self._events[:excess]
            self._events = self._events[excess:]

            # Remove from indexes
            for event in old_events:
                pid = getattr(event, "process_id", None)
                if pid and event in self._by_pid.get(pid, []):
                    self._by_pid[pid].remove(event)

                tid = getattr(event, "thread_id", None)
                if tid and event in self._by_tid.get(tid, []):
                    self._by_tid[tid].remove(event)

    def correlate_by_pid(self, pid: int) -> list[Any]:
        """Get all events correlated by process ID.

        Args:
            pid: Process ID to correlate.

        Returns:
            List of events for the given PID, sorted by timestamp.
        """
        events = self._by_pid.get(pid, [])
        return sorted(events, key=lambda e: getattr(e, "timestamp", datetime.min))

    def correlate_by_tid(self, tid: int) -> list[Any]:
        """Get all events correlated by thread ID.

        Args:
            tid: Thread ID to correlate.

        Returns:
            List of events for the given TID, sorted by timestamp.
        """
        events = self._by_tid.get(tid, [])
        return sorted(events, key=lambda e: getattr(e, "timestamp", datetime.min))

    def correlate_by_handle(self, handle: int) -> list[Any]:
        """Get all events correlated by handle.

        Args:
            handle: Handle value to correlate.

        Returns:
            List of events for the given handle, sorted by timestamp.
        """
        events = self._by_handle.get(handle, [])
        return sorted(events, key=lambda e: getattr(e, "timestamp", datetime.min))

    def correlated_groups(self) -> Iterator[CorrelationGroup]:
        """Get all correlation groups.

        Yields:
            CorrelationGroup objects for each unique PID.
        """
        for pid, events in self._by_pid.items():
            if events:
                yield CorrelationGroup(
                    key_type="pid",
                    key_value=pid,
                    events=list(events),
                )

    def trace_causality(
        self,
        start_event: Any,
        target_type: str | None = None,
    ) -> list[Any]:
        """Trace causal chain from a starting event.

        Args:
            start_event: The event to start tracing from.
            target_type: Optional target event type (e.g., "file", "network").

        Returns:
            List of causally related events.
        """
        result = []
        pid = getattr(start_event, "process_id", None)
        start_time = getattr(start_event, "timestamp", datetime.min)

        if pid is not None:
            related = self._by_pid.get(pid, [])
            for event in related:
                event_time = getattr(event, "timestamp", datetime.min)
                # Only include events after the start event within time window
                if event_time >= start_time:
                    time_diff = (event_time - start_time).total_seconds() * 1000
                    if time_diff <= self._config.time_window_ms:
                        if target_type:
                            provider = getattr(event, "provider_name", "").lower()
                            if target_type.lower() in provider:
                                result.append(event)
                        else:
                            result.append(event)

        return sorted(result, key=lambda e: getattr(e, "timestamp", datetime.min))

    def to_timeline_json(self, pid: int | None = None) -> str:
        """Export correlation data to timeline JSON.

        Args:
            pid: Optional PID to filter by.

        Returns:
            JSON string representation of the timeline.
        """
        events = self.correlate_by_pid(pid) if pid is not None else self._events

        timeline = []
        for event in events:
            timeline.append(
                {
                    "timestamp": str(getattr(event, "timestamp", "")),
                    "provider": getattr(event, "provider_name", ""),
                    "event_id": getattr(event, "event_id", 0),
                    "pid": getattr(event, "process_id", 0),
                    "tid": getattr(event, "thread_id", 0),
                }
            )

        return json.dumps({"timeline": timeline}, indent=2)

    def to_dataframe(self, pid: int | None = None) -> dict[str, list[Any]]:
        """Export correlation data to DataFrame-compatible format.

        Args:
            pid: Optional PID to filter by.

        Returns:
            Dictionary that can be converted to pandas DataFrame.
        """
        events = self.correlate_by_pid(pid) if pid is not None else self._events

        data: dict[str, list[Any]] = {
            "timestamp": [],
            "provider": [],
            "event_id": [],
            "pid": [],
            "tid": [],
        }

        for event in events:
            data["timestamp"].append(getattr(event, "timestamp", None))
            data["provider"].append(getattr(event, "provider_name", ""))
            data["event_id"].append(getattr(event, "event_id", 0))
            data["pid"].append(getattr(event, "process_id", 0))
            data["tid"].append(getattr(event, "thread_id", 0))

        return data
