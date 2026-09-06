"""Tests for the OTLP/HTTP transport (#90).

These run a real HTTP server from the standard library and assert on what was
actually received, rather than mocking the send. The exporter shipped for months
returning success without a transport at all (#88), which no amount of mocking
would have caught.
"""

from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace
from typing import Any

import pytest

from pyetwkit import OtlpExporter


# A stand-in for EtwEvent. The exporter reads events by attribute, so a plain
# dict would silently produce a span of defaults -- which is what the old tests
# in this repo were unknowingly asserting against.
def make_event(**overrides: Any) -> SimpleNamespace:
    fields: dict[str, Any] = {
        "provider_name": "Microsoft-Windows-Kernel-Process",
        "event_id": 1,
        "process_id": 4104,
        "thread_id": 512,
        "timestamp": 1788613764.0,
        "properties": {"ImageName": "cmd.exe"},
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


SAMPLE = make_event()


class _Collector(BaseHTTPRequestHandler):
    """Minimal OTLP collector that records what it was sent."""

    received: list[dict[str, Any]] = []
    status = 200

    def do_POST(self) -> None:  # noqa: N802 - name fixed by BaseHTTPRequestHandler
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        type(self).received.append(
            {
                "path": self.path,
                "content_type": self.headers.get("Content-Type"),
                "headers": dict(self.headers),
                "body": json.loads(body) if body else None,
            }
        )
        self.send_response(type(self).status)
        self.end_headers()

    def log_message(self, *args: Any) -> None:
        """Keep the handler's own logging out of the test output."""


@pytest.fixture
def collector():
    _Collector.received = []
    _Collector.status = 200
    server = HTTPServer(("127.0.0.1", 0), _Collector)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}", _Collector
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _spans(request: dict[str, Any]) -> list[dict[str, Any]]:
    return request["body"]["resourceSpans"][0]["scopeSpans"][0]["spans"]


class TestOtlpHttpTransport:
    def test_flush_posts_otlp_json_to_v1_traces(self, collector) -> None:
        endpoint, sink = collector

        exporter = OtlpExporter(endpoint=endpoint, service_name="svc")
        exporter.export(SAMPLE)

        assert exporter.flush() is True
        assert len(sink.received) == 1

        request = sink.received[0]
        assert request["path"] == "/v1/traces"
        assert request["content_type"] == "application/json"
        assert len(_spans(request)) == 1

    def test_resource_carries_service_name_and_attributes(self, collector) -> None:
        endpoint, sink = collector

        exporter = OtlpExporter(
            endpoint=endpoint,
            service_name="windows-etw",
            resource_attributes={"deployment.environment": "production"},
        )
        exporter.export(SAMPLE)
        exporter.flush()

        resource = sink.received[0]["body"]["resourceSpans"][0]["resource"]
        attributes = {a["key"]: a["value"] for a in resource["attributes"]}
        assert attributes["service.name"]["stringValue"] == "windows-etw"
        assert attributes["deployment.environment"]["stringValue"] == "production"

    def test_enums_are_integers_not_names(self, collector) -> None:
        """OTLP JSON forbids enum name strings.

        "only integer enum values are allowed in OTLP JSON Protobuf Encoding;
        the enum name strings MUST NOT be used." -- the exporter used to send
        "INTERNAL" and "OK", which a collector rejects.
        """
        endpoint, sink = collector

        exporter = OtlpExporter(endpoint=endpoint)
        exporter.export(SAMPLE)
        exporter.flush()

        span = _spans(sink.received[0])[0]
        assert span["kind"] == 1
        assert span["status"]["code"] == 1

    def test_trace_and_span_ids_are_hex_of_the_right_length(self, collector) -> None:
        endpoint, sink = collector

        exporter = OtlpExporter(endpoint=endpoint)
        exporter.export(SAMPLE)
        exporter.flush()

        span = _spans(sink.received[0])[0]
        assert len(span["traceId"]) == 32
        assert len(span["spanId"]) == 16
        int(span["traceId"], 16)
        int(span["spanId"], 16)

    def test_custom_headers_are_sent(self, collector) -> None:
        endpoint, sink = collector

        exporter = OtlpExporter(endpoint=endpoint, headers={"X-Api-Key": "secret"})
        exporter.export(SAMPLE)
        exporter.flush()

        assert sink.received[0]["headers"]["X-Api-Key"] == "secret"

    def test_endpoint_with_an_explicit_path_is_left_alone(self, collector) -> None:
        endpoint, sink = collector

        exporter = OtlpExporter(endpoint=f"{endpoint}/custom/v1/traces")
        exporter.export(SAMPLE)
        exporter.flush()

        assert sink.received[0]["path"] == "/custom/v1/traces"

    def test_batch_is_cleared_after_a_successful_send(self, collector) -> None:
        endpoint, _ = collector

        exporter = OtlpExporter(endpoint=endpoint)
        exporter.export(SAMPLE)
        assert exporter.flush() is True

        # Nothing left, so a second flush sends nothing and still succeeds.
        assert exporter.flush() is True

    def test_export_batch_sends_everything(self, collector) -> None:
        endpoint, sink = collector

        exporter = OtlpExporter(endpoint=endpoint)
        assert exporter.export_batch([SAMPLE, SAMPLE, SAMPLE]) is True
        assert len(_spans(sink.received[0])) == 3

    def test_reaching_batch_size_sends_without_an_explicit_flush(self, collector) -> None:
        from pyetwkit.exporters import OtlpExporterConfig

        endpoint, sink = collector

        exporter = OtlpExporter(endpoint=endpoint, config=OtlpExporterConfig(batch_size=2))
        exporter.export(SAMPLE)
        assert sink.received == []

        exporter.export(SAMPLE)
        assert len(sink.received) == 1
        assert len(_spans(sink.received[0])) == 2


class TestRealEventShapes:
    """The shapes an actual `EtwEvent` has, as opposed to a mock's."""

    def test_iso8601_timestamp_with_nanoseconds(self, collector) -> None:
        """`EtwEvent.timestamp` is an RFC 3339 string, not a number.

        `float()` on it raises, so every real event used to blow up here. The
        existing tests all passed mocks or plain floats, which is why nobody
        noticed. Nine fractional digits also defeat `datetime.fromisoformat`.
        """
        endpoint, sink = collector

        event = make_event(timestamp="2026-09-05T13:09:24.061643500+00:00")
        exporter = OtlpExporter(endpoint=endpoint)
        exporter.export(event)

        assert exporter.flush() is True

        span = _spans(sink.received[0])[0]
        # 2026-09-05T13:09:24Z in nanoseconds, to the second.
        assert span["startTimeUnixNano"] // 1_000_000_000 == 1788613764

    def test_datetime_timestamp_still_works(self, collector) -> None:
        from datetime import datetime, timezone

        endpoint, sink = collector

        when = datetime(2026, 9, 5, 13, 9, 24, tzinfo=timezone.utc)
        exporter = OtlpExporter(endpoint=endpoint)
        exporter.export(make_event(timestamp=when))
        exporter.flush()

        span = _spans(sink.received[0])[0]
        assert span["startTimeUnixNano"] // 1_000_000_000 == int(when.timestamp())

    def test_an_unparseable_timestamp_does_not_lose_the_span(self, collector) -> None:
        """A bad timestamp is not worth dropping the event over."""
        endpoint, sink = collector

        exporter = OtlpExporter(endpoint=endpoint)
        exporter.export(make_event(timestamp="not a timestamp"))

        assert exporter.flush() is True
        assert len(_spans(sink.received[0])) == 1

    def test_events_read_from_an_etl_file_export(self, collector) -> None:
        """End to end, with events from the committed capture."""
        from pathlib import Path

        from pyetwkit._core import EtlReader

        fixture = Path(__file__).parent / "fixtures" / "sample.etl"
        if not fixture.exists():
            pytest.skip("Requires sample ETL file")

        endpoint, sink = collector
        events = EtlReader(str(fixture)).read_all()
        assert events, "fixture produced no events"

        exporter = OtlpExporter(endpoint=endpoint, service_name="windows-etw")
        for event in events:
            exporter.export(event)

        assert exporter.flush() is True
        assert len(_spans(sink.received[0])) == len(events)


class TestOtlpHttpFailures:
    """A failure must be visible and must not cost the events."""

    def test_server_error_returns_false_and_keeps_the_batch(self, collector, caplog) -> None:
        endpoint, sink = collector
        sink.status = 503

        exporter = OtlpExporter(endpoint=endpoint)
        exporter.export(SAMPLE)

        with caplog.at_level(logging.ERROR):
            assert exporter.flush() is False

        assert "503" in caplog.text
        # Kept, so the caller can retry rather than losing the events.
        assert exporter.flush() is False
        assert len(sink.received) == 2

    def test_unreachable_collector_returns_false_without_raising(self, caplog) -> None:
        """Port 1 is closed. The exception must not reach the caller."""
        exporter = OtlpExporter(endpoint="http://127.0.0.1:1")
        exporter.export(SAMPLE)

        with caplog.at_level(logging.ERROR):
            assert exporter.flush() is False

        assert caplog.text

    def test_flush_with_nothing_buffered_is_not_a_failure(self) -> None:
        exporter = OtlpExporter(endpoint="http://127.0.0.1:1")
        assert exporter.flush() is True

    def test_shutdown_does_not_raise_when_the_collector_is_gone(self) -> None:
        """Callers reach shutdown from `finally`."""
        exporter = OtlpExporter(endpoint="http://127.0.0.1:1")
        exporter.export(SAMPLE)
        exporter.shutdown()
