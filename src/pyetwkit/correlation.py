"""Event Correlation Engine (v3.0.0 - #50).

This module provides automatic event correlation from different ETW providers
using shared identifiers (PID, TID, Handle, SessionID) to build unified activity timelines.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict, deque
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


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
        self._events: deque[Any] = deque()
        self._event_id_counter = 0
        # Use dict[int, event] for O(1) deletion instead of list
        self._by_pid: dict[int, dict[int, Any]] = defaultdict(dict)
        self._by_tid: dict[int, dict[int, Any]] = defaultdict(dict)
        self._by_handle: dict[int, dict[int, Any]] = defaultdict(dict)

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
        # Assign internal ID for O(1) deletion
        event_id = self._event_id_counter
        self._event_id_counter += 1
        event._correlation_id = event_id  # type: ignore[attr-defined]

        self._events.append(event)

        # Index by PID
        pid = getattr(event, "process_id", None)
        if pid is not None:
            self._by_pid[pid][event_id] = event

        # Index by TID
        tid = getattr(event, "thread_id", None)
        if tid is not None:
            self._by_tid[tid][event_id] = event

        # Index by Handle if present
        if self._config.enable_handle_tracking:
            props = getattr(event, "properties", {})
            handle = props.get("handle") or props.get("Handle")
            if handle is not None:
                self._by_handle[handle][event_id] = event

        # Trim if over max_events
        if len(self._events) > self._config.max_events:
            self._trim_events()

    def _trim_events(self) -> None:
        """Trim old events to stay within max_events limit (O(1) per event)."""
        excess = len(self._events) - self._config.max_events
        for _ in range(excess):
            old_event = self._events.popleft()
            event_id = getattr(old_event, "_correlation_id", None)
            if event_id is None:
                continue

            # O(1) deletion from indexes
            pid = getattr(old_event, "process_id", None)
            if pid is not None and event_id in self._by_pid.get(pid, {}):
                del self._by_pid[pid][event_id]

            tid = getattr(old_event, "thread_id", None)
            if tid is not None and event_id in self._by_tid.get(tid, {}):
                del self._by_tid[tid][event_id]

            if self._config.enable_handle_tracking:
                props = getattr(old_event, "properties", {})
                handle = props.get("handle") or props.get("Handle")
                if handle is not None and event_id in self._by_handle.get(handle, {}):
                    del self._by_handle[handle][event_id]

    def _sort_by_timestamp(self, events: list[Any]) -> list[Any]:
        """Sort events by timestamp (common helper method).

        Args:
            events: List of events to sort.

        Returns:
            Sorted list of events.
        """
        return sorted(events, key=lambda e: getattr(e, "timestamp", datetime.min))

    def correlate_by_pid(self, pid: int) -> list[Any]:
        """Get all events correlated by process ID.

        Args:
            pid: Process ID to correlate.

        Returns:
            List of events for the given PID, sorted by timestamp.
        """
        events = list(self._by_pid.get(pid, {}).values())
        return self._sort_by_timestamp(events)

    def correlate_by_tid(self, tid: int) -> list[Any]:
        """Get all events correlated by thread ID.

        Args:
            tid: Thread ID to correlate.

        Returns:
            List of events for the given TID, sorted by timestamp.
        """
        events = list(self._by_tid.get(tid, {}).values())
        return self._sort_by_timestamp(events)

    def correlate_by_handle(self, handle: int) -> list[Any]:
        """Get all events correlated by handle.

        Args:
            handle: Handle value to correlate.

        Returns:
            List of events for the given handle, sorted by timestamp.
        """
        events = list(self._by_handle.get(handle, {}).values())
        return self._sort_by_timestamp(events)

    def correlated_groups(self) -> Iterator[CorrelationGroup]:
        """Get all correlation groups.

        Yields:
            CorrelationGroup objects for each unique PID.
        """
        for pid, events_dict in self._by_pid.items():
            if events_dict:
                yield CorrelationGroup(
                    key_type="pid",
                    key_value=pid,
                    events=list(events_dict.values()),
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
        target_lower = target_type.lower() if target_type else None

        if pid is not None:
            related = self._by_pid.get(pid, {}).values()
            for event in related:
                event_time = getattr(event, "timestamp", datetime.min)
                # Only include events after the start event within time window
                if event_time < start_time:
                    continue

                time_diff = (event_time - start_time).total_seconds() * 1000
                if time_diff > self._config.time_window_ms:
                    continue

                if target_lower:
                    provider = getattr(event, "provider_name", "").lower()
                    if target_lower not in provider:
                        continue

                result.append(event)

        return self._sort_by_timestamp(result)

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
