"""Tests for ETL file reading functionality (v0.2.0 - #25)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


def check_extension_available() -> bool:
    """Check if the native extension is available.

    maturin builds the extension as ``pyetwkit._core`` (see ``module-name`` in
    pyproject.toml), never as a top-level ``pyetwkit_core``. Probing for the
    latter therefore always failed, which silently skipped this entire module.
    """
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


class TestEtlReader:
    """Tests for EtlReader class."""

    def test_etl_reader_exists(self) -> None:
        """Test that EtlReader class exists."""
        from pyetwkit import _core as pyetwkit_core

        assert hasattr(pyetwkit_core, "EtlReader")

    def test_etl_reader_file_not_found(self) -> None:
        """Test that opening non-existent file raises error."""
        from pyetwkit import _core as pyetwkit_core

        with pytest.raises((FileNotFoundError, OSError, RuntimeError)):
            pyetwkit_core.EtlReader("nonexistent_file.etl")

    def test_etl_reader_invalid_file(self) -> None:
        """Test that opening invalid file may not raise immediately.

        Note: The EtlReader constructor only checks file existence.
        Invalid file format is detected when starting to process events.
        This test verifies that behavior.
        """
        from pyetwkit import _core as pyetwkit_core

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
        from pyetwkit import _core as pyetwkit_core

        # This test verifies the interface exists
        # Actual file reading requires a valid ETL file
        assert hasattr(pyetwkit_core.EtlReader, "__enter__")
        assert hasattr(pyetwkit_core.EtlReader, "__exit__")

    def test_etl_reader_is_iterable(self) -> None:
        """Test that EtlReader is iterable."""
        from pyetwkit import _core as pyetwkit_core

        assert hasattr(pyetwkit_core.EtlReader, "__iter__")


def get_sample_etl_path() -> Path | None:
    """Get path to sample ETL file if available."""
    # Check common locations for ETL files
    possible_paths = [
        Path(__file__).parent / "fixtures" / "sample.etl",
        Path("tests/fixtures/sample.etl"),
        Path("test_data/sample.etl"),
    ]
    for path in possible_paths:
        if path.exists():
            return path
    return None


SAMPLE_ETL_PATH = get_sample_etl_path()


class TestEtlReaderWithFile:
    """Tests for EtlReader with actual ETL files.

    These tests are skipped if no test ETL file is available.
    """

    @pytest.fixture
    def sample_etl_path(self) -> Path | None:
        """Get path to sample ETL file if available."""
        return SAMPLE_ETL_PATH

    @pytest.mark.skipif(SAMPLE_ETL_PATH is None, reason="Requires sample ETL file")
    def test_etl_reader_read_events(self, sample_etl_path: Path | None) -> None:
        """Test reading events from ETL file."""
        if sample_etl_path is None:
            pytest.skip("No sample ETL file available")

        from pyetwkit import _core as pyetwkit_core

        with pyetwkit_core.EtlReader(str(sample_etl_path)) as reader:
            events = list(reader)
            # ETL file may have events or may be empty depending on system state
            assert isinstance(events, list)

    @pytest.mark.skipif(SAMPLE_ETL_PATH is None, reason="Requires sample ETL file")
    def test_etl_reader_event_properties(self, sample_etl_path: Path | None) -> None:
        """Test that events have expected properties."""
        if sample_etl_path is None:
            pytest.skip("No sample ETL file available")

        from pyetwkit import _core as pyetwkit_core

        with pyetwkit_core.EtlReader(str(sample_etl_path)) as reader:
            events = list(reader)
            if events:
                event = events[0]
                assert hasattr(event, "event_id")
                assert hasattr(event, "provider_id")
                assert hasattr(event, "timestamp")


# Properties that the old hardcoded parser in session.rs used to guess at, before
# properties were enumerated from the event schema via TDH. Any name outside this
# set proves the parser is no longer limited to the guess list.
LEGACY_GUESSED_PROPERTIES = frozenset(
    {
        "ProcessId",
        "ThreadId",
        "ImageFileName",
        "ProcessName",
        "CommandLine",
        "FileName",
        "FilePath",
        "Message",
        "Data",
        "Status",
        "Result",
        "ErrorCode",
    }
)


class TestGenericPropertyParsing:
    """Regression tests for schema-driven property parsing.

    Reading an ETL file needs no administrator rights, so unlike the live-capture
    tests these run everywhere, which is what makes them a usable guard.
    """

    @pytest.mark.skipif(SAMPLE_ETL_PATH is None, reason="Requires sample ETL file")
    def test_properties_are_not_limited_to_the_legacy_guess_list(self) -> None:
        """Events should expose whatever their schema declares."""
        from pyetwkit import _core as pyetwkit_core

        assert SAMPLE_ETL_PATH is not None
        with pyetwkit_core.EtlReader(str(SAMPLE_ETL_PATH)) as reader:
            events = list(reader)

        if not events:
            pytest.skip("Sample ETL file contained no events")

        seen: set[str] = set()
        for event in events:
            seen.update(event.properties.keys())

        if not seen:
            # Every event in the fixture lacked a resolvable TDH schema, which
            # happens for WPP and for providers with no manifest installed.
            # Skipping keeps this from failing for an environmental reason, but
            # it does mean the assertion below went unexercised.
            pytest.skip("No event in the sample ETL had a resolvable schema")

        assert not seen.issubset(LEGACY_GUESSED_PROPERTIES), (
            "Only legacy guessed property names were found, so properties are "
            f"probably still not schema-driven. Saw: {sorted(seen)}"
        )

    @pytest.mark.skipif(SAMPLE_ETL_PATH is None, reason="Requires sample ETL file")
    def test_properties_round_trip_into_to_dict(self) -> None:
        """Whatever properties() reports must survive into to_dict()."""
        from pyetwkit import _core as pyetwkit_core

        assert SAMPLE_ETL_PATH is not None
        with pyetwkit_core.EtlReader(str(SAMPLE_ETL_PATH)) as reader:
            events = list(reader)

        if not events:
            pytest.skip("Sample ETL file contained no events")

        for event in events:
            props = event.properties
            assert props == event.to_dict()["properties"]

    @pytest.mark.skipif(SAMPLE_ETL_PATH is None, reason="Requires sample ETL file")
    def test_property_values_are_python_native_types(self) -> None:
        """Parsed values must be usable from Python, not opaque handles."""
        from pyetwkit import _core as pyetwkit_core

        assert SAMPLE_ETL_PATH is not None
        with pyetwkit_core.EtlReader(str(SAMPLE_ETL_PATH)) as reader:
            events = list(reader)

        if not events:
            pytest.skip("Sample ETL file contained no events")

        allowed = (bool, int, float, str, bytes, list, dict, type(None))
        for event in events:
            for name, value in event.properties.items():
                assert isinstance(value, allowed), f"{name} produced {type(value)!r}"
