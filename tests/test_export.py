"""Tests for data export functionality (v0.3.0 - #14, #33)."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
from pathlib import Path

import pytest


def check_extension_available() -> bool:
    """Check if native extension is available."""
    try:
        from pyetwkit import _core  # noqa: F401

        return True
    except ImportError:
        return False


# Skip all tests if native extension is not available
pytestmark = pytest.mark.skipif(
    not check_extension_available(),
    reason="Native extension not built",
)


def _installed(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


# The exporters keep pandas and pyarrow optional, importing them inside the
# functions that need them, so `pyetwkit.export` itself always imports. Deciding
# up front which optional dependency is present is what lets everything else
# assert rather than skip: wrapping a call in `except ImportError: skip` would
# also swallow a genuine ImportError raised inside the module and report a
# broken exporter as a missing extra.
requires_pandas = pytest.mark.skipif(
    not _installed("pandas"), reason="pandas is not installed (pip install pyetwkit[export])"
)
requires_pyarrow = pytest.mark.skipif(
    not _installed("pyarrow"), reason="pyarrow is not installed (pip install pyetwkit[export])"
)

SAMPLE_EVENTS = [
    {
        "provider_name": "Microsoft-Windows-DNS-Client",
        "event_id": 3020,
        "process_id": 4104,
        "properties": {"QueryName": "example.com", "QueryType": 1},
    },
    {
        "provider_name": "Microsoft-Windows-DNS-Client",
        "event_id": 3006,
        "process_id": 4104,
        "properties": {"QueryName": "github.com", "QueryType": 28},
    },
]


class TestEventToDict:
    """Tests for event to dict conversion."""

    def test_event_has_to_dict(self) -> None:
        """Test that EtwEvent has to_dict method."""
        from pyetwkit import _core as pyetwkit_core

        event_class = pyetwkit_core.EtwEvent
        assert hasattr(event_class, "to_dict")

    def test_event_to_dict_returns_dict(self) -> None:
        """Test that to_dict returns a dictionary."""
        from pyetwkit import _core as pyetwkit_core

        # Create a mock event or use the class definition
        event_class = pyetwkit_core.EtwEvent
        assert hasattr(event_class, "to_dict")


class TestExportModule:
    """Tests for export module structure."""

    def test_export_module_exists(self) -> None:
        """The module must import with no optional dependency present."""
        from pyetwkit import export  # noqa: F401

    def test_export_all_functions(self) -> None:
        """Test that all export functions are available."""
        from pyetwkit.export import (
            to_arrow,
            to_csv,
            to_dataframe,
            to_json,
            to_jsonl,
            to_parquet,
        )

        assert all(
            callable(f) for f in [to_dataframe, to_csv, to_json, to_jsonl, to_parquet, to_arrow]
        )


class TestToJSON:
    """JSON export needs no optional dependency."""

    def test_to_json_function_exists(self) -> None:
        from pyetwkit.export import to_json

        assert callable(to_json)

    def test_to_jsonl_function_exists(self) -> None:
        from pyetwkit.export import to_jsonl

        assert callable(to_jsonl)

    def test_to_json_round_trips(self) -> None:
        from pyetwkit.export import to_json

        text = to_json(SAMPLE_EVENTS)
        assert text is not None
        assert [e["event_id"] for e in json.loads(text)] == [3020, 3006]

    def test_to_jsonl_writes_one_object_per_line(self, tmp_path: Path) -> None:
        from pyetwkit.export import to_jsonl

        path = tmp_path / "events.jsonl"
        to_jsonl(SAMPLE_EVENTS, path)
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["event_id"] == 3020


class TestToDataFrame:
    """Tests for DataFrame conversion."""

    def test_to_dataframe_function_exists(self) -> None:
        """Available whether or not pandas is: the import is done lazily."""
        from pyetwkit.export import to_dataframe

        assert callable(to_dataframe)

    @requires_pandas
    def test_to_dataframe_empty_list(self) -> None:
        """Test converting empty list to dataframe."""
        from pyetwkit.export import to_dataframe

        df = to_dataframe([])
        assert len(df) == 0

    @requires_pandas
    def test_to_dataframe_carries_the_events(self) -> None:
        from pyetwkit.export import to_dataframe

        df = to_dataframe(SAMPLE_EVENTS)
        assert len(df) == 2
        assert list(df["event_id"]) == [3020, 3006]


class TestToCSV:
    """CSV export goes through pandas."""

    def test_to_csv_function_exists(self) -> None:
        from pyetwkit.export import to_csv

        assert callable(to_csv)

    @requires_pandas
    def test_to_csv_creates_file(self) -> None:
        """Test that to_csv creates a file."""
        from pyetwkit.export import to_csv

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            temp_path = f.name

        try:
            to_csv([], temp_path)
            assert os.path.exists(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @requires_pandas
    def test_to_csv_writes_the_events(self, tmp_path: Path) -> None:
        from pyetwkit.export import to_csv

        path = tmp_path / "events.csv"
        to_csv(SAMPLE_EVENTS, path)
        text = path.read_text(encoding="utf-8")
        assert "event_id" in text
        assert "3020" in text


class TestToParquet:
    """Parquet export needs pyarrow."""

    def test_to_parquet_function_exists(self) -> None:
        from pyetwkit.export import to_parquet

        assert callable(to_parquet)

    @requires_pandas
    @requires_pyarrow
    def test_to_parquet_round_trips(self, tmp_path: Path) -> None:
        import pandas as pd

        from pyetwkit.export import to_parquet

        path = tmp_path / "events.parquet"
        to_parquet(SAMPLE_EVENTS, path)
        assert path.exists()
        assert list(pd.read_parquet(path)["event_id"]) == [3020, 3006]


class TestToArrow:
    """Arrow export needs pyarrow."""

    def test_to_arrow_function_exists(self) -> None:
        from pyetwkit.export import to_arrow

        assert callable(to_arrow)

    @requires_pandas
    @requires_pyarrow
    def test_to_arrow_returns_a_table_of_the_events(self) -> None:
        from pyetwkit.export import to_arrow

        table = to_arrow(SAMPLE_EVENTS)
        assert table.num_rows == 2
        assert table.column("event_id").to_pylist() == [3020, 3006]
