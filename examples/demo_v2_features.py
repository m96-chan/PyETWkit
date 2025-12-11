"""Demo script for PyETWkit v2.0.0 features.

This demonstrates:
- MultiSession: Multiple ETW sessions in parallel
- ManifestParser: Parse provider manifests for typed events
- RustEventFilter: High-performance Rust-side filtering
"""

from __future__ import annotations

print("=" * 60)
print("PyETWkit v2.0.0 Feature Demo")
print("=" * 60)

# 1. MultiSession
print("\n1. MultiSession - Multiple ETW sessions in parallel")
print("-" * 50)

from pyetwkit import MultiSession

multi = MultiSession()
print(f"Created MultiSession: {multi}")
print("Available methods:")
print("  - add_session(name, providers) -> Add a named session")
print("  - start_all() -> Start all sessions")
print("  - stop_all() -> Stop all sessions")
print("  - remove_session(name) -> Remove a session")
print("  - events() -> Iterate events from all sessions")

# 2. ManifestParser
print("\n2. ManifestParser - Parse ETW provider manifests")
print("-" * 50)

from pyetwkit import ManifestCache, ManifestParser

parser = ManifestParser()
cache = ManifestCache()

print(f"ManifestParser: {parser}")
print(f"ManifestCache: {cache}")
print("Features:")
print("  - Parse provider manifest XML files")
print("  - Extract event definitions with field types")
print("  - Cache parsed manifests for performance")
print("  - Auto-generate typed event classes")

# 3. RustEventFilter
print("\n3. RustEventFilter - High-performance Rust-side filtering")
print("-" * 50)

from pyetwkit import RustEventFilter

# Build a complex filter
rust_filter = (
    RustEventFilter()
    .event_ids([1, 2, 3, 10, 11])
    .exclude_event_ids([999])
    .level_max(4)  # Info level and below (0=Critical to 4=Info)
    .pid(1234)
)

print(f"RustEventFilter: {rust_filter}")
print("Filter configuration:")
print("  - event_ids: [1, 2, 3, 10, 11]")
print("  - exclude_event_ids: [999]")
print("  - level_max: 4 (Info and below)")
print("  - pid: 1234")
print("\nAdvantage: Filters are evaluated in Rust before")
print("reaching Python, providing maximum performance!")

# 4. Property Filtering
print("\n4. Property Filtering - Filter by event properties")
print("-" * 50)

property_filter = (
    RustEventFilter()
    .property_equals("ProcessName", "notepad.exe")
    .property_contains("CommandLine", "secret")
)

print("Property filter examples:")
print('  - property_equals("ProcessName", "notepad.exe")')
print('  - property_contains("CommandLine", "secret")')
print('  - property_regex("FileName", r".*\\.exe$")')
print('  - property_gt("Size", 1024)')
print('  - property_lt("Duration", 100)')

# 5. Filter Combinations
print("\n5. Filter Combinations - AND/OR/NOT logic")
print("-" * 50)

filter_a = RustEventFilter().event_ids([1, 2])
filter_b = RustEventFilter().pid(1234)

# Combined filters using Python operators
combined_and = filter_a & filter_b  # AND
combined_or = filter_a | filter_b  # OR
combined_not = ~filter_a  # NOT

print("Filter combination with Python operators:")
print("  - filter_a & filter_b -> Both must match (AND)")
print("  - filter_a | filter_b -> Either can match (OR)")
print("  - ~filter_a -> Inverts the filter (NOT)")

print("\n" + "=" * 60)
print("v2.0.0 Demo Complete!")
print("=" * 60)
