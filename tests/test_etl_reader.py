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


NESTED_STRUCT_ETL_PATH = Path(__file__).parent / "fixtures" / "nested_struct.etl"


class TestNestedStructProperties:
    """Regression tests for properties whose type is a nested structure.

    ``sample.etl`` cannot cover these: Microsoft-Windows-Kernel-Process declares
    no struct-typed property. ``nested_struct.etl`` holds events from a
    TraceLogging provider defined by ``fixtures/create_nested_struct_etl.ps1``,
    each carrying two ``{ Number, Affinity }`` structs.

    TraceLogging matters here rather than being an implementation detail: such
    events embed their schema, so the fixture decodes identically anywhere. A
    capture from a manifest provider does not -- decoding needs that manifest
    installed and of a matching version, so an earlier version of this fixture,
    taken from Kernel-Processor-Power, decoded on the machine that recorded it
    and produced nothing at all in CI on a different Windows build.
    """

    @pytest.mark.skipif(
        not NESTED_STRUCT_ETL_PATH.exists(), reason="Requires nested-struct ETL file"
    )
    def test_struct_properties_are_dicts_of_their_members(self) -> None:
        """A struct property must expose its members, not vanish."""
        from pyetwkit import _core as pyetwkit_core

        events = pyetwkit_core.EtlReader(str(NESTED_STRUCT_ETL_PATH)).read_all()
        assert events, "fixture produced no events"

        structs = {
            name: value
            for event in events
            for name, value in event.properties.items()
            if isinstance(value, dict)
        }
        assert structs, (
            "no struct-valued property was decoded; before nested structures "
            "were supported these were skipped outright"
        )

        # Both structs in the fixture are a { Number, Affinity } pair.
        assert "Park" in structs, sorted(structs)
        assert set(structs["Park"]) == {"Number", "Affinity"}
        assert structs["Park"] == {"Number": 7, "Affinity": 0x50C0}
        assert structs["Unpark"] == {"Number": 9, "Affinity": 0x000F}

    @pytest.mark.skipif(
        not NESTED_STRUCT_ETL_PATH.exists(), reason="Requires nested-struct ETL file"
    )
    def test_counted_string_has_no_length_prefix_in_its_value(self) -> None:
        """TDH returns the count as part of the value; it is not content.

        The fixture's ``Label`` is a counted string, which decoded as
        ``'\\x14core-state'`` -- the ``\\x14`` being its own 20-byte length.
        """
        from pyetwkit import _core as pyetwkit_core

        events = pyetwkit_core.EtlReader(str(NESTED_STRUCT_ETL_PATH)).read_all()
        labels = {e.properties["Label"] for e in events if "Label" in e.properties}
        assert labels, "fixture no longer carries a Label property"
        assert labels == {"core-state"}

    @pytest.mark.skipif(
        not NESTED_STRUCT_ETL_PATH.exists(), reason="Requires nested-struct ETL file"
    )
    def test_struct_members_do_not_leak_into_the_top_level(self) -> None:
        """Members belong to their struct, not beside it.

        The layout vector holds struct members too, so that the schema's own
        indices stay usable; only the top-level properties may become keys.
        """
        from pyetwkit import _core as pyetwkit_core

        events = pyetwkit_core.EtlReader(str(NESTED_STRUCT_ETL_PATH)).read_all()
        assert events, "fixture produced no events"

        for event in events:
            props = event.properties
            if "Park" not in props:
                continue
            assert "Affinity" not in props
            assert "Number" not in props
            return
        pytest.fail("no event carried a Park struct")

    @pytest.mark.skipif(
        not NESTED_STRUCT_ETL_PATH.exists(), reason="Requires nested-struct ETL file"
    )
    def test_struct_values_survive_into_to_dict(self) -> None:
        """Structs must round-trip like every other value."""
        from pyetwkit import _core as pyetwkit_core

        events = pyetwkit_core.EtlReader(str(NESTED_STRUCT_ETL_PATH)).read_all()
        assert events, "fixture produced no events"

        for event in events:
            assert event.properties == event.to_dict()["properties"]

    @pytest.mark.skipif(
        not NESTED_STRUCT_ETL_PATH.exists(), reason="Requires nested-struct ETL file"
    )
    def test_nested_values_are_python_native_types(self) -> None:
        """Members must be usable from Python, recursively."""
        from pyetwkit import _core as pyetwkit_core

        allowed = (bool, int, float, str, bytes, list, dict, type(None))
        events = pyetwkit_core.EtlReader(str(NESTED_STRUCT_ETL_PATH)).read_all()
        assert events, "fixture produced no events"

        for event in events:
            for name, value in event.properties.items():
                assert isinstance(value, allowed), f"{name} produced {type(value)!r}"
                if isinstance(value, dict):
                    for member, inner in value.items():
                        assert isinstance(
                            inner, allowed
                        ), f"{name}.{member} produced {type(inner)!r}"


NO_SCHEMA_ETL_PATH = Path(__file__).parent / "fixtures" / "no_schema.etl"

requires_no_schema_etl = pytest.mark.skipif(
    not NO_SCHEMA_ETL_PATH.exists(), reason="Requires schema-less ETL file"
)


class TestEventsWithoutASchema:
    """Events TDH cannot describe must not lose their payload.

    WPP without a matching TMF, and manifest providers whose manifest is not
    installed here, have no property names to report a value under. Before the
    fallback the payload was simply dropped. ``no_schema.etl`` is a capture where
    roughly half the events are of that kind.
    """

    @requires_no_schema_etl
    def test_undecodable_events_keep_their_payload(self) -> None:
        from pyetwkit import _core as pyetwkit_core

        events = pyetwkit_core.EtlReader(str(NO_SCHEMA_ETL_PATH)).read_all()
        assert events, "fixture produced no events"

        undecoded = [e for e in events if not e.properties]
        assert undecoded, "fixture no longer contains schema-less events"

        with_raw = [e for e in undecoded if e.raw_data is not None]
        assert with_raw, "schema-less events came back with no payload at all"
        assert all(isinstance(e.raw_data, bytes) for e in with_raw)
        assert all(len(e.raw_data) > 0 for e in with_raw)

    @requires_no_schema_etl
    def test_decoded_events_do_not_also_carry_raw_data(self) -> None:
        """The fallback is a fallback, not a second copy of every event."""
        from pyetwkit import _core as pyetwkit_core

        events = pyetwkit_core.EtlReader(str(NO_SCHEMA_ETL_PATH)).read_all()
        decoded = [e for e in events if e.properties]
        assert decoded, "fixture no longer contains decodable events"
        assert all(e.raw_data is None for e in decoded)


class TestPropertyFormatting:
    """TDH's own display strings, offered alongside the typed values."""

    def test_formatting_is_off_by_default(self) -> None:
        from pyetwkit import _core as pyetwkit_core

        assert pyetwkit_core.property_formatting() is False

    @pytest.mark.skipif(
        not NESTED_STRUCT_ETL_PATH.exists(), reason="Requires nested-struct ETL file"
    )
    def test_formatted_properties_appear_only_when_enabled(self) -> None:
        from pyetwkit import _core as pyetwkit_core

        path = str(NESTED_STRUCT_ETL_PATH)

        off = pyetwkit_core.EtlReader(path).read_all()
        assert off, "fixture produced no events"
        assert all(not e.formatted_properties for e in off)

        pyetwkit_core.set_property_formatting(True)
        try:
            on = pyetwkit_core.EtlReader(path).read_all()
            assert any(e.formatted_properties for e in on)
            for event in on:
                for name, text in event.formatted_properties.items():
                    assert isinstance(name, str)
                    assert isinstance(text, str)
            # Typed values must be unaffected by the string view.
            assert [e.properties for e in on] == [e.properties for e in off]
        finally:
            pyetwkit_core.set_property_formatting(False)

        assert pyetwkit_core.property_formatting() is False


WPP_ETL_PATH = Path(__file__).parent / "fixtures" / "wpp.etl"
WPP_TMF_DIR = Path(__file__).parent / "fixtures" / "wpp_tmf"

requires_wpp_etl = pytest.mark.skipif(
    not WPP_ETL_PATH.exists() or not WPP_TMF_DIR.is_dir(),
    reason="Requires the WPP ETL fixture and its TMF",
)

# What tracefmt, Microsoft's own formatter, makes of the same capture given the
# same TMF directory. Anything else is wrong.
WPP_EXPECTED = [
    "wpp probe seq=0 name=core-state value=0x50c0",
    "wpp probe seq=1 name=core-state value=0x50c1",
    "wpp probe seq=2 name=core-state value=0x50c2",
]


def _clear_wpp_sources() -> None:
    from pyetwkit import _core as pyetwkit_core

    pyetwkit_core.set_wpp_tmf_search_path(None)
    pyetwkit_core.set_wpp_tmf_file(None)
    pyetwkit_core.set_wpp_pdb_path(None)


def _wpp_messages() -> list[str]:
    from pyetwkit import _core as pyetwkit_core

    return [
        e.properties["FormattedString"]
        for e in pyetwkit_core.EtlReader(str(WPP_ETL_PATH)).read_all()
        if "FormattedString" in e.properties
    ]


class TestWppDecoding:
    """WPP events decode only when format information is supplied.

    They carry no schema of their own: the format strings live in a ``.tmf``
    generated from the emitting binary's PDB (see
    ``fixtures/create_wpp_etl.ps1``). Without one TDH only ever says "No Format
    Information found", which is exactly what the first test pins down.
    """

    def teardown_method(self) -> None:
        _clear_wpp_sources()

    @requires_wpp_etl
    def test_without_format_information_the_message_is_a_placeholder(self) -> None:
        _clear_wpp_sources()
        messages = _wpp_messages()
        assert messages, "fixture carried no WPP events"
        assert all("No Format Information found" in m for m in messages)

    @requires_wpp_etl
    def test_a_tmf_search_path_decodes_the_messages(self) -> None:
        from pyetwkit import _core as pyetwkit_core

        _clear_wpp_sources()
        pyetwkit_core.set_wpp_tmf_search_path(str(WPP_TMF_DIR))
        assert _wpp_messages() == WPP_EXPECTED

    @requires_wpp_etl
    def test_a_single_tmf_file_decodes_the_messages(self) -> None:
        from pyetwkit import _core as pyetwkit_core

        tmfs = sorted(WPP_TMF_DIR.glob("*.tmf"))
        assert tmfs, "no .tmf alongside the WPP fixture"

        _clear_wpp_sources()
        pyetwkit_core.set_wpp_tmf_file(str(tmfs[0]))
        assert _wpp_messages() == WPP_EXPECTED

    @requires_wpp_etl
    def test_clearing_the_source_goes_back_to_the_placeholder(self) -> None:
        """The sources are live: a decode must not stick around after removal."""
        from pyetwkit import _core as pyetwkit_core

        _clear_wpp_sources()
        pyetwkit_core.set_wpp_tmf_search_path(str(WPP_TMF_DIR))
        assert _wpp_messages() == WPP_EXPECTED

        _clear_wpp_sources()
        assert all("No Format Information found" in m for m in _wpp_messages())

    def test_sources_are_unset_by_default(self) -> None:
        from pyetwkit import _core as pyetwkit_core

        assert pyetwkit_core.wpp_tmf_search_path() is None
        assert pyetwkit_core.wpp_tmf_file() is None
        assert pyetwkit_core.wpp_pdb_path() is None

    def test_sources_round_trip(self) -> None:
        from pyetwkit import _core as pyetwkit_core

        try:
            pyetwkit_core.set_wpp_tmf_file(r"C:\tmf\a.tmf")
            pyetwkit_core.set_wpp_pdb_path(r"C:\bin\a.pdb")
            assert pyetwkit_core.wpp_tmf_file() == r"C:\tmf\a.tmf"
            assert pyetwkit_core.wpp_pdb_path() == r"C:\bin\a.pdb"
        finally:
            _clear_wpp_sources()
        assert pyetwkit_core.wpp_tmf_file() is None
        assert pyetwkit_core.wpp_pdb_path() is None

    @requires_wpp_etl
    def test_a_source_that_matches_nothing_leaves_other_events_alone(self) -> None:
        from pyetwkit import _core as pyetwkit_core

        _clear_wpp_sources()
        before = [
            (e.event_id, tuple(sorted(e.properties)))
            for e in pyetwkit_core.EtlReader(str(SAMPLE_ETL_PATH)).read_all()
        ]
        pyetwkit_core.set_wpp_tmf_search_path(r"Z:\no\such\directory")
        after = [
            (e.event_id, tuple(sorted(e.properties)))
            for e in pyetwkit_core.EtlReader(str(SAMPLE_ETL_PATH)).read_all()
        ]
        assert after == before
