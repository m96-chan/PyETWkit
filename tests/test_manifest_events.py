"""Tests for Manifest-based typed events (v2.0.0 - #55)."""

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


class TestManifestParser:
    """Tests for manifest parsing functionality."""

    def test_manifest_parser_exists(self) -> None:
        """Test that ManifestParser class exists."""
        from pyetwkit.manifest import ManifestParser

        assert ManifestParser is not None

    def test_manifest_parser_can_be_created(self) -> None:
        """Test that ManifestParser can be instantiated."""
        from pyetwkit.manifest import ManifestParser

        parser = ManifestParser()
        assert parser is not None

    def test_parse_from_registry(self) -> None:
        """Test parsing manifest from registry."""
        from pyetwkit.manifest import ManifestParser

        parser = ManifestParser()
        assert hasattr(parser, "parse_from_registry")
        assert callable(parser.parse_from_registry)

    def test_parse_from_file(self) -> None:
        """Test parsing manifest from file."""
        from pyetwkit.manifest import ManifestParser

        parser = ManifestParser()
        assert hasattr(parser, "parse_from_file")
        assert callable(parser.parse_from_file)


class TestProviderManifest:
    """Tests for ProviderManifest class."""

    def test_provider_manifest_exists(self) -> None:
        """Test that ProviderManifest class exists."""
        from pyetwkit.manifest import ProviderManifest

        assert ProviderManifest is not None

    def test_provider_manifest_has_provider_name(self) -> None:
        """Test that ProviderManifest has provider_name property."""
        from pyetwkit.manifest import ProviderManifest

        # Create a mock manifest
        manifest = ProviderManifest(
            provider_guid="22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716",
            provider_name="Microsoft-Windows-Kernel-Process",
        )
        assert manifest.provider_name == "Microsoft-Windows-Kernel-Process"

    def test_provider_manifest_has_events(self) -> None:
        """Test that ProviderManifest has events property."""
        from pyetwkit.manifest import ProviderManifest

        manifest = ProviderManifest(
            provider_guid="22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716",
            provider_name="Microsoft-Windows-Kernel-Process",
        )
        assert hasattr(manifest, "events")

    def test_provider_manifest_get_event_definition(self) -> None:
        """Test getting event definition by ID."""
        from pyetwkit.manifest import ProviderManifest

        manifest = ProviderManifest(
            provider_guid="22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716",
            provider_name="Microsoft-Windows-Kernel-Process",
        )
        assert hasattr(manifest, "get_event")
        assert callable(manifest.get_event)


class TestEventDefinition:
    """Tests for EventDefinition class."""

    def test_event_definition_exists(self) -> None:
        """Test that EventDefinition class exists."""
        from pyetwkit.manifest import EventDefinition

        assert EventDefinition is not None

    def test_event_definition_has_event_id(self) -> None:
        """Test that EventDefinition has event_id."""
        from pyetwkit.manifest import EventDefinition

        event_def = EventDefinition(
            event_id=1,
            name="ProcessStart",
            version=0,
        )
        assert event_def.event_id == 1

    def test_event_definition_has_name(self) -> None:
        """Test that EventDefinition has name."""
        from pyetwkit.manifest import EventDefinition

        event_def = EventDefinition(
            event_id=1,
            name="ProcessStart",
            version=0,
        )
        assert event_def.name == "ProcessStart"

    def test_event_definition_has_fields(self) -> None:
        """Test that EventDefinition has fields."""
        from pyetwkit.manifest import EventDefinition

        event_def = EventDefinition(
            event_id=1,
            name="ProcessStart",
            version=0,
        )
        assert hasattr(event_def, "fields")


class TestFieldDefinition:
    """Tests for FieldDefinition class."""

    def test_field_definition_exists(self) -> None:
        """Test that FieldDefinition class exists."""
        from pyetwkit.manifest import FieldDefinition

        assert FieldDefinition is not None

    def test_field_definition_has_name(self) -> None:
        """Test that FieldDefinition has name."""
        from pyetwkit.manifest import FieldDefinition

        field = FieldDefinition(
            name="ProcessId",
            field_type="uint32",
        )
        assert field.name == "ProcessId"

    def test_field_definition_has_type(self) -> None:
        """Test that FieldDefinition has field_type."""
        from pyetwkit.manifest import FieldDefinition

        field = FieldDefinition(
            name="ProcessId",
            field_type="uint32",
        )
        assert field.field_type == "uint32"


class TestTypedEventFactory:
    """Tests for typed event creation from manifests."""

    def test_typed_event_factory_exists(self) -> None:
        """Test that TypedEventFactory exists."""
        from pyetwkit.manifest import TypedEventFactory

        assert TypedEventFactory is not None

    def test_create_typed_event_class(self) -> None:
        """Test creating a typed event class from definition."""
        from pyetwkit.manifest import EventDefinition, FieldDefinition, TypedEventFactory

        event_def = EventDefinition(
            event_id=1,
            name="ProcessStart",
            version=0,
            fields=[
                FieldDefinition(name="ProcessId", field_type="uint32"),
                FieldDefinition(name="ImageFileName", field_type="string"),
            ],
        )

        factory = TypedEventFactory()
        ProcessStartEvent = factory.create_event_class(event_def)

        assert ProcessStartEvent is not None
        assert ProcessStartEvent.__name__ == "ProcessStartEvent"

    def test_typed_event_has_fields(self) -> None:
        """Test that created typed event has field accessors."""
        from pyetwkit.manifest import EventDefinition, FieldDefinition, TypedEventFactory

        event_def = EventDefinition(
            event_id=1,
            name="ProcessStart",
            version=0,
            fields=[
                FieldDefinition(name="ProcessId", field_type="uint32"),
                FieldDefinition(name="ImageFileName", field_type="string"),
            ],
        )

        factory = TypedEventFactory()
        ProcessStartEvent = factory.create_event_class(event_def)

        # The class should have these fields defined
        import dataclasses

        assert dataclasses.is_dataclass(ProcessStartEvent)


class TestManifestCache:
    """Tests for manifest caching."""

    def test_manifest_cache_exists(self) -> None:
        """Test that ManifestCache exists."""
        from pyetwkit.manifest import ManifestCache

        assert ManifestCache is not None

    def test_manifest_cache_singleton(self) -> None:
        """Test that ManifestCache can be accessed as singleton."""
        from pyetwkit.manifest import ManifestCache

        cache1 = ManifestCache.get_instance()
        cache2 = ManifestCache.get_instance()
        assert cache1 is cache2

    def test_manifest_cache_get_manifest(self) -> None:
        """Test getting manifest from cache."""
        from pyetwkit.manifest import ManifestCache

        cache = ManifestCache.get_instance()
        assert hasattr(cache, "get_manifest")
        assert callable(cache.get_manifest)
