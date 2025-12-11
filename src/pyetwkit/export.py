"""Data export functionality for ETW events.

This module provides functions to export ETW events to various formats:
- Pandas DataFrame
- CSV files
- JSON/JSONL files
- Apache Parquet files
- Apache Arrow format
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

# Type alias for events
EventLike = Any  # EtwEvent or dict


def _event_to_dict(event: EventLike) -> dict[str, Any]:
    """Convert an event to dictionary format."""
    if hasattr(event, "to_dict"):
        return event.to_dict()
    if isinstance(event, dict):
        return event
    raise TypeError(f"Cannot convert {type(event)} to dict")


def _flatten_event(event_dict: dict[str, Any]) -> dict[str, Any]:
    """Flatten nested properties into the main dict."""
    result = {}
    for key, value in event_dict.items():
        if key == "properties" and isinstance(value, dict):
            for prop_key, prop_value in value.items():
                result[f"prop_{prop_key}"] = prop_value
        else:
            result[key] = value
    return result


def to_dataframe(
    events: Sequence[EventLike],
    flatten: bool = True,
) -> Any:
    """Convert events to a Pandas DataFrame.

    Args:
        events: Sequence of EtwEvent objects or dicts
        flatten: If True, flatten nested properties into columns

    Returns:
        pandas.DataFrame containing the events

    Example:
        >>> from pyetwkit.export import to_dataframe
        >>> df = to_dataframe(events)
        >>> df.to_csv("events.csv")
    """
    try:
        import pandas as pd
    except ImportError as e:
        raise ImportError(
            "pandas is required for DataFrame export. Install it with: pip install pandas"
        ) from e

    if not events:
        return pd.DataFrame()

    rows = []
    for event in events:
        event_dict = _event_to_dict(event)
        if flatten:
            event_dict = _flatten_event(event_dict)
        rows.append(event_dict)

    return pd.DataFrame(rows)


def to_csv(
    events: Sequence[EventLike],
    path: str | Path,
    flatten: bool = True,
    **kwargs: Any,
) -> None:
    """Export events to a CSV file.

    Args:
        events: Sequence of EtwEvent objects or dicts
        path: Output file path
        flatten: If True, flatten nested properties into columns
        **kwargs: Additional arguments passed to pandas.DataFrame.to_csv()

    Example:
        >>> from pyetwkit.export import to_csv
        >>> to_csv(events, "events.csv")
    """
    df = to_dataframe(events, flatten=flatten)
    df.to_csv(path, index=False, **kwargs)


def to_json(
    events: Sequence[EventLike],
    path: str | Path | None = None,
    indent: int | None = None,
) -> str | None:
    """Export events to JSON format.

    Args:
        events: Sequence of EtwEvent objects or dicts
        path: Output file path (if None, returns string)
        indent: JSON indentation (None for compact)

    Returns:
        JSON string if path is None, otherwise None

    Example:
        >>> from pyetwkit.export import to_json
        >>> json_str = to_json(events)
        >>> to_json(events, "events.json")
    """
    data = [_event_to_dict(e) for e in events]
    json_str = json.dumps(data, indent=indent, default=str)

    if path is not None:
        Path(path).write_text(json_str, encoding="utf-8")
        return None
    return json_str


def to_jsonl(
    events: Sequence[EventLike] | Iterator[EventLike],
    path: str | Path,
) -> None:
    """Export events to JSON Lines format (one JSON object per line).

    This is more memory-efficient for large datasets as it can stream events.

    Args:
        events: Sequence or iterator of EtwEvent objects or dicts
        path: Output file path

    Example:
        >>> from pyetwkit.export import to_jsonl
        >>> to_jsonl(events, "events.jsonl")
    """
    with open(path, "w", encoding="utf-8") as f:
        for event in events:
            event_dict = _event_to_dict(event)
            f.write(json.dumps(event_dict, default=str))
            f.write("\n")


def to_parquet(
    events: Sequence[EventLike],
    path: str | Path,
    flatten: bool = True,
    **kwargs: Any,
) -> None:
    """Export events to Apache Parquet format.

    Args:
        events: Sequence of EtwEvent objects or dicts
        path: Output file path
        flatten: If True, flatten nested properties into columns
        **kwargs: Additional arguments passed to pandas.DataFrame.to_parquet()

    Example:
        >>> from pyetwkit.export import to_parquet
        >>> to_parquet(events, "events.parquet")
    """
    try:
        import pyarrow  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "pyarrow is required for Parquet export. Install it with: pip install pyarrow"
        ) from e

    df = to_dataframe(events, flatten=flatten)
    df.to_parquet(path, index=False, **kwargs)


def to_arrow(
    events: Sequence[EventLike],
    flatten: bool = True,
) -> Any:
    """Convert events to Apache Arrow Table format.

    Args:
        events: Sequence of EtwEvent objects or dicts
        flatten: If True, flatten nested properties into columns

    Returns:
        pyarrow.Table containing the events

    Example:
        >>> from pyetwkit.export import to_arrow
        >>> table = to_arrow(events)
        >>> table.to_pandas()  # Convert to pandas if needed
    """
    try:
        import pyarrow as pa
    except ImportError as e:
        raise ImportError(
            "pyarrow is required for Arrow export. Install it with: pip install pyarrow"
        ) from e

    df = to_dataframe(events, flatten=flatten)
    return pa.Table.from_pandas(df)


__all__ = [
    "to_dataframe",
    "to_csv",
    "to_json",
    "to_jsonl",
    "to_parquet",
    "to_arrow",
]
