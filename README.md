# PyETWkit

[![PyPI version](https://badge.fury.io/py/pyetwkit.svg)](https://badge.fury.io/py/pyetwkit)
[![Python](https://img.shields.io/pypi/pyversions/pyetwkit.svg)](https://pypi.org/project/pyetwkit/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/m96-chan/PyETWkit/actions/workflows/ci.yml/badge.svg)](https://github.com/m96-chan/PyETWkit/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/m96-chan/PyETWkit/branch/main/graph/badge.svg)](https://codecov.io/gh/m96-chan/PyETWkit)

A modern, high-performance ETW (Event Tracing for Windows) toolkit for Python, powered by a Rust backend.

---

## Features

- Real-time ETW streaming (sync & async)
- Kernel providers: process, thread, registry, file, disk, network...
- User providers: NDIS, Media Foundation, WASAPI, DXGI, Audio...
- Filtering: provider / event ID / PID / opcode
- **Rust backend (pyo3)** for high throughput & zero-copy event delivery
- Windows 10 / 11 / Server supported
- Modern, simple Python API (no ctypes hell)

---

## Installation

```bash
pip install pyetwkit
```

> Note: We recommend starting with TestPyPI releases during early development.

---

## Quick Start

### Listen to process events

```python
from pyetwkit import EtwListener

listener = EtwListener("Microsoft-Windows-Kernel-Process")

for event in listener.events():
    print(event.timestamp, event.process_id, event.event_name)
```

---

### Async streaming

```python
import asyncio
from pyetwkit import EtwStreamer

async def main():
    async for e in EtwStreamer("Microsoft-Windows-Kernel-Network"):
        print(e)

asyncio.run(main())
```

---

### Filter by PID

```python
listener = EtwListener("Microsoft-Windows-Kernel-Process", pid=1234)

for e in listener:
    print("Process event:", e)
```

---

## Architecture

```
Python API
  ↓
Rust backend (pyo3)
  ↓
Windows ETW subsystem
```

- Rust handles real-time ETW session processing
- Fast and safe struct passing to Python
- Strong backpressure handling with minimal latency

---

## Providers (Examples)

| Provider | Description |
|---------|-------------|
| Microsoft-Windows-Kernel-Process | Process create/exit |
| Microsoft-Windows-Kernel-Thread | Thread lifecycle |
| Microsoft-Windows-Kernel-File | File I/O |
| Microsoft-Windows-Kernel-Network | TCP/UDP events |
| Microsoft-Windows-Kernel-Registry | Registry operations |
| Microsoft-Windows-Win32k | UI subsystem |

User providers (MF, Audio, DXGI, NDIS, WASAPI) are also available.

---

## Rust Backend (WIP)

Rust crate structure:
```
pyetwkit-core/
 ├─ src/
 │   ├─ lib.rs
 │   ├─ consumer.rs
 │   ├─ provider.rs
 │   └─ event.rs
 ├─ Cargo.toml
```

Python binding via **pyo3**:
```rust
#[pyfunction]
fn start_provider(provider: String) -> PyResult<()> {
    // Start ETW session
}
```

---

## Roadmap

- [ ] Minimal Rust ETW consumer
- [ ] Provider auto-discovery
- [ ] Schema loader (manifest reader)
- [ ] Parquet / Arrow / Pandas export
- [ ] pyetwkit-cli (live viewer)
- [ ] Provider profiles for Audio / VRChat / OBS

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

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
