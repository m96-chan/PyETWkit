"""Tests for OpenTelemetry (OTLP) Exporter (v3.0.0 - #52)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestOtlpExporter:
    """Tests for OtlpExporter class."""

    def test_otlp_exporter_exists(self) -> None:
        """Test that OtlpExporter class exists."""
        from pyetwkit.exporters import OtlpExporter

        assert OtlpExporter is not None

    def test_otlp_exporter_can_be_created(self) -> None:
        """Test that OtlpExporter can be instantiated."""
        from pyetwkit.exporters import OtlpExporter

        exporter = OtlpExporter(endpoint="http://localhost:4317")
        assert exporter is not None
        assert exporter.endpoint == "http://localhost:4317"

    def test_otlp_exporter_service_name(self) -> None:
        """Test service name configuration."""
        from pyetwkit.exporters import OtlpExporter

        exporter = OtlpExporter(
            endpoint="http://localhost:4317",
            service_name="my-etw-service",
        )
        assert exporter.service_name == "my-etw-service"

    def test_otlp_exporter_resource_attributes(self) -> None:
        """Test resource attributes configuration."""
        from pyetwkit.exporters import OtlpExporter

        exporter = OtlpExporter(
            endpoint="http://localhost:4317",
            resource_attributes={
                "host.name": "server-01",
                "deployment.environment": "production",
            },
        )
        assert exporter.resource_attributes["host.name"] == "server-01"

    def test_otlp_exporter_export_method(self) -> None:
        """Test export method exists."""
        from pyetwkit.exporters import OtlpExporter

        exporter = OtlpExporter(endpoint="http://localhost:4317")
        assert hasattr(exporter, "export")

    def test_otlp_exporter_batch_export(self) -> None:
        """Test batch export method exists."""
        from pyetwkit.exporters import OtlpExporter

        exporter = OtlpExporter(endpoint="http://localhost:4317")
        assert hasattr(exporter, "export_batch")


class TestSpanMapper:
    """Tests for SpanMapper class."""

    def test_span_mapper_exists(self) -> None:
        """Test that SpanMapper class exists."""
        from pyetwkit.exporters import SpanMapper

        assert SpanMapper is not None

    def test_span_mapper_can_be_created(self) -> None:
        """Test that SpanMapper can be instantiated."""
        from pyetwkit.exporters import SpanMapper

        mapper = SpanMapper()
        assert mapper is not None

    def test_span_mapper_add_rule(self) -> None:
        """Test adding mapping rules."""
        from pyetwkit.exporters import SpanMapper

        mapper = SpanMapper()
        mapper.add_rule(
            provider="Microsoft-Windows-Kernel-Process",
            event_id=1,
            span_name="process.start",
            attributes=["ProcessId", "ImageFileName", "CommandLine"],
        )
        assert len(mapper.rules) == 1

    def test_span_mapper_get_span_name(self) -> None:
        """Test getting span name for an event."""
        from pyetwkit.exporters import SpanMapper

        mapper = SpanMapper()
        mapper.add_rule(
            provider="Microsoft-Windows-Kernel-Process",
            event_id=1,
            span_name="process.start",
        )

        mock_event = MagicMock()
        mock_event.provider_name = "Microsoft-Windows-Kernel-Process"
        mock_event.event_id = 1

        span_name = mapper.get_span_name(mock_event)
        assert span_name == "process.start"

    def test_span_mapper_extract_attributes(self) -> None:
        """Test extracting attributes from event."""
        from pyetwkit.exporters import SpanMapper

        mapper = SpanMapper()
        mapper.add_rule(
            provider="TestProvider",
            event_id=1,
            span_name="test.event",
            attributes=["ProcessId", "ImageFileName"],
        )

        mock_event = MagicMock()
        mock_event.provider_name = "TestProvider"
        mock_event.event_id = 1
        mock_event.properties = {
            "ProcessId": 1234,
            "ImageFileName": "test.exe",
            "OtherField": "ignored",
        }

        attrs = mapper.extract_attributes(mock_event)
        assert attrs["ProcessId"] == 1234
        assert attrs["ImageFileName"] == "test.exe"
        assert "OtherField" not in attrs


class TestExportMode:
    """Tests for export modes."""

    def test_export_mode_enum_exists(self) -> None:
        """Test that ExportMode enum exists."""
        from pyetwkit.exporters import ExportMode

        assert ExportMode is not None

    def test_export_mode_values(self) -> None:
        """Test ExportMode enum values."""
        from pyetwkit.exporters import ExportMode

        assert hasattr(ExportMode, "SPANS")
        assert hasattr(ExportMode, "LOGS")
        assert hasattr(ExportMode, "METRICS")


class TestOtlpExporterConfig:
    """Tests for OtlpExporter configuration."""

    def test_otlp_config_exists(self) -> None:
        """Test that OtlpExporterConfig exists."""
        from pyetwkit.exporters import OtlpExporterConfig

        assert OtlpExporterConfig is not None

    def test_otlp_config_defaults(self) -> None:
        """Test default configuration values."""
        from pyetwkit.exporters import ExportMode, OtlpExporterConfig

        config = OtlpExporterConfig()
        assert config.batch_size == 100
        assert config.export_interval_ms == 1000
        assert config.export_mode == ExportMode.SPANS

    def test_otlp_config_custom(self) -> None:
        """Test custom configuration values."""
        from pyetwkit.exporters import ExportMode, OtlpExporterConfig

        config = OtlpExporterConfig(
            batch_size=500,
            export_interval_ms=5000,
            export_mode=ExportMode.LOGS,
        )
        assert config.batch_size == 500
        assert config.export_interval_ms == 5000
        assert config.export_mode == ExportMode.LOGS


class TestEventToSpanMapping:
    """Tests for ETW to OpenTelemetry mapping."""

    def test_event_to_span_conversion(self) -> None:
        """Test converting ETW event to OTel span."""
        from pyetwkit.exporters import event_to_span

        mock_event = MagicMock()
        mock_event.event_id = 1
        mock_event.provider_name = "TestProvider"
        mock_event.timestamp = 1234567890.0
        mock_event.process_id = 1234
        mock_event.thread_id = 5678
        mock_event.properties = {"key": "value"}

        span = event_to_span(mock_event, span_name="test.event")
        assert span is not None
        assert span["name"] == "test.event"

    def test_event_to_log_conversion(self) -> None:
        """Test converting ETW event to OTel log."""
        from pyetwkit.exporters import event_to_log

        mock_event = MagicMock()
        mock_event.event_id = 1
        mock_event.provider_name = "TestProvider"
        mock_event.timestamp = 1234567890.0
        mock_event.process_id = 1234
        mock_event.properties = {"message": "test"}

        log = event_to_log(mock_event)
        assert log is not None


class TestOtlpExporterIntegration:
    """Tests for OtlpExporter integration."""

    def test_exporter_with_session(self) -> None:
        """Test using exporter with ETW session."""
        from pyetwkit.exporters import OtlpExporter

        exporter = OtlpExporter(endpoint="http://localhost:4317")
        assert hasattr(exporter, "attach_to_session")

    def test_exporter_shutdown(self) -> None:
        """Test exporter shutdown."""
        from pyetwkit.exporters import OtlpExporter

        exporter = OtlpExporter(endpoint="http://localhost:4317")
        assert hasattr(exporter, "shutdown")

    def test_exporter_flush(self) -> None:
        """Test exporter flush."""
        from pyetwkit.exporters import OtlpExporter

        exporter = OtlpExporter(endpoint="http://localhost:4317")
        assert hasattr(exporter, "flush")


class TestOtlpHeaders:
    """Tests for OTLP headers configuration."""

    def test_custom_headers(self) -> None:
        """Test custom headers configuration."""
        from pyetwkit.exporters import OtlpExporter

        exporter = OtlpExporter(
            endpoint="http://localhost:4317",
            headers={"Authorization": "Bearer token123"},
        )
        assert "Authorization" in exporter.headers

    def test_insecure_option(self) -> None:
        """Test insecure (non-TLS) option."""
        from pyetwkit.exporters import OtlpExporter

        exporter = OtlpExporter(
            endpoint="http://localhost:4317",
            insecure=True,
        )
        assert exporter.insecure is True


class TestSampling:
    """Tests for sampling configuration."""

    def test_sample_rate(self) -> None:
        """Test sample rate configuration."""
        from pyetwkit.exporters import OtlpExporter

        exporter = OtlpExporter(
            endpoint="http://localhost:4317",
            sample_rate=0.1,
        )
        assert exporter.sample_rate == 0.1

    def test_sample_rate_validation(self) -> None:
        """Test sample rate validation."""
        from pyetwkit.exporters import OtlpExporter

        with pytest.raises(ValueError):
            OtlpExporter(
                endpoint="http://localhost:4317",
                sample_rate=1.5,  # Invalid: > 1.0
            )

        with pytest.raises(ValueError):
            OtlpExporter(
                endpoint="http://localhost:4317",
                sample_rate=-0.1,  # Invalid: < 0.0
            )


class TestOtlpFileExport:
    """Tests for OTLP file export."""

    def test_file_exporter_exists(self) -> None:
        """Test that OtlpFileExporter exists."""
        from pyetwkit.exporters import OtlpFileExporter

        assert OtlpFileExporter is not None

    def test_file_exporter_can_be_created(self) -> None:
        """Test that OtlpFileExporter can be instantiated."""
        from pyetwkit.exporters import OtlpFileExporter

        exporter = OtlpFileExporter(output_path="traces.json")
        assert exporter is not None
        assert exporter.output_path == "traces.json"

    def test_file_exporter_formats(self) -> None:
        """Test supported file formats."""
        from pyetwkit.exporters import OtlpFileFormat

        assert hasattr(OtlpFileFormat, "JSON")
        assert hasattr(OtlpFileFormat, "PROTOBUF")
