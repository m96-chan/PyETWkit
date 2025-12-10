# PyETWkit Architecture

## Overview

PyETWkit is a high-performance ETW (Event Tracing for Windows) consumer library that provides a Pythonic interface for consuming Windows ETW events. It is built on top of [ferrisetw](https://github.com/n4r1b/ferrisetw), a Rust port of Microsoft's KrabsETW.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Python Layer                                    │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐   │
│  │   EtwListener    │  │   EtwStreamer    │  │   Pre-configured         │   │
│  │  (Sync API)      │  │  (Async API)     │  │   Providers              │   │
│  │  - __iter__      │  │  - __aiter__     │  │   - KernelProvider       │   │
│  │  - events()      │  │  - events()      │  │   - NetworkProvider      │   │
│  │  - Context Mgr   │  │  - Async Ctx Mgr │  │   - ProcessProvider      │   │
│  └────────┬─────────┘  └────────┬─────────┘  └──────────────────────────┘   │
│           │                     │                                            │
│           ▼                     ▼                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    pyetwkit._core (Rust Extension)                    │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │ PyEtwEvent  │  │PyEtwProvider│  │ PyEtwSession│  │PyKernelSess │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│  └───────────────────────────────┬──────────────────────────────────────┘   │
└──────────────────────────────────┼──────────────────────────────────────────┘
                                   │ pyo3 bindings
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Rust Layer (pyetwkit-core)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐     │
│  │  EtwEvent   │  │ EtwProvider │  │ EtwSession  │  │ KernelSession   │     │
│  │  - parse    │  │  - by_guid  │  │  - start    │  │  - enable_*     │     │
│  │  - to_json  │  │  - filters  │  │  - stop     │  │  - process/file │     │
│  └─────────────┘  └─────────────┘  └──────┬──────┘  └────────┬────────┘     │
│                                           │                   │              │
│  ┌─────────────┐  ┌─────────────┐  ┌──────┴───────────────────┴──────┐      │
│  │EventFilter  │  │SessionStats │  │           ferrisetw             │      │
│  │  - event_id │  │  - received │  │  - UserTrace / KernelTrace      │      │
│  │  - opcode   │  │  - lost     │  │  - Provider builder             │      │
│  │  - process  │  │  - eps      │  │  - Parser / Schema              │      │
│  └─────────────┘  └─────────────┘  └─────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Windows ETW Subsystem                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                    ETW Session (Kernel Mode)                        │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │     │
│  │  │ Provider A  │  │ Provider B  │  │ Kernel Prov │                 │     │
│  │  │ (User Mode) │  │ (User Mode) │  │ (NT Kernel) │                 │     │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │     │
│  │         │                │                │                         │     │
│  │         ▼                ▼                ▼                         │     │
│  │  ┌──────────────────────────────────────────────────────────┐      │     │
│  │  │              ETW Buffers (Ring Buffer)                    │      │     │
│  │  └───────────────────────────┬──────────────────────────────┘      │     │
│  └──────────────────────────────┼──────────────────────────────────────┘     │
│                                 │ ProcessTrace callback                       │
│                                 ▼                                             │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  TDH (Trace Data Helper) - Schema Resolution                       │     │
│  │  - TdhGetEventInformation                                          │     │
│  │  - TdhFormatProperty                                               │     │
│  └────────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Description

### Python Layer

#### EtwListener (Synchronous API)
- Provides blocking iteration over events
- Supports Python iterator protocol (`__iter__`)
- Context manager for automatic cleanup
- Timeout and max_events parameters for controlled iteration

#### EtwStreamer (Asynchronous API)
- Provides async iteration over events (`async for`)
- Async context manager support
- Non-blocking event polling with configurable interval
- Integration with asyncio event loop

#### Pre-configured Providers
- Factory classes for common ETW providers
- KernelProvider: Process, Thread, File, Network, Registry
- NetworkProvider: DNS, TCP/IP, Winsock
- ProcessProvider: Process lifecycle, Image loads
- SecurityProvider: Security auditing, Threat Intelligence

### Rust Layer (pyetwkit-core)

#### EtwSession
- Main ETW session management
- Provider registration and configuration
- Event channel for cross-thread communication
- Statistics tracking (events received, lost, EPS)

#### EtwProvider
- Provider configuration builder
- GUID-based provider identification
- Trace level and keyword filtering
- Event ID and process filtering

#### EtwEvent
- Parsed event data structure
- Property access by name
- JSON serialization
- Timestamp handling (Windows FILETIME to Unix)

#### KernelSession
- Special session for NT Kernel Logger
- Category-based event enabling
- Process, Thread, File I/O, Network events

#### EventFilter
- Composable filter chain
- Event ID, opcode, process ID filters
- Exclusion filters

### ferrisetw Integration

PyETWkit wraps ferrisetw, which provides:
- Safe Rust abstractions for ETW APIs
- UserTrace and KernelTrace builders
- Schema resolution via TDH APIs
- Event parsing with type-safe property access

## Data Flow

1. **Session Start**: Python creates EtwListener/EtwStreamer
2. **Provider Enable**: Providers registered with ETW session
3. **Event Generation**: Windows components write to ETW buffers
4. **Event Callback**: ferrisetw receives events via ProcessTrace
5. **Event Parsing**: Schema resolved, properties parsed
6. **Channel Send**: Events sent through crossbeam channel
7. **Python Receive**: Events yielded to Python iterator

## Thread Model

```
Main Thread (Python)              Background Thread (Rust)
──────────────────────            ─────────────────────────

listener.start() ──────────────▶ spawn trace thread
                                  │
                                  ▼
for event in listener: ◀───────── ProcessTrace loop
    process(event)                 │
                                   ├─▶ callback(record)
                                   │     │
                                   │     ▼
                                   │   parse event
                                   │     │
                                   │     ▼
                                   │   channel.send(event)
                                   │
listener.stop() ──────────────▶ stop trace
                                  │
                                  ▼
                                thread join
```

## Error Handling

- **Rust errors**: Converted to Python exceptions via pyo3
- **Permission errors**: OSError with clear message about admin privileges
- **Channel errors**: RuntimeError for closed/full channels
- **Windows API errors**: Wrapped with error codes

## Performance Considerations

1. **Zero-copy where possible**: Events parsed directly from buffers
2. **Bounded channels**: Backpressure via channel capacity limits
3. **Statistics tracking**: Atomic counters for loss detection
4. **Lazy schema resolution**: Schemas cached by ferrisetw
5. **Release builds**: LTO and single codegen unit for smaller binaries
