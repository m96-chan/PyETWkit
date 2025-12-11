"""Real-time event filtering callbacks (v2.0.0 - #56).

This module provides Rust-side event filtering for high-performance
event filtering before events reach Python.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


@dataclass
class FilterSpec:
    """Internal specification for a filter condition."""

    filter_type: str
    field_name: str | None = None
    value: Any = None
    pattern: str | None = None


class RustEventFilter:
    """High-performance event filter evaluated in Rust.

    Filters specified through this class are evaluated in Rust before
    events are passed to Python, providing significant performance benefits
    for high-volume event streams.

    Example:
        >>> filter = (
        ...     RustEventFilter()
        ...     .event_ids([1, 2, 3])
        ...     .level_max(4)
        ...     .pid(1234)
        ... )
        >>> session.add_provider("Microsoft-Windows-DNS-Client", filter=filter)
    """

    def __init__(self) -> None:
        """Initialize an empty filter."""
        self._specs: list[FilterSpec] = []
        self._negated = False
        self._combined_filters: list[tuple[str, RustEventFilter]] = []
        self._rust_handle: int | None = None

    @property
    def is_rust_filter(self) -> bool:
        """Indicate that this filter is evaluated in Rust."""
        return True

    def event_ids(self, ids: list[int]) -> RustEventFilter:
        """Filter to only include events with specified IDs.

        Args:
            ids: List of event IDs to include.

        Returns:
            Self for method chaining.

        Raises:
            ValueError: If any ID is negative.
        """
        for id_ in ids:
            if id_ < 0:
                raise ValueError(f"Event ID must be non-negative, got {id_}")

        new_filter = self._clone()
        new_filter._specs.append(FilterSpec(filter_type="event_ids", value=list(ids)))
        return new_filter

    def exclude_event_ids(self, ids: list[int]) -> RustEventFilter:
        """Exclude events with specified IDs.

        Args:
            ids: List of event IDs to exclude.

        Returns:
            Self for method chaining.
        """
        new_filter = self._clone()
        new_filter._specs.append(FilterSpec(filter_type="exclude_event_ids", value=list(ids)))
        return new_filter

    def level_max(self, level: int) -> RustEventFilter:
        """Filter to only include events at or below specified level.

        Args:
            level: Maximum trace level (0=Always, 1=Critical, 2=Error,
                   3=Warning, 4=Info, 5=Verbose).

        Returns:
            Self for method chaining.
        """
        new_filter = self._clone()
        new_filter._specs.append(FilterSpec(filter_type="level_max", value=level))
        return new_filter

    def keywords_any(self, keywords: int) -> RustEventFilter:
        """Filter to events with any of the specified keywords.

        Args:
            keywords: Bitmask of keywords to match.

        Returns:
            Self for method chaining.
        """
        new_filter = self._clone()
        new_filter._specs.append(FilterSpec(filter_type="keywords_any", value=keywords))
        return new_filter

    def keywords_all(self, keywords: int) -> RustEventFilter:
        """Filter to events with all of the specified keywords.

        Args:
            keywords: Bitmask of keywords that must all be present.

        Returns:
            Self for method chaining.
        """
        new_filter = self._clone()
        new_filter._specs.append(FilterSpec(filter_type="keywords_all", value=keywords))
        return new_filter

    def pid(self, process_id: int) -> RustEventFilter:
        """Filter to events from a specific process.

        Args:
            process_id: Process ID to filter for.

        Returns:
            Self for method chaining.
        """
        new_filter = self._clone()
        new_filter._specs.append(FilterSpec(filter_type="pid", value=process_id))
        return new_filter

    def property_equals(self, field_name: str, value: Any) -> RustEventFilter:
        """Filter by exact property value match.

        Args:
            field_name: Name of the event property.
            value: Value to match against.

        Returns:
            Self for method chaining.
        """
        new_filter = self._clone()
        new_filter._specs.append(
            FilterSpec(
                filter_type="property_equals",
                field_name=field_name,
                value=value,
            )
        )
        return new_filter

    def property_contains(self, field_name: str, substring: str) -> RustEventFilter:
        """Filter by property containing a substring.

        Args:
            field_name: Name of the event property.
            substring: Substring to search for.

        Returns:
            Self for method chaining.
        """
        new_filter = self._clone()
        new_filter._specs.append(
            FilterSpec(
                filter_type="property_contains",
                field_name=field_name,
                value=substring,
            )
        )
        return new_filter

    def property_regex(self, field_name: str, pattern: str) -> RustEventFilter:
        """Filter by property matching a regex pattern.

        Args:
            field_name: Name of the event property.
            pattern: Regular expression pattern.

        Returns:
            Self for method chaining.

        Raises:
            ValueError: If the regex pattern is invalid.
        """
        # Validate regex at construction time
        try:
            re.compile(pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}") from e

        new_filter = self._clone()
        new_filter._specs.append(
            FilterSpec(
                filter_type="property_regex",
                field_name=field_name,
                pattern=pattern,
            )
        )
        return new_filter

    def property_gt(self, field_name: str, value: int | float) -> RustEventFilter:
        """Filter by property greater than a value.

        Args:
            field_name: Name of the event property.
            value: Value to compare against.

        Returns:
            Self for method chaining.
        """
        new_filter = self._clone()
        new_filter._specs.append(
            FilterSpec(
                filter_type="property_gt",
                field_name=field_name,
                value=value,
            )
        )
        return new_filter

    def property_lt(self, field_name: str, value: int | float) -> RustEventFilter:
        """Filter by property less than a value.

        Args:
            field_name: Name of the event property.
            value: Value to compare against.

        Returns:
            Self for method chaining.
        """
        new_filter = self._clone()
        new_filter._specs.append(
            FilterSpec(
                filter_type="property_lt",
                field_name=field_name,
                value=value,
            )
        )
        return new_filter

    def _clone(self) -> RustEventFilter:
        """Create a clone of this filter."""
        new_filter = RustEventFilter()
        new_filter._specs = list(self._specs)
        new_filter._negated = self._negated
        new_filter._combined_filters = list(self._combined_filters)
        return new_filter

    def __and__(self, other: RustEventFilter) -> RustEventFilter:
        """Combine filters with AND logic.

        Args:
            other: Another filter to AND with.

        Returns:
            Combined filter.
        """
        new_filter = RustEventFilter()
        new_filter._combined_filters = [("and", self), ("and", other)]
        return new_filter

    def __or__(self, other: RustEventFilter) -> RustEventFilter:
        """Combine filters with OR logic.

        Args:
            other: Another filter to OR with.

        Returns:
            Combined filter.
        """
        new_filter = RustEventFilter()
        new_filter._combined_filters = [("or", self), ("or", other)]
        return new_filter

    def __invert__(self) -> RustEventFilter:
        """Negate this filter.

        Returns:
            Negated filter.
        """
        new_filter = self._clone()
        new_filter._negated = not new_filter._negated
        return new_filter

    def to_bytes(self) -> bytes:
        """Serialize the filter for Rust.

        Returns:
            Byte representation of the filter.
        """
        return self._serialize()

    def _serialize(self) -> bytes:
        """Serialize the filter specification.

        Format:
            1 byte: version (currently 1)
            1 byte: flags (bit 0 = negated)
            2 bytes: number of specs
            For each spec:
                1 byte: type code
                variable: type-specific data
        """
        data = bytearray()

        # Version
        data.append(1)

        # Flags
        flags = 0
        if self._negated:
            flags |= 1
        data.append(flags)

        # Number of specs
        data.extend(struct.pack("<H", len(self._specs)))

        # Type codes
        type_codes = {
            "event_ids": 1,
            "exclude_event_ids": 2,
            "level_max": 3,
            "keywords_any": 4,
            "keywords_all": 5,
            "pid": 6,
            "property_equals": 10,
            "property_contains": 11,
            "property_regex": 12,
            "property_gt": 13,
            "property_lt": 14,
        }

        for spec in self._specs:
            type_code = type_codes.get(spec.filter_type, 0)
            data.append(type_code)

            if spec.filter_type in ("event_ids", "exclude_event_ids"):
                # List of u16 event IDs
                ids = spec.value or []
                data.extend(struct.pack("<H", len(ids)))
                for id_ in ids:
                    data.extend(struct.pack("<H", id_))

            elif spec.filter_type == "level_max":
                data.append(spec.value or 0)

            elif spec.filter_type in ("keywords_any", "keywords_all"):
                data.extend(struct.pack("<Q", spec.value or 0))

            elif spec.filter_type == "pid":
                data.extend(struct.pack("<I", spec.value or 0))

            elif spec.filter_type in (
                "property_equals",
                "property_contains",
                "property_gt",
                "property_lt",
            ):
                # Field name (length-prefixed)
                field_bytes = (spec.field_name or "").encode("utf-8")
                data.extend(struct.pack("<H", len(field_bytes)))
                data.extend(field_bytes)

                # Value (type-dependent)
                value = spec.value
                if isinstance(value, int):
                    data.append(1)  # int type
                    data.extend(struct.pack("<q", value))
                elif isinstance(value, float):
                    data.append(2)  # float type
                    data.extend(struct.pack("<d", value))
                elif isinstance(value, str):
                    data.append(3)  # string type
                    value_bytes = value.encode("utf-8")
                    data.extend(struct.pack("<H", len(value_bytes)))
                    data.extend(value_bytes)
                else:
                    data.append(0)  # null/unknown

            elif spec.filter_type == "property_regex":
                # Field name
                field_bytes = (spec.field_name or "").encode("utf-8")
                data.extend(struct.pack("<H", len(field_bytes)))
                data.extend(field_bytes)

                # Pattern
                pattern_bytes = (spec.pattern or "").encode("utf-8")
                data.extend(struct.pack("<H", len(pattern_bytes)))
                data.extend(pattern_bytes)

        return bytes(data)

    def matches(self, event: Any) -> bool:
        """Check if an event matches this filter (Python fallback).

        This method is provided for testing and fallback when Rust
        evaluation is not available.

        Args:
            event: The event to check.

        Returns:
            True if the event matches the filter.
        """
        result = self._matches_specs(event)

        if self._negated:
            result = not result

        return result

    def _matches_specs(self, event: Any) -> bool:
        """Check if event matches all filter specs."""
        return all(self._matches_spec(event, spec) for spec in self._specs)

    def _matches_spec(self, event: Any, spec: FilterSpec) -> bool:
        """Check if event matches a single filter spec."""
        if spec.filter_type == "event_ids":
            return event.event_id in (spec.value or [])

        elif spec.filter_type == "exclude_event_ids":
            return event.event_id not in (spec.value or [])

        elif spec.filter_type == "level_max":
            level = getattr(event, "level", 0)
            return level <= (spec.value or 5)

        elif spec.filter_type == "keywords_any":
            keywords = getattr(event, "keywords", 0)
            return bool(keywords & (spec.value or 0))

        elif spec.filter_type == "keywords_all":
            keywords = getattr(event, "keywords", 0)
            mask = spec.value or 0
            return (keywords & mask) == mask

        elif spec.filter_type == "pid":
            pid = getattr(event, "process_id", 0)
            return pid == spec.value

        elif spec.filter_type == "property_equals":
            props = getattr(event, "properties", {})
            return props.get(spec.field_name) == spec.value

        elif spec.filter_type == "property_contains":
            props = getattr(event, "properties", {})
            value = props.get(spec.field_name, "")
            return spec.value in str(value) if value else False

        elif spec.filter_type == "property_regex":
            props = getattr(event, "properties", {})
            value = props.get(spec.field_name, "")
            return bool(re.search(spec.pattern or "", str(value))) if value else False

        elif spec.filter_type == "property_gt":
            props = getattr(event, "properties", {})
            value = props.get(spec.field_name)
            return value > spec.value if value is not None else False

        elif spec.filter_type == "property_lt":
            props = getattr(event, "properties", {})
            value = props.get(spec.field_name)
            return value < spec.value if value is not None else False

        return True
