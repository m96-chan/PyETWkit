# PyETWkit
A modern, high-performance ETW (Event Tracing for Windows) toolkit for Python, powered by a Rust backend.

---

## ✨ Features
- 🔥 Real-time ETW streaming (sync & async)
- ⚙️ Kernel providers: process, thread, registry, file, disk, network…
- 🪟 User providers: NDIS, Media Foundation, WASAPI, DXGI, Audio…
- 🎯 Filtering: provider / event ID / PID / opcode
- 🚀 **Rust backend (pyo3)** for high throughput & zero-copy event delivery
- 🧪 Windows 10 / 11 / Server supported
- 🧠 Modern, simple Python API (no ctypes hell)

---

## 🔧 Installation
```
pip install pyetwkit
```

(※ TestPyPI リリースから始めることを推奨)

---

## 🚀 Quick Start

### Listen to process events
```python
from PyETWkit import EtwListener

listener = EtwListener("Microsoft-Windows-Kernel-Process")

for event in listener.events():
    print(event.timestamp, event.process_id, event.event_name)
```

---

### Async streaming
```python
import asyncio
from PyETWkit import EtwStreamer

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

## 🧩 Architecture
```
Python API
  ↓
Rust backend (pyo3)
  ↓
Windows ETW subsystem
```

- Rust がリアルタイム ETW セッションを処理  
- Python には高速で安全な構造体を渡す  
- バックプレッシャーに強く、遅延が小さい

---

## 📚 Providers (Examples)

| Provider | Description |
|---------|-------------|
| Microsoft-Windows-Kernel-Process | Process create/exit |
| Microsoft-Windows-Kernel-Thread | Thread lifecycle |
| Microsoft-Windows-Kernel-File | File I/O |
| Microsoft-Windows-Kernel-Network | TCP/UDP events |
| Microsoft-Windows-Kernel-Registry | Registry operations |
| Microsoft-Windows-Win32k | UI subsystem |

User providers (MF, Audio, DXGI, NDIS, WASAPI) も使用可能。

---

## 🛠 Rust Backend (WIP)

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

## 🗺 Roadmap
- [ ] Minimal Rust ETW consumer
- [ ] Provider auto-discovery
- [ ] Schema loader (manifest reader)
- [ ] Parquet / Arrow / Pandas export
- [ ] pyetwkit-cli (live viewer)
- [ ] Audio / VRChat / OBS 向け provider プロファイル

---

## 📝 License
MIT

---

## 🧑‍💻 Author
[m96-chan](https://github.com/m96-chan)S
