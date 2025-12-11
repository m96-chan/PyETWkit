# PyETWkit Examples

This directory contains example scripts demonstrating how to use PyETWkit.

## Prerequisites

- Windows 10 or later
- Administrator privileges (for ETW sessions)
- PyETWkit installed: `pip install pyetwkit`

## Examples

### basic_session.py

Basic ETW session example showing how to monitor DNS client events.

```bash
# Run as administrator
python basic_session.py
```

### kernel_trace.py

Kernel-level tracing for process events (start/stop).

```bash
# Run as administrator
python kernel_trace.py
```

### provider_discovery.py

Discover and search for ETW providers on the system. No admin required.

```bash
python provider_discovery.py
```

### profiles.py

Use pre-configured provider profiles for common monitoring scenarios.

```bash
# Run as administrator
python profiles.py
```

### export_events.py

Capture events and export to CSV, JSON, and JSONL formats.

```bash
# Run as administrator
python export_events.py
```

### read_etl.py

Read events from an existing ETL file.

```bash
# First, create an ETL file
logman start mytrace -p Microsoft-Windows-DNS-Client -o trace.etl -ets
ping example.com
logman stop mytrace -ets

# Then read it
python read_etl.py trace.etl
```

## CLI Examples

PyETWkit also provides a command-line interface:

```bash
# List providers
pyetwkit providers
pyetwkit providers --search Kernel

# List profiles
pyetwkit profiles

# Listen to events
pyetwkit listen Microsoft-Windows-DNS-Client
pyetwkit listen --profile network

# Export ETL file
pyetwkit export trace.etl -o events.csv
pyetwkit export trace.etl -o events.parquet -f parquet
```
