# PyETWkit

[![PyPI version](https://badge.fury.io/py/pyetwkit.svg)](https://badge.fury.io/py/pyetwkit)
[![Python](https://img.shields.io/pypi/pyversions/pyetwkit.svg)](https://pypi.org/project/pyetwkit/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/m96-chan/PyETWkit/actions/workflows/ci.yml/badge.svg)](https://github.com/m96-chan/PyETWkit/actions/workflows/ci.yml)

A modern, high-performance ETW (Event Tracing for Windows) toolkit for Python, powered by a Rust backend.

---

## Features

- **Real-time ETW streaming** with sync API
- **Kernel providers**: process, thread, registry, file, disk, network
- **User providers**: DNS, Audio, and more via profiles
- **Filtering**: by provider, event ID, trace level
- **ETL file reading**: Parse existing trace logs
- **Export**: CSV, JSON, JSONL, Parquet, Arrow formats
- **CLI tool**: `pyetwkit` command for quick monitoring
- **Provider discovery**: Search and list available providers
- **Pre-configured profiles**: Audio, network, security scenarios
- **Rust backend (pyo3)**: High throughput, zero-copy event delivery
- Windows 10 / 11 / Server supported

---

## Installation

```bash
pip install pyetwkit
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

## Roadmap

### Completed

- [x] Rust ETW consumer (ferrisetw backend)
- [x] Provider discovery and enumeration
- [x] User-mode ETW sessions
- [x] Kernel-mode tracing (process, thread, image load)
- [x] Event schema and property parsing
- [x] ETL file reading
- [x] Export to CSV, JSON, JSONL, Parquet, Arrow
- [x] CLI tool (`pyetwkit` command)
- [x] Provider profiles (audio, network, security)
- [x] Stack trace capture support
- [x] Session statistics

### Planned

#### v1.1 - Enhanced Core
- [ ] [Async streaming API](https://github.com/m96-chan/PyETWkit/issues/54)
- [ ] [Manifest-based typed events](https://github.com/m96-chan/PyETWkit/issues/55)
- [ ] [Real-time event filtering callbacks](https://github.com/m96-chan/PyETWkit/issues/56)

#### v2.0 - Enterprise Features
- [ ] [Multi-session / Multi-provider concurrent subscription](https://github.com/m96-chan/PyETWkit/issues/48)
  - Kernel + User + Custom providers simultaneously
  - Unified event stream delivery
- [ ] [OpenTelemetry (OTLP) Exporter](https://github.com/m96-chan/PyETWkit/issues/52)
  - Integration with Jaeger, Grafana, Datadog
  - Enterprise observability standard
- [ ] [ETW Recording & Replay (.etwpack)](https://github.com/m96-chan/PyETWkit/issues/51)
  - Python-optimized capture format
  - Faster than native ETL files

#### v3.0 - Advanced Analysis
- [ ] [Event Correlation Engine](https://github.com/m96-chan/PyETWkit/issues/50)
  - Auto-correlate by PID/TID/Handle
  - Unified activity timelines
  - "Wireshark for ETW" level insight
- [ ] [Live Dashboard with WebSocket UI](https://github.com/m96-chan/PyETWkit/issues/49)
  - Browser-based real-time visualization
  - CPU, Network, Disk, Audio monitoring
  - VRChat/Unity/OBS support

---

## Examples

See the [examples/](examples/) directory for complete sample scripts:

- `basic_session.py` - Simple ETW session
- `kernel_trace.py` - Kernel-level process monitoring
- `export_events.py` - Capture and export events
- `provider_discovery.py` - Find ETW providers
- `profiles.py` - Use pre-configured profiles
- `read_etl.py` - Read ETL files

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
