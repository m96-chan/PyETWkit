"""Advanced event filtering for ETW sessions.

This module provides a fluent API for building event filters that
can be applied at the Python or Rust level for optimal performance.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyetwkit._core import EtwEvent


@dataclass
class FilterRule:
    """A single filter rule."""

    field: str
    operator: str
    value: Any
    negate: bool = False

    def matches(self, event: EtwEvent) -> bool:
        """Check if event matches this rule."""
        # Get field value from event
        if self.field == "event_id":
            actual = event.event_id
        elif self.field == "process_id":
            actual = event.process_id
        elif self.field == "thread_id":
            actual = event.thread_id
        elif self.field == "provider_name":
            actual = event.provider_name or ""
        elif self.field == "level":
            actual = event.level
        elif self.field == "opcode":
            actual = event.opcode
        else:
            # Check in properties
            props = event.to_dict().get("properties", {})
            actual = props.get(self.field)

        if actual is None:
            result = False
        elif self.operator == "eq":
            result = actual == self.value
        elif self.operator == "ne":
            result = actual != self.value
        elif self.operator == "in":
            result = actual in self.value
        elif self.operator == "not_in":
            result = actual not in self.value
        elif self.operator == "contains":
            result = str(self.value).lower() in str(actual).lower()
        elif self.operator == "startswith":
            result = str(actual).lower().startswith(str(self.value).lower())
        elif self.operator == "endswith":
            result = str(actual).lower().endswith(str(self.value).lower())
        elif self.operator == "regex":
            result = bool(re.search(self.value, str(actual)))
        elif self.operator == "gt":
            result = actual > self.value
        elif self.operator == "gte":
            result = actual >= self.value
        elif self.operator == "lt":
            result = actual < self.value
        elif self.operator == "lte":
            result = actual <= self.value
        else:
            result = False

        return not result if self.negate else result


@dataclass
class EventFilterBuilder:
    """Fluent builder for event filters.

    Provides a chainable API for building complex event filters
    with support for multiple conditions and operators.

    Example:
        >>> filter = (
        ...     EventFilterBuilder()
        ...     .event_ids([1, 2, 3])
        ...     .process_id(1234)
        ...     .property_contains("ImageFileName", "chrome")
        ...     .level_max(4)
        ...     .build()
        ... )
        >>> for event in session.events():
        ...     if filter.matches(event):
        ...         process(event)
    """

    rules: list[FilterRule] = field(default_factory=list)
    _match_all: bool = True  # AND mode by default

    def event_id(self, event_id: int) -> EventFilterBuilder:
        """Filter by exact event ID."""
        self.rules.append(FilterRule("event_id", "eq", event_id))
        return self

    def event_ids(self, ids: Sequence[int]) -> EventFilterBuilder:
        """Filter by multiple event IDs (OR)."""
        self.rules.append(FilterRule("event_id", "in", list(ids)))
        return self

    def exclude_event_ids(self, ids: Sequence[int]) -> EventFilterBuilder:
        """Exclude specific event IDs."""
        self.rules.append(FilterRule("event_id", "not_in", list(ids)))
        return self

    def process_id(self, pid: int) -> EventFilterBuilder:
        """Filter by process ID."""
        self.rules.append(FilterRule("process_id", "eq", pid))
        return self

    def process_ids(self, pids: Sequence[int]) -> EventFilterBuilder:
        """Filter by multiple process IDs."""
        self.rules.append(FilterRule("process_id", "in", list(pids)))
        return self

    def thread_id(self, tid: int) -> EventFilterBuilder:
        """Filter by thread ID."""
        self.rules.append(FilterRule("thread_id", "eq", tid))
        return self

    def provider_name(self, name: str) -> EventFilterBuilder:
        """Filter by provider name (exact match)."""
        self.rules.append(FilterRule("provider_name", "eq", name))
        return self

    def provider_contains(self, substring: str) -> EventFilterBuilder:
        """Filter by provider name containing substring."""
        self.rules.append(FilterRule("provider_name", "contains", substring))
        return self

    def level(self, level: int) -> EventFilterBuilder:
        """Filter by exact level."""
        self.rules.append(FilterRule("level", "eq", level))
        return self

    def level_max(self, max_level: int) -> EventFilterBuilder:
        """Filter by maximum level (include lower severity)."""
        self.rules.append(FilterRule("level", "lte", max_level))
        return self

    def level_min(self, min_level: int) -> EventFilterBuilder:
        """Filter by minimum level."""
        self.rules.append(FilterRule("level", "gte", min_level))
        return self

    def opcode(self, opcode: int) -> EventFilterBuilder:
        """Filter by opcode."""
        self.rules.append(FilterRule("opcode", "eq", opcode))
        return self

    def opcodes(self, opcodes: Sequence[int]) -> EventFilterBuilder:
        """Filter by multiple opcodes."""
        self.rules.append(FilterRule("opcode", "in", list(opcodes)))
        return self

    def property_equals(self, name: str, value: Any) -> EventFilterBuilder:
        """Filter by property value equality."""
        self.rules.append(FilterRule(name, "eq", value))
        return self

    def property_contains(self, name: str, substring: str) -> EventFilterBuilder:
        """Filter by property containing substring."""
        self.rules.append(FilterRule(name, "contains", substring))
        return self

    def property_startswith(self, name: str, prefix: str) -> EventFilterBuilder:
        """Filter by property starting with prefix."""
        self.rules.append(FilterRule(name, "startswith", prefix))
        return self

    def property_endswith(self, name: str, suffix: str) -> EventFilterBuilder:
        """Filter by property ending with suffix."""
        self.rules.append(FilterRule(name, "endswith", suffix))
        return self

    def property_regex(self, name: str, pattern: str) -> EventFilterBuilder:
        """Filter by property matching regex pattern."""
        self.rules.append(FilterRule(name, "regex", pattern))
        return self

    def property_gt(self, name: str, value: Any) -> EventFilterBuilder:
        """Filter by property greater than value."""
        self.rules.append(FilterRule(name, "gt", value))
        return self

    def property_lt(self, name: str, value: Any) -> EventFilterBuilder:
        """Filter by property less than value."""
        self.rules.append(FilterRule(name, "lt", value))
        return self

    def custom(self, predicate: Callable[[EtwEvent], bool]) -> EventFilterBuilder:
        """Add a custom filter predicate."""
        # Wrap in a special rule that uses the predicate
        rule = FilterRule("_custom", "custom", predicate)
        rule.matches = lambda e: predicate(e)  # type: ignore
        self.rules.append(rule)
        return self

    def match_any(self) -> EventFilterBuilder:
        """Switch to OR mode (match any rule)."""
        self._match_all = False
        return self

    def match_all(self) -> EventFilterBuilder:
        """Switch to AND mode (match all rules)."""
        self._match_all = True
        return self

    def build(self) -> EventFilter:
        """Build the final filter."""
        return EventFilter(self.rules.copy(), self._match_all)

    def __call__(self, event: EtwEvent) -> bool:
        """Allow using builder directly as a filter."""
        return self.build().matches(event)


@dataclass
class EventFilter:
    """Compiled event filter for efficient matching."""

    rules: list[FilterRule]
    match_all: bool = True

    def matches(self, event: EtwEvent) -> bool:
        """Check if event matches the filter."""
        if not self.rules:
            return True

        if self.match_all:
            return all(rule.matches(event) for rule in self.rules)
        else:
            return any(rule.matches(event) for rule in self.rules)

    def __call__(self, event: EtwEvent) -> bool:
        """Allow using filter as a callable."""
        return self.matches(event)

    def __and__(self, other: EventFilter) -> EventFilter:
        """Combine filters with AND."""
        return EventFilter(self.rules + other.rules, match_all=True)

    def __or__(self, other: EventFilter) -> EventFilter:
        """Combine filters with OR."""
        combined = EventFilter(self.rules + other.rules, match_all=False)
        return combined


# Convenience functions for common filters


def process_filter(pid: int) -> EventFilter:
    """Create a filter for a specific process."""
    return EventFilterBuilder().process_id(pid).build()


def event_id_filter(*event_ids: int) -> EventFilter:
    """Create a filter for specific event IDs."""
    return EventFilterBuilder().event_ids(list(event_ids)).build()


def provider_filter(name: str) -> EventFilter:
    """Create a filter for a specific provider."""
    return EventFilterBuilder().provider_contains(name).build()


def level_filter(max_level: int = 4) -> EventFilter:
    """Create a filter for events up to a severity level."""
    return EventFilterBuilder().level_max(max_level).build()


def property_filter(name: str, value: Any) -> EventFilter:
    """Create a filter for a property value."""
    return EventFilterBuilder().property_equals(name, value).build()


__all__ = [
    "FilterRule",
    "EventFilterBuilder",
    "EventFilter",
    # Convenience functions
    "process_filter",
    "event_id_filter",
    "provider_filter",
    "level_filter",
    "property_filter",
]
