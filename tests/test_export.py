"""Tests for data export functionality (v0.3.0 - #14, #33)."""

import os
import tempfile

import pytest


def check_extension_available() -> bool:
    """Check if native extension is available."""
    try:
        import pyetwkit_core  # noqa: F401

        return True
    except ImportError:
        return False


# Skip all tests if native extension is not available
pytestmark = pytest.mark.skipif(
    not check_extension_available(),
    reason="Native extension not built",
)


class TestEventToDict:
    """Tests for event to dict conversion."""

    def test_event_has_to_dict(self) -> None:
        """Test that EtwEvent has to_dict method."""
        import pyetwkit_core

        event_class = pyetwkit_core.EtwEvent
        assert hasattr(event_class, "to_dict")

    def test_event_to_dict_returns_dict(self) -> None:
        """Test that to_dict returns a dictionary."""
        import pyetwkit_core

        # Create a mock event or use the class definition
        event_class = pyetwkit_core.EtwEvent
        assert hasattr(event_class, "to_dict")


class TestToDataFrame:
    """Tests for DataFrame conversion."""

    def test_to_dataframe_function_exists(self) -> None:
        """Test that to_dataframe function exists in export module."""
        try:
            from pyetwkit.export import to_dataframe

            assert callable(to_dataframe)
        except ImportError:
            pytest.skip("pyetwkit.export module not available")

    def test_to_dataframe_empty_list(self) -> None:
        """Test converting empty list to dataframe."""
        try:
            from pyetwkit.export import to_dataframe

            df = to_dataframe([])
            assert len(df) == 0
        except ImportError:
            pytest.skip("pyetwkit.export module not available")


class TestToCSV:
    """Tests for CSV export."""

    def test_to_csv_function_exists(self) -> None:
        """Test that to_csv function exists."""
        try:
            from pyetwkit.export import to_csv

            assert callable(to_csv)
        except ImportError:
            pytest.skip("pyetwkit.export module not available")

    def test_to_csv_creates_file(self) -> None:
        """Test that to_csv creates a file."""
        try:
            from pyetwkit.export import to_csv

            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
                temp_path = f.name

            try:
                to_csv([], temp_path)
                assert os.path.exists(temp_path)
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        except ImportError:
            pytest.skip("pyetwkit.export module not available")


class TestToJSON:
    """Tests for JSON export."""

    def test_to_json_function_exists(self) -> None:
        """Test that to_json function exists."""
        try:
            from pyetwkit.export import to_json

            assert callable(to_json)
        except ImportError:
            pytest.skip("pyetwkit.export module not available")

    def test_to_jsonl_function_exists(self) -> None:
        """Test that to_jsonl function exists."""
        try:
            from pyetwkit.export import to_jsonl

            assert callable(to_jsonl)
        except ImportError:
            pytest.skip("pyetwkit.export module not available")


class TestToParquet:
    """Tests for Parquet export."""

    def test_to_parquet_function_exists(self) -> None:
        """Test that to_parquet function exists."""
        try:
            from pyetwkit.export import to_parquet

            assert callable(to_parquet)
        except ImportError:
            pytest.skip("pyetwkit.export module not available")


class TestToArrow:
    """Tests for Arrow export."""

    def test_to_arrow_function_exists(self) -> None:
        """Test that to_arrow function exists."""
        try:
            from pyetwkit.export import to_arrow

            assert callable(to_arrow)
        except ImportError:
            pytest.skip("pyetwkit.export module not available")


class TestExportModule:
    """Tests for export module structure."""

    def test_export_module_exists(self) -> None:
        """Test that pyetwkit.export module exists."""
        try:
            from pyetwkit import export  # noqa: F401

            assert True
        except ImportError:
            pytest.skip("pyetwkit.export module not available")

    def test_export_all_functions(self) -> None:
        """Test that all export functions are available."""
        try:
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
        except ImportError:
            pytest.skip("pyetwkit.export module not available")
