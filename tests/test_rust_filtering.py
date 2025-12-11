"""Tests for Real-time event filtering callbacks (v2.0.0 - #56)."""

from __future__ import annotations

import pytest


def check_extension_available() -> bool:
    """Check if native extension is available."""
    try:
        import pyetwkit_core  # noqa: F401

        return True
    except ImportError:
        return False


# Skip all tests if native extension is not available
pytestmark = pytest.mark.skipif(
    not check_extension_available(),
    reason="Native extension not built",
)


class TestRustEventFilter:
    """Tests for Rust-side EventFilter."""

    def test_rust_event_filter_exists(self) -> None:
        """Test that RustEventFilter class exists."""
        from pyetwkit import RustEventFilter

        assert RustEventFilter is not None

    def test_rust_event_filter_can_be_created(self) -> None:
        """Test that RustEventFilter can be instantiated."""
        from pyetwkit import RustEventFilter

        filter = RustEventFilter()
        assert filter is not None

    def test_rust_event_filter_event_ids(self) -> None:
        """Test filtering by event IDs."""
        from pyetwkit import RustEventFilter

        filter = RustEventFilter().event_ids([1, 2, 3])
        assert filter is not None

    def test_rust_event_filter_exclude_event_ids(self) -> None:
        """Test excluding event IDs."""
        from pyetwkit import RustEventFilter

        filter = RustEventFilter().exclude_event_ids([100, 200])
        assert filter is not None

    def test_rust_event_filter_level(self) -> None:
        """Test filtering by level."""
        from pyetwkit import RustEventFilter

        filter = RustEventFilter().level_max(4)  # Info and above
        assert filter is not None

    def test_rust_event_filter_keywords(self) -> None:
        """Test filtering by keywords."""
        from pyetwkit import RustEventFilter

        filter = RustEventFilter().keywords_any(0x10)
        assert filter is not None

    def test_rust_event_filter_pid(self) -> None:
        """Test filtering by process ID."""
        from pyetwkit import RustEventFilter

        filter = RustEventFilter().pid(1234)
        assert filter is not None

    def test_rust_event_filter_chaining(self) -> None:
        """Test that filter methods can be chained."""
        from pyetwkit import RustEventFilter

        filter = RustEventFilter().event_ids([1, 2]).level_max(4).pid(1234)
        assert filter is not None


class TestRustPropertyFiltering:
    """Tests for Rust-side property filtering."""

    def test_property_equals(self) -> None:
        """Test property equals filter."""
        from pyetwkit import RustEventFilter

        filter = RustEventFilter().property_equals("ProcessId", 1234)
        assert filter is not None

    def test_property_contains(self) -> None:
        """Test property contains filter."""
        from pyetwkit import RustEventFilter

        filter = RustEventFilter().property_contains("ImageFileName", "chrome")
        assert filter is not None

    def test_property_regex(self) -> None:
        """Test property regex filter."""
        from pyetwkit import RustEventFilter

        filter = RustEventFilter().property_regex("CommandLine", r"--type=renderer")
        assert filter is not None

    def test_property_greater_than(self) -> None:
        """Test property greater than filter."""
        from pyetwkit import RustEventFilter

        filter = RustEventFilter().property_gt("ProcessId", 100)
        assert filter is not None

    def test_property_less_than(self) -> None:
        """Test property less than filter."""
        from pyetwkit import RustEventFilter

        filter = RustEventFilter().property_lt("ProcessId", 10000)
        assert filter is not None


class TestFilterCombinations:
    """Tests for combining filters."""

    def test_filter_and(self) -> None:
        """Test AND combination of filters."""
        from pyetwkit import RustEventFilter

        filter1 = RustEventFilter().event_ids([1, 2])
        filter2 = RustEventFilter().pid(1234)

        combined = filter1 & filter2
        assert combined is not None

    def test_filter_or(self) -> None:
        """Test OR combination of filters."""
        from pyetwkit import RustEventFilter

        filter1 = RustEventFilter().event_ids([1])
        filter2 = RustEventFilter().event_ids([2])

        combined = filter1 | filter2
        assert combined is not None

    def test_filter_not(self) -> None:
        """Test NOT operation on filter."""
        from pyetwkit import RustEventFilter

        filter = RustEventFilter().event_ids([100, 200])
        inverted = ~filter
        assert inverted is not None


class TestFilterIntegration:
    """Tests for filter integration with sessions."""

    def test_rust_filter_can_be_created_for_session(self) -> None:
        """Test that RustEventFilter can be created for use with sessions."""
        from pyetwkit import RustEventFilter

        filter = RustEventFilter().event_ids([1, 2])

        # Filter should be ready for Rust-side evaluation
        assert filter.is_rust_filter
        assert filter.to_bytes() is not None

    def test_filter_integration_ready(self) -> None:
        """Test that filter is ready for session integration."""
        from pyetwkit import RustEventFilter

        filter = RustEventFilter().event_ids([1, 2]).pid(1234)

        # Filter should have serialized representation
        data = filter.to_bytes()
        assert len(data) > 0
        # Version byte should be 1
        assert data[0] == 1


class TestFilterPerformance:
    """Tests for filter performance characteristics."""

    def test_filter_is_evaluated_in_rust(self) -> None:
        """Test that filter is marked for Rust evaluation."""
        from pyetwkit import RustEventFilter

        filter = RustEventFilter().event_ids([1, 2])
        # Filter should have a flag or method indicating Rust-side evaluation
        assert hasattr(filter, "is_rust_filter") or hasattr(filter, "_rust_handle")

    def test_filter_serialization(self) -> None:
        """Test that filter can be serialized for Rust."""
        from pyetwkit import RustEventFilter

        filter = RustEventFilter().event_ids([1, 2]).pid(1234)
        # Filter should be serializable
        assert hasattr(filter, "to_bytes") or hasattr(filter, "_serialize")


class TestFilterValidation:
    """Tests for filter validation."""

    def test_invalid_event_id(self) -> None:
        """Test that invalid event IDs raise error."""
        from pyetwkit import RustEventFilter

        with pytest.raises((ValueError, TypeError)):
            RustEventFilter().event_ids([-1])  # Negative ID invalid

    def test_invalid_regex(self) -> None:
        """Test that invalid regex raises error."""
        from pyetwkit import RustEventFilter

        with pytest.raises((ValueError, RuntimeError)):
            RustEventFilter().property_regex("Field", "[invalid")  # Unclosed bracket

    def test_empty_filter(self) -> None:
        """Test that empty filter is valid (matches all)."""
        from pyetwkit import RustEventFilter

        filter = RustEventFilter()
        # Empty filter should be valid
        assert filter is not None
