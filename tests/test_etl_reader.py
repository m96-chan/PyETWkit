"""Tests for ETL file reading functionality (v0.2.0 - #25)."""

import os
import tempfile
from pathlib import Path

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


class TestEtlReader:
    """Tests for EtlReader class."""

    def test_etl_reader_exists(self) -> None:
        """Test that EtlReader class exists."""
        import pyetwkit_core

        assert hasattr(pyetwkit_core, "EtlReader")

    def test_etl_reader_file_not_found(self) -> None:
        """Test that opening non-existent file raises error."""
        import pyetwkit_core

        with pytest.raises((FileNotFoundError, OSError, RuntimeError)):
            pyetwkit_core.EtlReader("nonexistent_file.etl")

    def test_etl_reader_invalid_file(self) -> None:
        """Test that opening invalid file may not raise immediately.

        Note: The EtlReader constructor only checks file existence.
        Invalid file format is detected when starting to process events.
        This test verifies that behavior.
        """
        import pyetwkit_core

        # Create a temporary file with invalid content
        with tempfile.NamedTemporaryFile(suffix=".etl", delete=False) as f:
            f.write(b"not a valid etl file")
            temp_path = f.name

        try:
            # EtlReader accepts existing files - validation happens during processing
            reader = pyetwkit_core.EtlReader(temp_path)
            # The reader is created successfully but will fail/return no events when read
            assert reader.path == temp_path
        finally:
            os.unlink(temp_path)

    def test_etl_reader_is_context_manager(self) -> None:
        """Test that EtlReader can be used as context manager."""
        import pyetwkit_core

        # This test verifies the interface exists
        # Actual file reading requires a valid ETL file
        assert hasattr(pyetwkit_core.EtlReader, "__enter__")
        assert hasattr(pyetwkit_core.EtlReader, "__exit__")

    def test_etl_reader_is_iterable(self) -> None:
        """Test that EtlReader is iterable."""
        import pyetwkit_core

        assert hasattr(pyetwkit_core.EtlReader, "__iter__")


class TestEtlReaderWithFile:
    """Tests for EtlReader with actual ETL files.

    These tests are skipped if no test ETL file is available.
    """

    @pytest.fixture
    def sample_etl_path(self) -> Path | None:
        """Get path to sample ETL file if available."""
        # Check common locations for ETL files
        possible_paths = [
            Path("tests/fixtures/sample.etl"),
            Path("test_data/sample.etl"),
            # Windows default trace location
            Path(os.environ.get("LOCALAPPDATA", "")) / "Temp" / "test.etl",
        ]
        for path in possible_paths:
            if path.exists():
                return path
        return None

    @pytest.mark.skip(reason="Requires sample ETL file")
    def test_etl_reader_read_events(self, sample_etl_path: Path | None) -> None:
        """Test reading events from ETL file."""
        if sample_etl_path is None:
            pytest.skip("No sample ETL file available")

        import pyetwkit_core

        with pyetwkit_core.EtlReader(str(sample_etl_path)) as reader:
            events = list(reader)
            assert len(events) > 0

    @pytest.mark.skip(reason="Requires sample ETL file")
    def test_etl_reader_event_properties(self, sample_etl_path: Path | None) -> None:
        """Test that events have expected properties."""
        if sample_etl_path is None:
            pytest.skip("No sample ETL file available")

        import pyetwkit_core

        with pyetwkit_core.EtlReader(str(sample_etl_path)) as reader:
            for event in reader:
                assert hasattr(event, "event_id")
                assert hasattr(event, "provider_id")
                assert hasattr(event, "timestamp")
                break  # Only check first event
