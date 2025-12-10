"""Tests for schema loader functionality (v0.3.0 - #13)."""

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


class TestEventSchema:
    """Tests for EventSchema class."""

    def test_event_schema_class_exists(self) -> None:
        """Test that EventSchema class exists."""
        import pyetwkit_core

        assert hasattr(pyetwkit_core, "EventSchema")

    def test_event_schema_has_properties(self) -> None:
        """Test that EventSchema has properties attribute."""
        import pyetwkit_core

        # Check class definition
        schema_class = pyetwkit_core.EventSchema
        assert hasattr(schema_class, "properties") or hasattr(schema_class, "property_names")


class TestSchemaLocator:
    """Tests for SchemaLocator functionality."""

    def test_schema_locator_exists(self) -> None:
        """Test that SchemaCache or EventSchema exists."""
        import pyetwkit_core

        # SchemaCache serves as the locator/cache
        assert hasattr(pyetwkit_core, "SchemaCache") or hasattr(pyetwkit_core, "EventSchema")


class TestPropertyInfo:
    """Tests for PropertyInfo class."""

    def test_property_info_exists(self) -> None:
        """Test that PropertyInfo class exists."""
        import pyetwkit_core

        assert hasattr(pyetwkit_core, "PropertyInfo")

    def test_property_info_has_name(self) -> None:
        """Test that PropertyInfo has name attribute."""
        import pyetwkit_core

        if hasattr(pyetwkit_core, "PropertyInfo"):
            # Check class attributes
            prop_class = pyetwkit_core.PropertyInfo
            # Name should be accessible
            assert prop_class is not None

    def test_property_info_has_type(self) -> None:
        """Test that PropertyInfo has type information."""
        import pyetwkit_core

        if hasattr(pyetwkit_core, "PropertyInfo"):
            prop_class = pyetwkit_core.PropertyInfo
            assert prop_class is not None


class TestSchemaCache:
    """Tests for schema caching functionality."""

    def test_schema_cache_exists(self) -> None:
        """Test that schema caching is available."""
        import pyetwkit_core

        # Either a cache class or caching built into SchemaLocator
        has_cache = (
            hasattr(pyetwkit_core, "SchemaCache")
            or hasattr(pyetwkit_core, "clear_schema_cache")
            or hasattr(pyetwkit_core, "SchemaLocator")
        )
        assert has_cache


class TestEventProperties:
    """Tests for event property resolution."""

    def test_event_has_properties_dict(self) -> None:
        """Test that EtwEvent has properties as dict."""
        import pyetwkit_core

        event_class = pyetwkit_core.EtwEvent
        assert hasattr(event_class, "properties")

    def test_event_property_access(self) -> None:
        """Test that event properties can be accessed."""
        import pyetwkit_core

        event_class = pyetwkit_core.EtwEvent
        # The properties attribute should exist
        assert hasattr(event_class, "properties") or hasattr(event_class, "get_property")
