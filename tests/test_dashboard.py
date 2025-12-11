"""Tests for Live Dashboard with WebSocket UI (v3.0.0 - #49)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock


class TestDashboardServer:
    """Tests for Dashboard server."""

    def test_dashboard_class_exists(self) -> None:
        """Test that Dashboard class exists."""
        from pyetwkit.dashboard import Dashboard

        assert Dashboard is not None

    def test_dashboard_can_be_created(self) -> None:
        """Test that Dashboard can be instantiated."""
        from pyetwkit.dashboard import Dashboard

        dashboard = Dashboard(port=8080)
        assert dashboard is not None
        assert dashboard.port == 8080

    def test_dashboard_default_port(self) -> None:
        """Test default port is 7860 (Gradio default)."""
        from pyetwkit.dashboard import Dashboard

        dashboard = Dashboard()
        assert dashboard.port == 7860

    def test_dashboard_custom_host(self) -> None:
        """Test custom host configuration."""
        from pyetwkit.dashboard import Dashboard

        dashboard = Dashboard(host="0.0.0.0", port=9000)
        assert dashboard.host == "0.0.0.0"
        assert dashboard.port == 9000

    def test_dashboard_add_provider(self) -> None:
        """Test adding a provider to the dashboard."""
        from pyetwkit.dashboard import Dashboard

        dashboard = Dashboard()
        dashboard.add_provider("22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716")
        assert len(dashboard.providers) == 1

    def test_dashboard_add_multiple_providers(self) -> None:
        """Test adding multiple providers."""
        from pyetwkit.dashboard import Dashboard

        dashboard = Dashboard()
        dashboard.add_provider("22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716")
        dashboard.add_provider("1c95126e-7eea-49a9-a3fe-a378b03ddb4d")
        assert len(dashboard.providers) == 2


class TestDashboardWebSocket:
    """Tests for WebSocket functionality."""

    def test_websocket_handler_exists(self) -> None:
        """Test that WebSocket handler exists."""
        from pyetwkit.dashboard import WebSocketHandler

        assert WebSocketHandler is not None

    def test_websocket_handler_can_be_created(self) -> None:
        """Test that WebSocketHandler can be instantiated."""
        from pyetwkit.dashboard import WebSocketHandler

        handler = WebSocketHandler()
        assert handler is not None

    def test_websocket_broadcast_method(self) -> None:
        """Test that EventBuffer has add_event method (replaces broadcast)."""
        from pyetwkit.dashboard import WebSocketHandler

        handler = WebSocketHandler()
        assert hasattr(handler, "add_event")

    def test_websocket_client_management(self) -> None:
        """Test EventBuffer has get_events method (replaces clients)."""
        from pyetwkit.dashboard import WebSocketHandler

        handler = WebSocketHandler()
        assert hasattr(handler, "get_events")
        assert len(handler.get_events()) == 0


class TestEventSerializer:
    """Tests for event serialization to JSON."""

    def test_event_serializer_exists(self) -> None:
        """Test that EventSerializer exists."""
        from pyetwkit.dashboard import EventSerializer

        assert EventSerializer is not None

    def test_serialize_event_to_json(self) -> None:
        """Test serializing an event to JSON."""
        from pyetwkit.dashboard import EventSerializer

        serializer = EventSerializer()
        mock_event = MagicMock()
        mock_event.event_id = 1
        mock_event.provider_name = "TestProvider"
        mock_event.timestamp = 1234567890.0
        mock_event.process_id = 1234
        mock_event.thread_id = 5678
        mock_event.properties = {"key": "value"}

        result = serializer.serialize(mock_event)
        assert isinstance(result, str)

        data = json.loads(result)
        assert data["event_id"] == 1
        assert data["provider_name"] == "TestProvider"

    def test_serialize_batch_events(self) -> None:
        """Test serializing batch of events."""
        from pyetwkit.dashboard import EventSerializer

        serializer = EventSerializer()
        mock_events = []
        for i in range(3):
            event = MagicMock()
            event.event_id = i
            event.provider_name = "TestProvider"
            event.timestamp = 1234567890.0 + i
            event.process_id = 1234
            event.thread_id = 5678
            event.properties = {}
            mock_events.append(event)

        result = serializer.serialize_batch(mock_events)
        data = json.loads(result)
        assert len(data["events"]) == 3


class TestDashboardConfig:
    """Tests for dashboard configuration."""

    def test_dashboard_config_exists(self) -> None:
        """Test that DashboardConfig exists."""
        from pyetwkit.dashboard import DashboardConfig

        assert DashboardConfig is not None

    def test_dashboard_config_defaults(self) -> None:
        """Test default configuration values."""
        from pyetwkit.dashboard import DashboardConfig

        config = DashboardConfig()
        assert config.host == "127.0.0.1"
        assert config.port == 7860  # Gradio default
        assert config.enable_cors is True
        assert config.max_clients == 100

    def test_dashboard_config_custom_values(self) -> None:
        """Test custom configuration values."""
        from pyetwkit.dashboard import DashboardConfig

        config = DashboardConfig(
            host="0.0.0.0",
            port=9000,
            enable_cors=False,
            max_clients=50,
        )
        assert config.host == "0.0.0.0"
        assert config.port == 9000
        assert config.enable_cors is False
        assert config.max_clients == 50


class TestDashboardMessages:
    """Tests for dashboard message types."""

    def test_event_message_format(self) -> None:
        """Test event message format."""
        from pyetwkit.dashboard import create_event_message

        msg = create_event_message(
            event_id=1,
            provider="TestProvider",
            timestamp=1234567890.0,
            properties={"key": "value"},
        )
        data = json.loads(msg)
        assert data["type"] == "event"
        assert data["payload"]["event_id"] == 1

    def test_stats_message_format(self) -> None:
        """Test stats message format."""
        from pyetwkit.dashboard import create_stats_message

        msg = create_stats_message(
            events_per_second=100,
            total_events=10000,
            active_providers=5,
        )
        data = json.loads(msg)
        assert data["type"] == "stats"
        assert data["payload"]["events_per_second"] == 100

    def test_error_message_format(self) -> None:
        """Test error message format."""
        from pyetwkit.dashboard import create_error_message

        msg = create_error_message("Connection failed")
        data = json.loads(msg)
        assert data["type"] == "error"
        assert data["payload"]["message"] == "Connection failed"


class TestDashboardIntegration:
    """Integration tests for dashboard."""

    def test_dashboard_context_manager(self) -> None:
        """Test dashboard as context manager."""
        from pyetwkit.dashboard import Dashboard

        dashboard = Dashboard(port=8080)
        assert hasattr(dashboard, "__enter__")
        assert hasattr(dashboard, "__exit__")

    def test_dashboard_start_stop(self) -> None:
        """Test dashboard start and stop methods."""
        from pyetwkit.dashboard import Dashboard

        dashboard = Dashboard(port=8080)
        assert hasattr(dashboard, "start")
        assert hasattr(dashboard, "stop")
        assert hasattr(dashboard, "is_running")

    def test_dashboard_url_property(self) -> None:
        """Test dashboard URL property."""
        from pyetwkit.dashboard import Dashboard

        dashboard = Dashboard(host="localhost", port=8080)
        assert dashboard.url == "http://localhost:8080"

    def test_dashboard_websocket_url(self) -> None:
        """Test dashboard WebSocket URL property."""
        from pyetwkit.dashboard import Dashboard

        dashboard = Dashboard(host="localhost", port=8080)
        assert dashboard.ws_url == "ws://localhost:8080/ws"
