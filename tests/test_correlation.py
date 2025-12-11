"""Tests for Event Correlation Engine (v3.0.0 - #50)."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock


class TestCorrelationEngine:
    """Tests for CorrelationEngine."""

    def test_correlation_engine_exists(self) -> None:
        """Test that CorrelationEngine class exists."""
        from pyetwkit.correlation import CorrelationEngine

        assert CorrelationEngine is not None

    def test_correlation_engine_can_be_created(self) -> None:
        """Test that CorrelationEngine can be instantiated."""
        from pyetwkit.correlation import CorrelationEngine

        engine = CorrelationEngine()
        assert engine is not None

    def test_correlation_engine_add_provider(self) -> None:
        """Test adding a provider to the engine."""
        from pyetwkit.correlation import CorrelationEngine

        engine = CorrelationEngine()
        engine.add_provider("22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716")
        assert len(engine.providers) == 1

    def test_correlation_engine_add_event(self) -> None:
        """Test adding an event to the engine."""
        from pyetwkit.correlation import CorrelationEngine

        engine = CorrelationEngine()

        mock_event = MagicMock()
        mock_event.event_id = 1
        mock_event.process_id = 1234
        mock_event.thread_id = 5678
        mock_event.timestamp = datetime.now()
        mock_event.properties = {}

        engine.add_event(mock_event)
        assert engine.event_count == 1


class TestCorrelationByPID:
    """Tests for PID-based correlation."""

    def test_correlate_by_pid(self) -> None:
        """Test correlating events by process ID."""
        from pyetwkit.correlation import CorrelationEngine

        engine = CorrelationEngine()

        # Add events with same PID
        for i in range(3):
            event = MagicMock()
            event.event_id = i
            event.process_id = 1234
            event.thread_id = 5678
            event.timestamp = datetime.now() + timedelta(seconds=i)
            event.provider_name = "TestProvider"
            event.properties = {}
            engine.add_event(event)

        # Add event with different PID
        other_event = MagicMock()
        other_event.event_id = 100
        other_event.process_id = 9999
        other_event.thread_id = 1111
        other_event.timestamp = datetime.now()
        other_event.provider_name = "TestProvider"
        other_event.properties = {}
        engine.add_event(other_event)

        # Correlate by PID 1234
        correlated = engine.correlate_by_pid(1234)
        assert len(correlated) == 3

    def test_correlate_by_pid_returns_timeline(self) -> None:
        """Test that correlated events are in chronological order."""
        from pyetwkit.correlation import CorrelationEngine

        engine = CorrelationEngine()
        base_time = datetime.now()

        # Add events out of order
        for i in [2, 0, 1]:
            event = MagicMock()
            event.event_id = i
            event.process_id = 1234
            event.thread_id = 5678
            event.timestamp = base_time + timedelta(seconds=i)
            event.provider_name = "TestProvider"
            event.properties = {}
            engine.add_event(event)

        correlated = engine.correlate_by_pid(1234)
        # Should be sorted by timestamp
        assert correlated[0].event_id == 0
        assert correlated[1].event_id == 1
        assert correlated[2].event_id == 2


class TestCorrelationByTID:
    """Tests for TID-based correlation."""

    def test_correlate_by_tid(self) -> None:
        """Test correlating events by thread ID."""
        from pyetwkit.correlation import CorrelationEngine

        engine = CorrelationEngine()

        # Add events with same TID
        for i in range(3):
            event = MagicMock()
            event.event_id = i
            event.process_id = 1234
            event.thread_id = 5678
            event.timestamp = datetime.now() + timedelta(seconds=i)
            event.provider_name = "TestProvider"
            event.properties = {}
            engine.add_event(event)

        correlated = engine.correlate_by_tid(5678)
        assert len(correlated) == 3


class TestCorrelationGroup:
    """Tests for CorrelationGroup."""

    def test_correlation_group_exists(self) -> None:
        """Test that CorrelationGroup exists."""
        from pyetwkit.correlation import CorrelationGroup

        assert CorrelationGroup is not None

    def test_correlation_group_properties(self) -> None:
        """Test CorrelationGroup properties."""
        from pyetwkit.correlation import CorrelationGroup

        events = [MagicMock() for _ in range(3)]
        group = CorrelationGroup(
            key_type="pid",
            key_value=1234,
            events=events,
        )

        assert group.key_type == "pid"
        assert group.key_value == 1234
        assert len(group.events) == 3

    def test_correlation_group_timeline(self) -> None:
        """Test CorrelationGroup timeline method."""
        from pyetwkit.correlation import CorrelationGroup

        events = []
        base_time = datetime.now()
        for i in range(3):
            event = MagicMock()
            event.timestamp = base_time + timedelta(seconds=i)
            events.append(event)

        group = CorrelationGroup(
            key_type="pid",
            key_value=1234,
            events=events,
        )

        timeline = group.timeline()
        assert len(timeline) == 3


class TestCorrelatedGroups:
    """Tests for correlated_groups iterator."""

    def test_correlated_groups_method(self) -> None:
        """Test correlated_groups method exists."""
        from pyetwkit.correlation import CorrelationEngine

        engine = CorrelationEngine()
        assert hasattr(engine, "correlated_groups")

    def test_correlated_groups_returns_groups(self) -> None:
        """Test correlated_groups returns CorrelationGroup objects."""
        from pyetwkit.correlation import CorrelationEngine, CorrelationGroup

        engine = CorrelationEngine()

        # Add events for multiple PIDs
        for pid in [1234, 5678]:
            for i in range(2):
                event = MagicMock()
                event.event_id = i
                event.process_id = pid
                event.thread_id = pid * 10
                event.timestamp = datetime.now() + timedelta(seconds=i)
                event.provider_name = "TestProvider"
                event.properties = {}
                engine.add_event(event)

        groups = list(engine.correlated_groups())
        assert len(groups) >= 2
        assert all(isinstance(g, CorrelationGroup) for g in groups)


class TestCausalityTracing:
    """Tests for causality tracing."""

    def test_trace_causality_method(self) -> None:
        """Test trace_causality method exists."""
        from pyetwkit.correlation import CorrelationEngine

        engine = CorrelationEngine()
        assert hasattr(engine, "trace_causality")

    def test_trace_causality_returns_chain(self) -> None:
        """Test trace_causality returns event chain."""
        from pyetwkit.correlation import CorrelationEngine

        engine = CorrelationEngine()

        # Add related events
        network_event = MagicMock()
        network_event.event_id = 1
        network_event.process_id = 1234
        network_event.thread_id = 5678
        network_event.timestamp = datetime.now()
        network_event.provider_name = "Network"
        network_event.properties = {"handle": 0x100}
        engine.add_event(network_event)

        file_event = MagicMock()
        file_event.event_id = 2
        file_event.process_id = 1234
        file_event.thread_id = 5678
        file_event.timestamp = datetime.now() + timedelta(milliseconds=10)
        file_event.provider_name = "File"
        file_event.properties = {}
        engine.add_event(file_event)

        chain = engine.trace_causality(network_event, target_type="file")
        assert chain is not None


class TestCorrelationKeys:
    """Tests for correlation key types."""

    def test_correlation_key_types(self) -> None:
        """Test supported correlation key types."""
        from pyetwkit.correlation import CorrelationKeyType

        assert hasattr(CorrelationKeyType, "PID")
        assert hasattr(CorrelationKeyType, "TID")
        assert hasattr(CorrelationKeyType, "HANDLE")
        assert hasattr(CorrelationKeyType, "SESSION_ID")
        assert hasattr(CorrelationKeyType, "CONNECTION_ID")


class TestCorrelationOutput:
    """Tests for correlation output formats."""

    def test_to_timeline_json(self) -> None:
        """Test converting correlation to timeline JSON."""
        from pyetwkit.correlation import CorrelationEngine

        engine = CorrelationEngine()

        event = MagicMock()
        event.event_id = 1
        event.process_id = 1234
        event.thread_id = 5678
        event.timestamp = datetime.now()
        event.provider_name = "TestProvider"
        event.properties = {}
        engine.add_event(event)

        json_output = engine.to_timeline_json(pid=1234)
        assert isinstance(json_output, str)

    def test_to_dataframe(self) -> None:
        """Test converting correlation to pandas DataFrame."""
        from pyetwkit.correlation import CorrelationEngine

        engine = CorrelationEngine()

        event = MagicMock()
        event.event_id = 1
        event.process_id = 1234
        event.thread_id = 5678
        event.timestamp = datetime.now()
        event.provider_name = "TestProvider"
        event.properties = {}
        engine.add_event(event)

        df = engine.to_dataframe(pid=1234)
        # Should return DataFrame-like object or dict
        assert df is not None


class TestCorrelationConfig:
    """Tests for correlation configuration."""

    def test_correlation_config_exists(self) -> None:
        """Test that CorrelationConfig exists."""
        from pyetwkit.correlation import CorrelationConfig

        assert CorrelationConfig is not None

    def test_correlation_config_defaults(self) -> None:
        """Test default configuration values."""
        from pyetwkit.correlation import CorrelationConfig

        config = CorrelationConfig()
        assert config.time_window_ms == 1000
        assert config.max_events == 10000
        assert config.enable_handle_tracking is True

    def test_correlation_config_custom(self) -> None:
        """Test custom configuration values."""
        from pyetwkit.correlation import CorrelationConfig

        config = CorrelationConfig(
            time_window_ms=5000,
            max_events=50000,
            enable_handle_tracking=False,
        )
        assert config.time_window_ms == 5000
        assert config.max_events == 50000
        assert config.enable_handle_tracking is False
