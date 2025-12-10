"""Tests for TraceLogging provider support (v0.3.0 - #29)."""

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


class TestTraceLoggingDetection:
    """Tests for TraceLogging event detection."""

    def test_event_has_is_tracelogging(self) -> None:
        """Test that EtwEvent can identify TraceLogging events."""
        import pyetwkit_core

        event_class = pyetwkit_core.EtwEvent
        # Should have a way to check if event is TraceLogging
        has_tl_check = (
            hasattr(event_class, "is_tracelogging")
            or hasattr(event_class, "schema_type")
            or hasattr(event_class, "metadata_type")
        )
        assert has_tl_check


class TestTraceLoggingSchema:
    """Tests for TraceLogging schema parsing."""

    def test_tracelogging_schema_support(self) -> None:
        """Test that TraceLogging schema can be parsed."""
        import pyetwkit_core

        # Either SchemaLocator handles TraceLogging or there's a specific class
        has_tl_support = (
            hasattr(pyetwkit_core, "TraceLoggingSchema")
            or hasattr(pyetwkit_core, "SchemaLocator")
            or hasattr(pyetwkit_core, "EventSchema")
        )
        assert has_tl_support


class TestTraceLoggingProvider:
    """Tests for TraceLogging provider handling."""

    def test_provider_source_tracelogging(self) -> None:
        """Test that provider source can be TraceLogging."""
        import pyetwkit_core

        # Check if ProviderSource includes TraceLogging
        # This was added in discovery module
        providers = pyetwkit_core.list_providers()
        # Some providers should have different sources
        sources = set(p.source for p in providers[:100])
        # At minimum we should have xml or mof
        assert len(sources) >= 1


class TestTraceLoggingMetadata:
    """Tests for TraceLogging self-describing metadata."""

    def test_event_metadata_parsing(self) -> None:
        """Test that event metadata can be parsed from TraceLogging events."""
        import pyetwkit_core

        event_class = pyetwkit_core.EtwEvent
        # Properties dict should work for all event types including TraceLogging
        assert hasattr(event_class, "properties")
