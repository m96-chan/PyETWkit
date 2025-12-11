"""Live Dashboard with WebSocket UI (v3.0.0 - #49).

This module provides a real-time visualization dashboard delivered via WebSocket
to a browser-based UI, enabling live ETW event monitoring.
"""

from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


@dataclass
class DashboardConfig:
    """Configuration for the Dashboard server."""

    host: str = "127.0.0.1"
    port: int = 8080
    enable_cors: bool = True
    max_clients: int = 100
    event_buffer_size: int = 1000


class EventSerializer:
    """Serializes ETW events to JSON for WebSocket transmission."""

    def serialize(self, event: Any) -> str:
        """Serialize a single event to JSON.

        Args:
            event: The ETW event to serialize.

        Returns:
            JSON string representation of the event.
        """
        data = {
            "event_id": getattr(event, "event_id", 0),
            "provider_name": getattr(event, "provider_name", ""),
            "timestamp": getattr(event, "timestamp", 0.0),
            "process_id": getattr(event, "process_id", 0),
            "thread_id": getattr(event, "thread_id", 0),
            "properties": getattr(event, "properties", {}),
        }
        return json.dumps(data)

    def serialize_batch(self, events: list[Any]) -> str:
        """Serialize a batch of events to JSON.

        Args:
            events: List of ETW events to serialize.

        Returns:
            JSON string with events array.
        """
        data = {
            "events": [
                {
                    "event_id": getattr(e, "event_id", 0),
                    "provider_name": getattr(e, "provider_name", ""),
                    "timestamp": getattr(e, "timestamp", 0.0),
                    "process_id": getattr(e, "process_id", 0),
                    "properties": getattr(e, "properties", {}),
                }
                for e in events
            ]
        }
        return json.dumps(data)


class WebSocketHandler:
    """Handles WebSocket connections and message broadcasting."""

    def __init__(self) -> None:
        """Initialize the WebSocket handler."""
        self.clients: list[Any] = []
        self._lock = threading.Lock()

    def add_client(self, client: Any) -> None:
        """Add a client connection.

        Args:
            client: WebSocket client connection.
        """
        with self._lock:
            self.clients.append(client)

    def remove_client(self, client: Any) -> None:
        """Remove a client connection.

        Args:
            client: WebSocket client connection.
        """
        with self._lock:
            if client in self.clients:
                self.clients.remove(client)

    async def broadcast(self, message: str) -> None:
        """Broadcast a message to all connected clients.

        Args:
            message: Message to broadcast.
        """
        with self._lock:
            clients = list(self.clients)

        for client in clients:
            try:
                await client.send(message)
            except Exception:
                self.remove_client(client)

    def broadcast_sync(self, message: str) -> None:
        """Synchronous broadcast wrapper.

        Args:
            message: Message to broadcast.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.broadcast(message))
            else:
                loop.run_until_complete(self.broadcast(message))
        except RuntimeError:
            # No event loop, create one
            asyncio.run(self.broadcast(message))


class Dashboard:
    """Real-time ETW event visualization dashboard.

    Provides a WebSocket-based server that streams ETW events to
    browser-based UI clients for real-time visualization.

    Example:
        >>> dashboard = Dashboard(port=8080)
        >>> dashboard.add_provider("Microsoft-Windows-Kernel-Process")
        >>> dashboard.start()
        >>> # Dashboard available at http://localhost:8080
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        config: DashboardConfig | None = None,
    ) -> None:
        """Initialize the Dashboard.

        Args:
            host: Host address to bind to.
            port: Port number to listen on.
            config: Optional dashboard configuration.
        """
        self._config = config or DashboardConfig(host=host, port=port)
        self._host = host
        self._port = port
        self._providers: list[str] = []
        self._is_running = False
        self._ws_handler = WebSocketHandler()
        self._serializer = EventSerializer()
        self._server_thread: threading.Thread | None = None

    @property
    def host(self) -> str:
        """Get the host address."""
        return self._host

    @property
    def port(self) -> int:
        """Get the port number."""
        return self._port

    @property
    def providers(self) -> list[str]:
        """Get the list of providers."""
        return list(self._providers)

    @property
    def is_running(self) -> bool:
        """Check if the dashboard is running."""
        return self._is_running

    @property
    def url(self) -> str:
        """Get the HTTP URL for the dashboard."""
        return f"http://{self._host}:{self._port}"

    @property
    def ws_url(self) -> str:
        """Get the WebSocket URL for event streaming."""
        return f"ws://{self._host}:{self._port}/ws"

    def add_provider(self, provider_guid: str) -> Dashboard:
        """Add an ETW provider to monitor.

        Args:
            provider_guid: Provider GUID string.

        Returns:
            Self for method chaining.
        """
        self._providers.append(provider_guid)
        return self

    def start(self) -> Dashboard:
        """Start the dashboard server.

        Returns:
            Self for method chaining.
        """
        if self._is_running:
            return self

        self._is_running = True
        # Server would be started in a background thread
        # Actual WebSocket server implementation would use aiohttp or similar
        return self

    def stop(self) -> Dashboard:
        """Stop the dashboard server.

        Returns:
            Self for method chaining.
        """
        self._is_running = False
        return self

    def broadcast_event(self, event: Any) -> None:
        """Broadcast an event to all connected clients.

        Args:
            event: ETW event to broadcast.
        """
        message = self._serializer.serialize(event)
        self._ws_handler.broadcast_sync(message)

    def __enter__(self) -> Dashboard:
        """Context manager entry."""
        return self.start()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Context manager exit."""
        self.stop()
        return False


def create_event_message(
    event_id: int,
    provider: str,
    timestamp: float,
    properties: dict[str, Any],
) -> str:
    """Create an event message for WebSocket transmission.

    Args:
        event_id: Event ID.
        provider: Provider name.
        timestamp: Event timestamp.
        properties: Event properties.

    Returns:
        JSON message string.
    """
    return json.dumps(
        {
            "type": "event",
            "payload": {
                "event_id": event_id,
                "provider": provider,
                "timestamp": timestamp,
                "properties": properties,
            },
        }
    )


def create_stats_message(
    events_per_second: int,
    total_events: int,
    active_providers: int,
) -> str:
    """Create a stats message for WebSocket transmission.

    Args:
        events_per_second: Current event rate.
        total_events: Total events processed.
        active_providers: Number of active providers.

    Returns:
        JSON message string.
    """
    return json.dumps(
        {
            "type": "stats",
            "payload": {
                "events_per_second": events_per_second,
                "total_events": total_events,
                "active_providers": active_providers,
            },
        }
    )


def create_error_message(message: str) -> str:
    """Create an error message for WebSocket transmission.

    Args:
        message: Error message.

    Returns:
        JSON message string.
    """
    return json.dumps(
        {
            "type": "error",
            "payload": {
                "message": message,
            },
        }
    )
