# PyETWkit

[![PyPI version](https://badge.fury.io/py/pyetwkit.svg)](https://badge.fury.io/py/pyetwkit)
[![Python](https://img.shields.io/pypi/pyversions/pyetwkit.svg)](https://pypi.org/project/pyetwkit/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/m96-chan/PyETWkit/actions/workflows/ci.yml/badge.svg)](https://github.com/m96-chan/PyETWkit/actions/workflows/ci.yml)

A modern, high-performance ETW (Event Tracing for Windows) toolkit for Python, powered by a Rust backend.

---

## Features

### Core
- **Real-time ETW streaming** with sync API
- **Kernel providers**: process, thread, registry, file, disk, network
- **User providers**: DNS, Audio, and more via profiles
- **ETL file reading**: Parse existing trace logs
- **Rust backend (pyo3)**: High throughput, zero-copy event delivery
- Windows 10 / 11 / Server supported

### v2.0 - Enterprise Features
- **Multi-session support**: Run multiple ETW sessions simultaneously
- **Manifest-based typed events**: Parse ETW manifests for structured event data
- **Rust-side filtering**: High-performance event filtering in Rust
- **Provider discovery**: Search and list available providers
- **Pre-configured profiles**: Audio, network, security scenarios

### v3.0 - Advanced Analysis
- **Live Dashboard**: Browser-based real-time visualization with Gradio
- **Event Correlation Engine**: Auto-correlate events by PID/TID/Handle
- **Recording & Replay**: Capture and replay ETW sessions (.etwpack format)
- **OpenTelemetry Exporter**: Export events to OTLP (Jaeger, Grafana, Datadog)

### Export Formats
- CSV, JSON, JSONL, Parquet, Arrow

---

## Installation

```bash
pip install pyetwkit

# Optional: Dashboard support
pip install pyetwkit[dashboard]

# Optional: Export to Parquet/Arrow
pip install pyetwkit[export]
```

---

## Quick Start

### CLI Usage

```bash
# List available providers
pyetwkit providers
pyetwkit providers --search Kernel

# List profiles
pyetwkit profiles

# Listen to events (requires admin)
pyetwkit listen Microsoft-Windows-DNS-Client
pyetwkit listen --profile network

# Launch live dashboard (requires admin)
pyetwkit dashboard Microsoft-Windows-Kernel-Process
pyetwkit dashboard --profile network --port 8080

# Export ETL file
pyetwkit export trace.etl -o events.csv
pyetwkit export trace.etl -o events.parquet -f parquet
```

### Python API

```python
from pyetwkit._core import EtwProvider, EtwSession

# Create session
session = EtwSession("MySession")

# Add provider
provider = EtwProvider(
    "Microsoft-Windows-DNS-Client",
    "DNS-Client"
)
provider = provider.with_level(4)  # Info level
session.add_provider(provider)

# Start and process events
session.start()

try:
    while True:
        event = session.next_event_timeout(1000)
        if event:
            print(f"Event {event.event_id}: {event.provider_name}")
except KeyboardInterrupt:
    pass
finally:
    session.stop()
```

### Live Dashboard

```python
from pyetwkit import Dashboard

# Create and launch dashboard
dashboard = Dashboard(port=7860)
dashboard.add_provider("Microsoft-Windows-Kernel-Process")
dashboard.add_provider("Microsoft-Windows-DNS-Client")

# Opens browser at http://localhost:7860
dashboard.launch()
```

### Event Correlation

```python
from pyetwkit import CorrelationEngine

# Create correlation engine
engine = CorrelationEngine()
engine.add_provider("Microsoft-Windows-Kernel-Process")
engine.add_provider("Microsoft-Windows-Kernel-Network")

# Add events from your ETW session
for event in events:
    engine.add_event(event)

# Correlate events by process ID
correlated = engine.correlate_by_pid(1234)
for event in correlated:
    print(f"Event {event.event_id} from {event.provider_name}")

# Export to timeline JSON
timeline = engine.to_timeline_json(pid=1234)
```

### Recording & Replay

```python
from pyetwkit import Recorder, Player, CompressionType, RecorderConfig

# Record events
config = RecorderConfig(compression=CompressionType.ZSTD)
recorder = Recorder("session.etwpack", config=config)
recorder.add_provider("Microsoft-Windows-DNS-Client")
recorder.start()

# ... capture events ...
recorder.stop()

# Replay events
player = Player("session.etwpack")
print(f"Duration: {player.duration:.2f}s, Events: {player.event_count}")

for event in player.events():
    print(f"Event {event['event_id']}")
```

### OpenTelemetry Export

```python
from pyetwkit import OtlpExporter, SpanMapper

# Configure exporter
exporter = OtlpExporter(
    endpoint="http://collector:4317",
    service_name="my-service",
    resource_attributes={
        "deployment.environment": "production",
    },
)

# Map ETW events to spans
mapper = SpanMapper()
mapper.add_rule(
    provider="Microsoft-Windows-Kernel-Process",
    event_id=1,
    span_name="process.start",
    attributes=["ProcessId", "ImageFileName"],
)

# Export events
for event in events:
    exporter.export(event)
exporter.flush()
```

### Kernel Tracing

```python
from pyetwkit._core import PyKernelFlags, PyKernelSession

flags = PyKernelFlags()
flags = flags.with_process()  # Enable process events

session = PyKernelSession(flags)
session.start()

for _ in range(10):
    event = session.next_event_timeout(1000)
    if event and event.event_id == 1:  # Process start
        props = event.to_dict().get("properties", {})
        print(f"Process: {props.get('ImageFileName')}")

session.stop()
```

### Provider Discovery

```python
from pyetwkit._core import list_providers, search_providers

# List all providers
for p in list_providers()[:10]:
    print(f"{p.name}: {p.guid}")

# Search by name
for p in search_providers("Kernel"):
    print(p.name)
```

### Export Events

```python
from pyetwkit._core import EtlReader
from pyetwkit.export import to_csv, to_parquet

# Read ETL file
reader = EtlReader("trace.etl")
events = list(reader.events())

# Export to various formats
to_csv(events, "events.csv")
to_parquet(events, "events.parquet")
```

---

## Architecture

```
Python API / CLI
  ↓
pyetwkit (Python package)
  ↓
pyetwkit._core (Rust/pyo3)
  ↓
ferrisetw (Rust ETW library)
  ↓
Windows ETW subsystem
```

---

## Documentation

- [Tutorial](docs/tutorial.md) - Comprehensive usage guide
- [API Reference](docs/api/) - Detailed API documentation
- [Examples](examples/) - Sample scripts
- [Architecture](docs/architecture/) - Design documents

---

## Changelog

### v3.0.0 (2024-12)
- **Live Dashboard**: Gradio-based real-time UI (`pyetwkit dashboard` CLI)
- **Event Correlation Engine**: Link events by PID/TID/Handle with timeline export
- **Recording & Replay**: Capture sessions to `.etwpack` format with compression
- **OpenTelemetry Exporter**: Export to OTLP endpoints (Jaeger, Grafana, etc.)

### v2.0.0 (2024-12)
- **Multi-session support**: Run multiple ETW sessions simultaneously
- **Manifest-based typed events**: Parse ETW provider manifests
- **Rust-side filtering**: High-performance filtering with `RustEventFilter`
- **Enhanced CLI**: Provider profiles, export options

### v1.0.0 (2024-12)
- Initial release
- Real-time ETW streaming
- Kernel and user-mode providers
- ETL file reading
- Export to CSV, JSON, JSONL, Parquet, Arrow
- CLI tool with provider discovery

---

## Examples

See the [examples/](examples/) directory for complete sample scripts:

- `basic_session.py` - Simple ETW session
- `kernel_trace.py` - Kernel-level process monitoring
- `export_events.py` - Capture and export events
- `provider_discovery.py` - Find ETW providers
- `profiles.py` - Use pre-configured profiles
- `read_etl.py` - Read ETL files
- `demo_v2_features.py` - v2.0 features demo
- `demo_v3_features.py` - v3.0 features demo

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

[MIT](LICENSE)

---

## Author

[m96-chan](https://github.com/m96-chan)
