"""Manifest-based typed events (v2.0.0 - #55).

This module provides support for parsing ETW provider manifests and generating
typed Python classes for event fields.
"""

from __future__ import annotations

import dataclasses
import re
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from pathlib import Path

T = TypeVar("T")


@dataclass
class FieldDefinition:
    """Definition of a field within an ETW event.

    Attributes:
        name: Name of the field.
        field_type: Type of the field (e.g., 'uint32', 'string', 'binary').
        description: Optional description of the field.
        out_type: Optional output type for formatting.
    """

    name: str
    field_type: str
    description: str = ""
    out_type: str | None = None

    @property
    def python_type(self) -> type:
        """Get the Python type corresponding to this field type."""
        type_map = {
            "uint8": int,
            "uint16": int,
            "uint32": int,
            "uint64": int,
            "int8": int,
            "int16": int,
            "int32": int,
            "int64": int,
            "float": float,
            "double": float,
            "boolean": bool,
            "string": str,
            "unicode_string": str,
            "ansi_string": str,
            "binary": bytes,
            "pointer": int,
            "guid": str,
            "sid": str,
            "hexint32": int,
            "hexint64": int,
        }
        return type_map.get(self.field_type.lower(), object)


@dataclass
class EventDefinition:
    """Definition of an ETW event from a manifest.

    Attributes:
        event_id: The event ID number.
        name: Name of the event.
        version: Event version number.
        fields: List of field definitions.
        description: Optional event description.
        task: Optional task name.
        opcode: Optional opcode value.
        level: Optional level value.
        keywords: Optional keywords bitmask.
    """

    event_id: int
    name: str
    version: int
    fields: list[FieldDefinition] = field(default_factory=list)
    description: str = ""
    task: str = ""
    opcode: int = 0
    level: int = 0
    keywords: int = 0

    def get_field(self, name: str) -> FieldDefinition | None:
        """Get a field definition by name."""
        for f in self.fields:
            if f.name == name:
                return f
        return None


@dataclass
class ProviderManifest:
    """Manifest describing an ETW provider and its events.

    Attributes:
        provider_guid: GUID of the provider.
        provider_name: Name of the provider.
        events: Dictionary of event definitions keyed by event ID.
        description: Optional provider description.
    """

    provider_guid: str
    provider_name: str
    events: dict[int, EventDefinition] = field(default_factory=dict)
    description: str = ""

    def get_event(self, event_id: int, version: int = 0) -> EventDefinition | None:  # noqa: ARG002
        """Get an event definition by ID.

        Args:
            event_id: The event ID to look up.
            version: Optional version number (default 0, reserved for future use).

        Returns:
            The EventDefinition if found, None otherwise.
        """
        return self.events.get(event_id)

    def add_event(self, event: EventDefinition) -> None:
        """Add an event definition to the manifest."""
        self.events[event.event_id] = event


class ManifestParser:
    """Parser for ETW provider manifests.

    Supports parsing from:
    - Windows Registry (provider registration)
    - Manifest XML files (.man)
    - MOF files (legacy WMI)
    """

    def __init__(self) -> None:
        """Initialize the manifest parser."""
        self._cache: dict[str, ProviderManifest] = {}

    def parse_from_registry(self, provider_guid: str) -> ProviderManifest | None:
        """Parse manifest from Windows Registry.

        Args:
            provider_guid: GUID of the provider to look up.

        Returns:
            ProviderManifest if found and parsed, None otherwise.
        """
        # Normalize GUID format
        guid = provider_guid.strip("{}").lower()

        # Check cache first
        if guid in self._cache:
            return self._cache[guid]

        try:
            import winreg

            # Look up provider in registry
            reg_path = (
                f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WINEVT\\Publishers\\{{{guid}}}"
            )
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path, 0, winreg.KEY_READ) as key:
                try:
                    name, _ = winreg.QueryValueEx(key, "")
                    manifest = ProviderManifest(
                        provider_guid=guid,
                        provider_name=name if name else f"Provider-{guid}",
                    )
                    self._cache[guid] = manifest
                    return manifest
                except FileNotFoundError:
                    # Provider exists but no name
                    manifest = ProviderManifest(
                        provider_guid=guid,
                        provider_name=f"Provider-{guid}",
                    )
                    self._cache[guid] = manifest
                    return manifest
        except (FileNotFoundError, OSError):
            return None

    def parse_from_file(self, path: Path | str) -> ProviderManifest | None:
        """Parse manifest from a file.

        Args:
            path: Path to the manifest file (.man or .mof).

        Returns:
            ProviderManifest if parsed successfully, None otherwise.
        """
        from pathlib import Path

        path = Path(path)

        if not path.exists():
            return None

        if path.suffix.lower() == ".man":
            return self._parse_manifest_xml(path)
        elif path.suffix.lower() == ".mof":
            return self._parse_mof(path)
        else:
            return None

    def _parse_manifest_xml(self, path: Path) -> ProviderManifest | None:
        """Parse an ETW manifest XML file."""
        import xml.etree.ElementTree as ET

        try:
            tree = ET.parse(path)
            root = tree.getroot()

            # Find provider element
            ns = {"": "http://schemas.microsoft.com/win/2004/08/events"}
            provider_elem = root.find(".//provider", ns) or root.find(".//Provider", ns)

            if provider_elem is None:
                # Try without namespace
                provider_elem = root.find(".//provider")
                if provider_elem is None:
                    return None

            guid = provider_elem.get("guid", "").strip("{}")
            name = provider_elem.get("name", f"Provider-{guid}")

            manifest = ProviderManifest(
                provider_guid=guid,
                provider_name=name,
            )

            # Parse events
            for event_elem in root.iter():
                if event_elem.tag.endswith("event") or event_elem.tag == "event":
                    event_id = int(event_elem.get("value", event_elem.get("id", "0")))
                    event_name = event_elem.get("symbol", f"Event{event_id}")
                    version = int(event_elem.get("version", "0"))

                    event_def = EventDefinition(
                        event_id=event_id,
                        name=event_name,
                        version=version,
                    )
                    manifest.add_event(event_def)

            return manifest

        except ET.ParseError:
            return None

    def _parse_mof(self, path: Path) -> ProviderManifest | None:
        """Parse a legacy MOF file."""
        # Basic MOF parsing - extract class definitions
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")

            # Extract GUID from class definition
            guid_match = re.search(r'Guid\s*\(\s*"([^"]+)"\s*\)', content, re.IGNORECASE)
            guid = guid_match.group(1) if guid_match else "00000000-0000-0000-0000-000000000000"

            # Extract class name
            class_match = re.search(r"class\s+(\w+)", content, re.IGNORECASE)
            name = class_match.group(1) if class_match else f"Provider-{guid}"

            return ProviderManifest(
                provider_guid=guid,
                provider_name=name,
            )
        except (OSError, UnicodeDecodeError):
            return None


class TypedEventFactory:
    """Factory for creating typed event classes from manifest definitions.

    Creates Python dataclasses with proper type annotations based on
    event field definitions.
    """

    def __init__(self) -> None:
        """Initialize the typed event factory."""
        self._classes: dict[tuple[str, int, int], type] = {}

    def create_event_class(self, event_def: EventDefinition) -> type:
        """Create a typed event class from an event definition.

        Args:
            event_def: The event definition to create a class for.

        Returns:
            A dataclass type with fields matching the event definition.
        """
        cache_key = ("", event_def.event_id, event_def.version)
        if cache_key in self._classes:
            return self._classes[cache_key]

        # Create fields for the dataclass
        field_annotations: dict[str, type] = {}
        field_defaults: dict[str, Any] = {}

        for field_def in event_def.fields:
            field_annotations[field_def.name] = field_def.python_type
            # Default to None for all fields (they may not be present in all events)
            field_defaults[field_def.name] = None

        # Add standard event fields
        field_annotations["event_id"] = int
        field_annotations["timestamp"] = int
        field_annotations["process_id"] = int
        field_annotations["thread_id"] = int
        field_defaults["event_id"] = event_def.event_id
        field_defaults["timestamp"] = 0
        field_defaults["process_id"] = 0
        field_defaults["thread_id"] = 0

        # Create the class name
        class_name = f"{event_def.name}Event"

        # Create a new class dynamically
        cls = dataclasses.make_dataclass(
            class_name,
            [
                (name, annotation, dataclasses.field(default=field_defaults.get(name)))
                for name, annotation in field_annotations.items()
            ],
        )

        self._classes[cache_key] = cls
        return cls

    def wrap_event(self, event: Any, event_def: EventDefinition) -> Any:
        """Wrap a raw ETW event with a typed event instance.

        Args:
            event: The raw EtwEvent to wrap.
            event_def: The event definition describing the fields.

        Returns:
            A typed event instance with parsed fields.
        """
        cls = self.create_event_class(event_def)

        # Extract field values from the raw event
        kwargs: dict[str, Any] = {
            "event_id": event.event_id,
            "timestamp": getattr(event, "timestamp", 0),
            "process_id": getattr(event, "process_id", 0),
            "thread_id": getattr(event, "thread_id", 0),
        }

        # Try to extract each defined field from the event properties
        properties = getattr(event, "properties", {})
        for field_def in event_def.fields:
            if field_def.name in properties:
                kwargs[field_def.name] = properties[field_def.name]

        return cls(**kwargs)


class ManifestCache:
    """Global cache for provider manifests.

    Implements singleton pattern for efficient manifest reuse.
    """

    _instance: ManifestCache | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        """Initialize the manifest cache."""
        self._manifests: dict[str, ProviderManifest] = {}
        self._parser = ManifestParser()
        self._factory = TypedEventFactory()

    @classmethod
    def get_instance(cls) -> ManifestCache:
        """Get the singleton instance of the manifest cache.

        Returns:
            The global ManifestCache instance.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get_manifest(self, provider_guid: str) -> ProviderManifest | None:
        """Get a provider manifest by GUID.

        Args:
            provider_guid: The provider GUID to look up.

        Returns:
            The ProviderManifest if found, None otherwise.
        """
        guid = provider_guid.strip("{}").lower()

        if guid in self._manifests:
            return self._manifests[guid]

        # Try to load from registry
        manifest = self._parser.parse_from_registry(guid)
        if manifest:
            self._manifests[guid] = manifest
            return manifest

        return None

    def register_manifest(self, manifest: ProviderManifest) -> None:
        """Register a manifest in the cache.

        Args:
            manifest: The manifest to register.
        """
        guid = manifest.provider_guid.strip("{}").lower()
        self._manifests[guid] = manifest

    @property
    def parser(self) -> ManifestParser:
        """Get the manifest parser."""
        return self._parser

    @property
    def factory(self) -> TypedEventFactory:
        """Get the typed event factory."""
        return self._factory
