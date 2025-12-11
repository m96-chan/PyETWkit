# PyETWkit Tutorial

This tutorial guides you through the main features of PyETWkit.

## Installation

```bash
pip install pyetwkit
```

## Quick Start

### Using the CLI

PyETWkit provides a command-line interface for quick ETW monitoring:

```bash
# List available providers
pyetwkit providers

# Search for specific providers
pyetwkit providers --search DNS

# List available profiles
pyetwkit profiles

# Listen to events (requires admin)
pyetwkit listen Microsoft-Windows-DNS-Client

# Use a profile
pyetwkit listen --profile network
```

### Basic Python Usage

```python
from pyetwkit._core import EtwProvider, EtwSession

# Create a session
session = EtwSession("MySession")

# Add a provider
provider = EtwProvider(
    "Microsoft-Windows-DNS-Client",
    "Microsoft-Windows-DNS-Client"
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

## Core Concepts

### ETW Sessions

An ETW session is a connection to the Windows Event Tracing infrastructure.
Each session must have a unique name.

```python
from pyetwkit._core import EtwSession

session = EtwSession("UniqueSessionName")
```

### Providers

Providers are the sources of ETW events. Each provider has a name and GUID.

```python
from pyetwkit._core import EtwProvider

# Using provider name
provider = EtwProvider("Microsoft-Windows-DNS-Client", "DNS-Client")

# Set trace level (1=Critical, 2=Error, 3=Warning, 4=Info, 5=Verbose)
provider = provider.with_level(4)

# Enable all keywords (event categories)
provider = provider.with_any_keyword(0xFFFFFFFF)
```

### Provider Discovery

Find available providers on the system:

```python
from pyetwkit._core import list_providers, search_providers, get_provider_info

# List all providers
providers = list_providers()
for p in providers[:10]:
    print(f"{p.name}: {p.guid}")

# Search by name
kernel_providers = search_providers("Kernel")

# Get detailed info
info = get_provider_info("Microsoft-Windows-DNS-Client")
if info:
    print(f"GUID: {info.guid}")
```

### Profiles

Profiles are pre-configured sets of providers for common use cases:

```python
from pyetwkit.profiles import list_profiles, get_profile

# List available profiles
for profile in list_profiles():
    print(f"{profile.name}: {profile.description}")

# Get a specific profile
network = get_profile("network")
if network:
    for p in network.providers:
        print(f"  {p.name}")
```

## Kernel Tracing

Monitor kernel-level events like process creation:

```python
from pyetwkit._core import PyKernelFlags, PyKernelSession

# Configure kernel flags
flags = PyKernelFlags()
flags = flags.with_process()      # Process events
flags = flags.with_thread()       # Thread events
flags = flags.with_image_load()   # DLL/module loads

# Create and start session
session = PyKernelSession(flags)
session.start()

try:
    while True:
        event = session.next_event_timeout(1000)
        if event:
            if event.event_id == 1:  # Process start
                props = event.to_dict().get("properties", {})
                print(f"Process started: {props.get('ImageFileName')}")
except KeyboardInterrupt:
    pass
finally:
    session.stop()
```

## Reading ETL Files

Read events from saved ETL (Event Trace Log) files:

```python
from pyetwkit._core import EtlReader

reader = EtlReader("trace.etl")
for event in reader.events():
    print(f"[{event.timestamp}] {event.provider_name} Event {event.event_id}")
```

## Exporting Events

Export captured events to various formats:

```python
from pyetwkit.export import to_csv, to_json, to_jsonl, to_parquet

# Collect events
events = []
for event in reader.events():
    events.append(event)

# Export to different formats
to_csv(events, "events.csv")
to_json(events, "events.json", indent=2)
to_jsonl(events, "events.jsonl")
to_parquet(events, "events.parquet")  # Requires pyarrow
```

## CLI Export

Export ETL files from the command line:

```bash
# Export to CSV
pyetwkit export trace.etl -o events.csv

# Export to Parquet
pyetwkit export trace.etl -o events.parquet -f parquet

# Filter by provider
pyetwkit export trace.etl -o filtered.csv -p Microsoft-Windows-DNS-Client

# Limit number of events
pyetwkit export trace.etl -o sample.json -f json --limit 1000
```

## Event Structure

Each event contains:

- `event_id`: Event type identifier
- `provider_name`: Source provider name
- `provider_id`: Provider GUID
- `timestamp`: When the event occurred
- `process_id`: Source process ID
- `thread_id`: Source thread ID
- `properties`: Event-specific data

```python
event_dict = event.to_dict()
print(f"Event ID: {event_dict['event_id']}")
print(f"Properties: {event_dict.get('properties', {})}")
```

## Best Practices

1. **Use unique session names** - Avoid conflicts with other ETW consumers
2. **Stop sessions properly** - Always call `session.stop()` in a finally block
3. **Filter at source** - Use trace levels and keywords to reduce event volume
4. **Run as administrator** - ETW sessions require elevated privileges
5. **Handle timeouts** - Use `next_event_timeout()` for non-blocking operation

## Troubleshooting

### "Access denied" errors

ETW sessions require administrator privileges. Run your script or terminal as Administrator.

### Session already exists

If a previous session wasn't properly stopped, clean it up:

```bash
logman stop MySession -ets
```

### No events received

- Check that the provider name is correct
- Ensure the trace level includes the events you want
- Verify the application generating events is running
