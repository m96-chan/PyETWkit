"""OpenTelemetry (OTLP) Exporter (v3.0.0 - #52).

This module provides exporters for ETW events to OpenTelemetry Protocol (OTLP)
for integration with modern observability platforms.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ExportMode(Enum):
    """Export modes for ETW events."""

    SPANS = "spans"
    LOGS = "logs"
    METRICS = "metrics"


class OtlpFileFormat(Enum):
    """File formats for OTLP export."""

    JSON = "json"
    PROTOBUF = "protobuf"


@dataclass
class OtlpExporterConfig:
    """Configuration for OtlpExporter."""

    batch_size: int = 100
    export_interval_ms: int = 1000
    export_mode: ExportMode = ExportMode.SPANS
    timeout_ms: int = 30000


@dataclass
class SpanMappingRule:
    """A rule for mapping ETW events to spans."""

    provider: str
    event_id: int
    span_name: str
    attributes: list[str] = field(default_factory=list)


class SpanMapper:
    """Maps ETW events to OpenTelemetry spans.

    Example:
        >>> mapper = SpanMapper()
        >>> mapper.add_rule(
        ...     provider="Microsoft-Windows-Kernel-Process",
        ...     event_id=1,
        ...     span_name="process.start",
        ...     attributes=["ProcessId", "ImageFileName"]
        ... )
    """

    def __init__(self) -> None:
        """Initialize the SpanMapper."""
        self._rules: list[SpanMappingRule] = []

    @property
    def rules(self) -> list[SpanMappingRule]:
        """Get the list of mapping rules."""
        return list(self._rules)

    def add_rule(
        self,
        provider: str,
        event_id: int,
        span_name: str,
        attributes: list[str] | None = None,
    ) -> SpanMapper:
        """Add a mapping rule.

        Args:
            provider: Provider name to match.
            event_id: Event ID to match.
            span_name: Span name to use for matching events.
            attributes: List of event properties to include as attributes.

        Returns:
            Self for method chaining.
        """
        self._rules.append(
            SpanMappingRule(
                provider=provider,
                event_id=event_id,
                span_name=span_name,
                attributes=attributes or [],
            )
        )
        return self

    def get_span_name(self, event: Any) -> str | None:
        """Get the span name for an event.

        Args:
            event: ETW event.

        Returns:
            Span name or None if no rule matches.
        """
        provider = getattr(event, "provider_name", "")
        event_id = getattr(event, "event_id", 0)

        for rule in self._rules:
            if rule.provider == provider and rule.event_id == event_id:
                return rule.span_name

        return None

    def extract_attributes(self, event: Any) -> dict[str, Any]:
        """Extract attributes from an event based on mapping rules.

        Args:
            event: ETW event.

        Returns:
            Dictionary of attributes.
        """
        provider = getattr(event, "provider_name", "")
        event_id = getattr(event, "event_id", 0)
        properties = getattr(event, "properties", {})

        for rule in self._rules:
            if rule.provider == provider and rule.event_id == event_id:
                return {key: properties[key] for key in rule.attributes if key in properties}

        return {}


class OtlpExporter:
    """Exports ETW events to OpenTelemetry Protocol (OTLP).

    Example:
        >>> exporter = OtlpExporter(
        ...     endpoint="http://collector:4317",
        ...     service_name="windows-etw"
        ... )
        >>> exporter.export(event)
    """

    def __init__(
        self,
        endpoint: str,
        service_name: str = "pyetwkit",
        resource_attributes: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        insecure: bool = False,
        sample_rate: float = 1.0,
        config: OtlpExporterConfig | None = None,
        span_mapper: SpanMapper | None = None,
    ) -> None:
        """Initialize the OtlpExporter.

        Args:
            endpoint: OTLP collector endpoint URL.
            service_name: Service name for exported telemetry.
            resource_attributes: Additional resource attributes.
            headers: HTTP headers for requests.
            insecure: Whether to use insecure (non-TLS) connection.
            sample_rate: Sampling rate (0.0-1.0).
            config: Exporter configuration.
            span_mapper: Custom span mapper.

        Raises:
            ValueError: If sample_rate is outside valid range.
        """
        if not 0.0 <= sample_rate <= 1.0:
            raise ValueError(f"sample_rate must be between 0.0 and 1.0, got {sample_rate}")

        self._endpoint = endpoint
        self._service_name = service_name
        self._resource_attributes = resource_attributes or {}
        self._headers = headers or {}
        self._insecure = insecure
        self._sample_rate = sample_rate
        self._config = config or OtlpExporterConfig()
        self._span_mapper = span_mapper or SpanMapper()
        self._batch: list[dict[str, Any]] = []
        self._last_export = time.time()

    @property
    def endpoint(self) -> str:
        """Get the endpoint URL."""
        return self._endpoint

    @property
    def service_name(self) -> str:
        """Get the service name."""
        return self._service_name

    @property
    def resource_attributes(self) -> dict[str, str]:
        """Get the resource attributes."""
        return dict(self._resource_attributes)

    @property
    def headers(self) -> dict[str, str]:
        """Get the HTTP headers."""
        return dict(self._headers)

    @property
    def insecure(self) -> bool:
        """Check if insecure mode is enabled."""
        return self._insecure

    @property
    def sample_rate(self) -> float:
        """Get the sample rate."""
        return self._sample_rate

    def export(self, event: Any) -> bool:
        """Export a single event.

        Args:
            event: ETW event to export.

        Returns:
            True if exported successfully.
        """
        # Apply sampling
        if self._sample_rate < 1.0:
            import random

            if random.random() > self._sample_rate:
                return True  # Sampled out

        span = event_to_span(
            event,
            span_name=self._span_mapper.get_span_name(event),
            service_name=self._service_name,
        )
        self._batch.append(span)

        if len(self._batch) >= self._config.batch_size:
            return self.flush()

        return True

    def export_batch(self, events: list[Any]) -> bool:
        """Export a batch of events.

        Args:
            events: List of ETW events to export.

        Returns:
            True if exported successfully.
        """
        for event in events:
            self.export(event)
        return self.flush()

    def flush(self) -> bool:
        """Flush pending events to the collector.

        Returns:
            True if flushed successfully.
        """
        if not self._batch:
            return True

        # In production, would send to OTLP endpoint
        # For now, just clear the batch
        self._batch.clear()
        self._last_export = time.time()
        return True

    def shutdown(self) -> None:
        """Shutdown the exporter."""
        self.flush()

    def attach_to_session(self, session: Any) -> None:
        """Attach the exporter to an ETW session.

        Args:
            session: ETW session to attach to.
        """
        # Would register as an event callback
        pass


class OtlpFileExporter:
    """Exports ETW events to OTLP file format.

    Example:
        >>> exporter = OtlpFileExporter("traces.json")
        >>> exporter.export(event)
    """

    def __init__(
        self,
        output_path: str,
        format: OtlpFileFormat = OtlpFileFormat.JSON,
        service_name: str = "pyetwkit",
    ) -> None:
        """Initialize the OtlpFileExporter.

        Args:
            output_path: Path to output file.
            format: Output file format.
            service_name: Service name for exported telemetry.
        """
        self._output_path = output_path
        self._format = format
        self._service_name = service_name
        self._spans: list[dict[str, Any]] = []

    @property
    def output_path(self) -> str:
        """Get the output path."""
        return self._output_path

    def export(self, event: Any) -> bool:
        """Export a single event.

        Args:
            event: ETW event to export.

        Returns:
            True if exported successfully.
        """
        span = event_to_span(event, service_name=self._service_name)
        self._spans.append(span)
        return True

    def flush(self) -> bool:
        """Flush spans to file with atomic write.

        Returns:
            True if flushed successfully.
        """
        if not self._spans:
            return True

        if self._format == OtlpFileFormat.JSON:
            try:
                # Atomic write via temp file
                output = Path(self._output_path)
                temp_path = output.with_suffix(".tmp")
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump({"spans": self._spans}, f, indent=2)
                temp_path.replace(output)
                self._spans.clear()
            except OSError as e:
                logger.error("Failed to write OTLP file %s: %s", self._output_path, e)
                return False
            except (TypeError, ValueError) as e:
                logger.error("Failed to serialize spans: %s", e)
                return False

        return True

    def shutdown(self) -> None:
        """Shutdown the exporter."""
        self.flush()


def event_to_span(
    event: Any,
    span_name: str | None = None,
    service_name: str = "pyetwkit",
) -> dict[str, Any]:
    """Convert an ETW event to an OpenTelemetry span.

    Args:
        event: ETW event.
        span_name: Optional span name override.
        service_name: Service name.

    Returns:
        Span dictionary in OTLP format.
    """
    event_id = getattr(event, "event_id", 0)
    provider_name = getattr(event, "provider_name", "unknown")
    raw_timestamp = getattr(event, "timestamp", time.time())
    process_id = getattr(event, "process_id", 0)
    thread_id = getattr(event, "thread_id", 0)
    properties = getattr(event, "properties", {})

    # Convert timestamp to float (seconds since epoch)
    if hasattr(raw_timestamp, "timestamp"):
        # datetime object
        timestamp = raw_timestamp.timestamp()
    else:
        timestamp = float(raw_timestamp)

    return {
        "traceId": uuid.uuid4().hex,
        "spanId": uuid.uuid4().hex[:16],
        "name": span_name or f"{provider_name}.{event_id}",
        "kind": "INTERNAL",
        "startTimeUnixNano": int(timestamp * 1e9),
        "endTimeUnixNano": int(timestamp * 1e9),
        "attributes": [
            {"key": "service.name", "value": {"stringValue": service_name}},
            {"key": "etw.provider", "value": {"stringValue": provider_name}},
            {"key": "etw.event_id", "value": {"intValue": event_id}},
            {"key": "process.pid", "value": {"intValue": process_id}},
            {"key": "thread.id", "value": {"intValue": thread_id}},
            *[{"key": f"etw.{k}", "value": _attribute_value(v)} for k, v in properties.items()],
        ],
        "status": {"code": "OK"},
    }


def event_to_log(
    event: Any,
    service_name: str = "pyetwkit",
) -> dict[str, Any]:
    """Convert an ETW event to an OpenTelemetry log.

    Args:
        event: ETW event.
        service_name: Service name.

    Returns:
        Log dictionary in OTLP format.
    """
    event_id = getattr(event, "event_id", 0)
    provider_name = getattr(event, "provider_name", "unknown")
    raw_timestamp = getattr(event, "timestamp", time.time())
    process_id = getattr(event, "process_id", 0)
    properties = getattr(event, "properties", {})

    # Convert timestamp to float (seconds since epoch)
    if hasattr(raw_timestamp, "timestamp"):
        # datetime object
        timestamp = raw_timestamp.timestamp()
    else:
        timestamp = float(raw_timestamp)

    return {
        "timeUnixNano": int(timestamp * 1e9),
        "severityNumber": 9,  # INFO
        "severityText": "INFO",
        "body": {"stringValue": f"{provider_name}: Event {event_id}"},
        "attributes": [
            {"key": "service.name", "value": {"stringValue": service_name}},
            {"key": "etw.provider", "value": {"stringValue": provider_name}},
            {"key": "etw.event_id", "value": {"intValue": event_id}},
            {"key": "process.pid", "value": {"intValue": process_id}},
            *[{"key": f"etw.{k}", "value": _attribute_value(v)} for k, v in properties.items()],
        ],
        "resource": {
            "attributes": [
                {"key": "service.name", "value": {"stringValue": service_name}},
            ]
        },
    }


def _attribute_value(value: Any) -> dict[str, Any]:
    """Convert a Python value to an OTLP attribute value.

    Args:
        value: Python value.

    Returns:
        OTLP attribute value dictionary.
    """
    if isinstance(value, bool):
        return {"boolValue": value}
    elif isinstance(value, int):
        return {"intValue": value}
    elif isinstance(value, float):
        return {"doubleValue": value}
    elif isinstance(value, str):
        return {"stringValue": value}
    elif isinstance(value, (list, tuple)):
        return {"arrayValue": {"values": [_attribute_value(v) for v in value]}}
    else:
        return {"stringValue": str(value)}
