"""Demo script for PyETWkit v3.0.0 features.

This demonstrates:
- Dashboard: Real-time WebSocket UI for ETW events
- CorrelationEngine: Link related events by PID/TID/Handle
- Recording/Player: Record and replay ETW sessions
- OtlpExporter: Export events to OpenTelemetry
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

print("=" * 60)
print("PyETWkit v3.0.0 Feature Demo")
print("=" * 60)

# 1. Dashboard - Real-time WebSocket UI
print("\n1. Dashboard - Real-time WebSocket UI")
print("-" * 50)

from pyetwkit import Dashboard, DashboardConfig, EventSerializer

# Create a dashboard
dashboard = Dashboard(host="127.0.0.1", port=8080)
dashboard.add_provider("Microsoft-Windows-Kernel-Process")
dashboard.add_provider("Microsoft-Windows-DNS-Client")

print("Dashboard created:")
print(f"  HTTP URL: {dashboard.url}")
print(f"  WebSocket URL: {dashboard.ws_url}")
print(f"  Providers: {dashboard.providers}")

# Custom configuration
config = DashboardConfig(
    host="0.0.0.0",
    port=9000,
    enable_cors=True,
    max_clients=50,
    event_buffer_size=5000,
)
print("\nCustom config example:")
print(f"  max_clients: {config.max_clients}")
print(f"  event_buffer_size: {config.event_buffer_size}")

# EventSerializer for JSON output
serializer = EventSerializer()
mock_event = MagicMock()
mock_event.event_id = 1
mock_event.provider_name = "Test"
mock_event.timestamp = 1234567890.0
mock_event.process_id = 1234
mock_event.thread_id = 5678
mock_event.properties = {"key": "value"}
json_output = serializer.serialize(mock_event)
print(f"\nSerialized event: {json_output[:60]}...")

# 2. CorrelationEngine - Link related events
print("\n2. CorrelationEngine - Link related events by PID/TID/Handle")
print("-" * 50)

from pyetwkit import CorrelationEngine, CorrelationKeyType

# Create correlation engine
engine = CorrelationEngine()
engine.add_provider("Microsoft-Windows-Kernel-Process")
engine.add_provider("Microsoft-Windows-Kernel-Network")


# Create mock events for demonstration
def create_mock_event(event_id, pid, tid, provider, timestamp):
    event = MagicMock()
    event.event_id = event_id
    event.process_id = pid
    event.thread_id = tid
    event.provider_name = provider
    event.timestamp = timestamp
    event.properties = {}
    return event


# Add events from multiple providers for the same process
base_time = datetime.now()
events = [
    create_mock_event(1, 1234, 100, "Kernel-Process", base_time),
    create_mock_event(2, 1234, 100, "Kernel-Network", base_time + timedelta(milliseconds=50)),
    create_mock_event(3, 1234, 101, "Kernel-Process", base_time + timedelta(milliseconds=100)),
    create_mock_event(4, 5678, 200, "Kernel-Network", base_time + timedelta(milliseconds=150)),
]

for event in events:
    engine.add_event(event)

print(f"Added {engine.event_count} events from {len(engine.providers)} providers")

# Correlate by PID
correlated = engine.correlate_by_pid(1234)
print(f"\nEvents correlated by PID 1234: {len(correlated)} events")
for e in correlated:
    print(f"  - Event {e.event_id} from {e.provider_name} (TID: {e.thread_id})")

# Get correlation groups
print("\nCorrelation groups (by PID):")
for group in engine.correlated_groups():
    print(f"  PID {group.pid}: {len(group.events)} events")

# Export to JSON timeline
timeline_json = engine.to_timeline_json(pid=1234)
print(f"\nTimeline JSON preview: {timeline_json[:80]}...")

# 3. Recording & Player - Record and replay sessions
print("\n3. Recording & Player - Record and replay ETW sessions")
print("-" * 50)

from pyetwkit import CompressionType, Player, Recorder, RecorderConfig

# Create a recorder with custom configuration
config = RecorderConfig(
    compression=CompressionType.ZSTD,
    chunk_size=1024 * 1024,  # 1MB
    buffer_size=64 * 1024,  # 64KB
)

# Create a temporary file for demonstration
with tempfile.NamedTemporaryFile(suffix=".etwpack", delete=False) as f:
    temp_path = Path(f.name)

recorder = Recorder(temp_path, config=config)
recorder.add_provider("Microsoft-Windows-DNS-Client")

print("Recorder created:")
print(f"  Output: {recorder.output_path}")
print(f"  Providers: {recorder.providers}")
print(f"  Compression: {config.compression.value}")

# Record some events
recorder.start()
for event in events[:3]:
    recorder.add_event(event)
recorder.stop()

print(f"\nRecorded {len(events[:3])} events to {temp_path.name}")

# Play back the recording
player = Player(temp_path)
print("\nPlayer loaded:")
print(f"  Duration: {player.duration:.2f}s")
print(f"  Event count: {player.event_count}")

# Iterate events with filtering
print("\nEvents from playback:")
for event in player.events():
    print(f"  - Event {event.get('event_id')} from {event.get('provider_name')}")

# Cleanup
temp_path.unlink(missing_ok=True)

# 4. OtlpExporter - Export to OpenTelemetry
print("\n4. OtlpExporter - Export events to OpenTelemetry")
print("-" * 50)

from pyetwkit import ExportMode, OtlpExporter, OtlpExporterConfig, SpanMapper

# Create an OTLP exporter
exporter = OtlpExporter(
    endpoint="http://collector:4317",
    service_name="pyetwkit-demo",
    resource_attributes={
        "deployment.environment": "production",
        "service.version": "3.0.0",
    },
    sample_rate=1.0,
)

print("OtlpExporter created:")
print(f"  Endpoint: {exporter.endpoint}")
print(f"  Service: {exporter.service_name}")
print(f"  Sample rate: {exporter.sample_rate}")

# Create a SpanMapper for custom event-to-span mapping
mapper = SpanMapper()
mapper.add_rule(
    provider="Microsoft-Windows-Kernel-Process",
    event_id=1,
    span_name="process.start",
    attributes=["ProcessId", "ImageFileName", "CommandLine"],
)
mapper.add_rule(
    provider="Microsoft-Windows-DNS-Client",
    event_id=3006,
    span_name="dns.query",
    attributes=["QueryName", "QueryType"],
)

print(f"\nSpanMapper rules configured: {len(mapper.rules)} rules")
for rule in mapper.rules:
    print(f"  - {rule.provider}:{rule.event_id} -> {rule.span_name}")

# Export configuration options
export_config = OtlpExporterConfig(
    batch_size=100,
    export_interval_ms=1000,
    export_mode=ExportMode.SPANS,
    timeout_ms=30000,
)
print("\nExporter config:")
print(f"  Batch size: {export_config.batch_size}")
print(f"  Export mode: {export_config.export_mode.value}")

# Export events (simulated)
print("\nExporting events...")
for event in events[:2]:
    success = exporter.export(event)
    print(f"  Exported event {event.event_id}: {'OK' if success else 'FAILED'}")

exporter.flush()
print("  Flush complete!")

# 5. Correlation Key Types
print("\n5. Available Correlation Key Types")
print("-" * 50)

print("CorrelationKeyType enum values:")
for key_type in CorrelationKeyType:
    print(f"  - {key_type.name}: {key_type.value}")

print("\n" + "=" * 60)
print("v3.0.0 Demo Complete!")
print("=" * 60)
