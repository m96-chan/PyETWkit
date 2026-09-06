"""OpenTelemetry (OTLP) Exporter (v3.0.0 - #52).

This module provides exporters for ETW events to OpenTelemetry Protocol (OTLP)
for integration with modern observability platforms.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# OTLP/HTTP puts traces here. The default port is 4318; 4317 is the gRPC one.
OTLP_TRACES_PATH = "/v1/traces"

# OTLP's JSON encoding follows the protobuf JSON mapping with one relevant
# deviation: "only integer enum values are allowed in OTLP JSON Protobuf
# Encoding; the enum name strings MUST NOT be used". These used to be sent as
# "INTERNAL" and "OK", which a collector rejects.
# https://opentelemetry.io/docs/specs/otlp/
SPAN_KIND_INTERNAL = 1
STATUS_CODE_OK = 1


# The field names an event is expected to carry. Used both to read values and
# to tell an event from something that is not one at all.
_EVENT_FIELDS = (
    "event_id",
    "provider_name",
    "timestamp",
    "process_id",
    "thread_id",
    "properties",
)


def _event_field(event: Any, name: str, default: Any) -> Any:
    """Read one field, whether the event is a mapping or an object.

    `getattr` alone quietly returned the default for every field of a `dict`, so
    a dict event produced a span named "unknown.0" with no provider and no PID --
    no error, just wrong. `pyetwkit.export` has always accepted both shapes; this
    brings the OTLP side into line with it.
    """
    if isinstance(event, Mapping):
        value = event.get(name, default)
    else:
        value = getattr(event, name, default)
    return default if value is None else value


def _require_event(event: Any) -> None:
    """Reject something that is not an event at all.

    Without this a string or an int would sail through and produce a span of
    defaults, which is the failure this whole change is about.
    """
    if isinstance(event, Mapping):
        return
    if any(hasattr(event, field) for field in _EVENT_FIELDS):
        return
    raise TypeError(
        f"expected an ETW event or a mapping of event fields, got {type(event).__name__}"
    )


def _timestamp_seconds(raw: Any) -> float:
    """Seconds since the epoch, from whatever an event carries.

    `EtwEvent.timestamp` is an RFC 3339 string with nanosecond precision, e.g.
    "2026-09-05T13:09:24.061643500+00:00". `float()` on that raises, which meant
    every real event blew up here -- the existing tests all used mocks or plain
    numbers. `datetime.fromisoformat` cannot take nine fractional digits either
    on the Python versions this supports, so the fraction is trimmed to six.
    """
    if hasattr(raw, "timestamp"):  # datetime
        return float(raw.timestamp())

    if isinstance(raw, str):
        text = re.sub(r"(\.\d{6})\d+", r"\1", raw)
        try:
            return datetime.fromisoformat(text).timestamp()
        except ValueError:
            logger.warning("Unparseable event timestamp %r; using now()", raw)
            return time.time()

    return float(raw)


def _package_version() -> str:
    """The package version, imported lazily.

    `pyetwkit/__init__.py` imports this module, so importing it back at module
    scope would be a cycle that happens to work only because `__version__` is
    defined before that import runs.
    """
    from pyetwkit import __version__

    return __version__


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
        provider = _event_field(event, "provider_name", "")
        event_id = _event_field(event, "event_id", 0)

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
        provider = _event_field(event, "provider_name", "")
        event_id = _event_field(event, "event_id", 0)
        properties = _event_field(event, "properties", {})

        for rule in self._rules:
            if rule.provider == provider and rule.event_id == event_id:
                return {key: properties[key] for key in rule.attributes if key in properties}

        return {}


class OtlpExporter:
    """Exports ETW events to an OTLP collector over HTTP.

    Spans are sent as OTLP/HTTP with JSON encoding, POSTed to ``/v1/traces`` on
    the given endpoint. That encoding needs no dependencies beyond the standard
    library, which is why it is used in preference to gRPC or protobuf.

    The endpoint is used as given; only a missing path is filled in. **OTLP/HTTP
    is normally port 4318** -- 4317 is the gRPC port and will not answer an HTTP
    request.

    :meth:`flush` returns False and logs the reason when a send fails, keeping
    the batch so it can be retried. It never raises: exporters are driven from
    event callbacks, and a collector being down should not stop a trace session.

    See :class:`OtlpFileExporter` to write spans to a file instead.

    Example:
        >>> exporter = OtlpExporter(
        ...     endpoint="http://collector:4318",
        ...     service_name="windows-etw"
        ... )
        >>> exporter.export(event)
        True
        >>> if not exporter.flush():
        ...     log.warning("OTLP export failed; see the log for the reason")
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
        """Buffer one event as a span, sending once the batch is full.

        Args:
            event: ETW event to export.

        Returns:
            True once the span is buffered, or the result of the :meth:`flush`
            this triggers if the event fills the batch.
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

    def _traces_url(self) -> str:
        """The URL to POST to.

        The endpoint is used as given. Only the path is filled in, and only when
        there is none: rewriting what the caller passed -- including "helpfully"
        turning the gRPC port 4317 into the HTTP one -- would break anyone
        serving OTLP/HTTP somewhere else, and quietly.
        """
        parts = urlsplit(self._endpoint)
        if parts.path in ("", "/"):
            return urlunsplit(parts._replace(path=OTLP_TRACES_PATH))
        return self._endpoint

    def flush(self) -> bool:
        """Send pending spans to the collector.

        Returns:
            True if there was nothing to send or the collector accepted it,
            False if the send failed. Failures are logged with the reason.

        The batch is kept when a send fails, so the events can be retried rather
        than lost. Nothing is raised: this is called from event callbacks, and a
        collector being down should not take the trace session with it.
        """
        if not self._batch:
            self._last_export = time.time()
            return True

        url = self._traces_url()
        payload = json.dumps(self._build_request(self._batch)).encode("utf-8")

        request = Request(url, data=payload, method="POST")
        request.add_header("Content-Type", "application/json")
        for name, value in self._headers.items():
            request.add_header(name, value)

        timeout = self._config.timeout_ms / 1000.0
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310 - caller's URL
                status = response.status
        except HTTPError as e:
            logger.error(
                "OTLP export to %s failed: HTTP %s %s. %d span(s) kept for retry.",
                url,
                e.code,
                e.reason,
                len(self._batch),
            )
            return False
        except URLError as e:
            hint = ""
            if urlsplit(self._endpoint).port == 4317:
                hint = " (port 4317 is the OTLP/gRPC port; OTLP/HTTP is usually 4318)"
            logger.error(
                "OTLP export to %s failed: %s%s. %d span(s) kept for retry.",
                url,
                e.reason,
                hint,
                len(self._batch),
            )
            return False
        except OSError as e:
            logger.error(
                "OTLP export to %s failed: %s. %d span(s) kept for retry.",
                url,
                e,
                len(self._batch),
            )
            return False

        if not 200 <= status < 300:
            logger.error(
                "OTLP export to %s failed: HTTP %s. %d span(s) kept for retry.",
                url,
                status,
                len(self._batch),
            )
            return False

        self._batch.clear()
        self._last_export = time.time()
        return True

    def _build_request(self, spans: list[dict[str, Any]]) -> dict[str, Any]:
        """Wrap spans in the OTLP ExportTraceServiceRequest envelope."""
        attributes = [
            {"key": "service.name", "value": {"stringValue": self._service_name}},
            *(
                {"key": key, "value": _attribute_value(value)}
                for key, value in self._resource_attributes.items()
            ),
        ]
        return {
            "resourceSpans": [
                {
                    "resource": {"attributes": attributes},
                    "scopeSpans": [
                        {
                            "scope": {"name": "pyetwkit", "version": _package_version()},
                            "spans": spans,
                        }
                    ],
                }
            ]
        }

    def shutdown(self) -> None:
        """Flush what is left and stop.

        Callers reach this from ``finally``, so a failure is logged by `flush`
        and otherwise ignored rather than raised from a teardown path.
        """
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
    _require_event(event)
    event_id = _event_field(event, "event_id", 0)
    provider_name = _event_field(event, "provider_name", "unknown")
    raw_timestamp = _event_field(event, "timestamp", time.time())
    process_id = _event_field(event, "process_id", 0)
    thread_id = _event_field(event, "thread_id", 0)
    properties = _event_field(event, "properties", {})

    timestamp = _timestamp_seconds(raw_timestamp)

    return {
        "traceId": uuid.uuid4().hex,
        "spanId": uuid.uuid4().hex[:16],
        "name": span_name or f"{provider_name}.{event_id}",
        "kind": SPAN_KIND_INTERNAL,
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
        "status": {"code": STATUS_CODE_OK},
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
    _require_event(event)
    event_id = _event_field(event, "event_id", 0)
    provider_name = _event_field(event, "provider_name", "unknown")
    raw_timestamp = _event_field(event, "timestamp", time.time())
    process_id = _event_field(event, "process_id", 0)
    properties = _event_field(event, "properties", {})

    timestamp = _timestamp_seconds(raw_timestamp)

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
