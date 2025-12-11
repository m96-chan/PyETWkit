"""Live Dashboard with Gradio UI (v3.0.0 - #49).

This module provides a real-time visualization dashboard using Gradio,
enabling live ETW event monitoring in a browser-based UI.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from itertools import islice
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class DashboardConfig:
    """Configuration for the Dashboard server."""

    host: str = "127.0.0.1"
    port: int = 7860
    enable_cors: bool = True
    max_clients: int = 100
    event_buffer_size: int = 1000
    share: bool = False


@dataclass
class DashboardStats:
    """Statistics for the dashboard."""

    total_events: int = 0
    events_per_second: float = 0.0
    active_providers: int = 0
    start_time: datetime | None = None
    last_event_time: datetime | None = None


class EventSerializer:
    """Serializes ETW events to JSON for transmission."""

    # Attribute mapping for efficient extraction
    _ATTR_DEFAULTS: dict[str, Any] = {
        "event_id": 0,
        "provider_name": "",
        "process_id": 0,
        "thread_id": 0,
        "properties": {},
    }

    def serialize(self, event: Any) -> str:
        """Serialize a single event to JSON.

        Args:
            event: The ETW event to serialize.

        Returns:
            JSON string representation of the event.
        """
        timestamp = getattr(event, "timestamp", 0.0)
        if hasattr(timestamp, "isoformat"):
            timestamp = timestamp.isoformat()

        # Extract attributes using mapping
        data = {key: getattr(event, key, default) for key, default in self._ATTR_DEFAULTS.items()}
        data["timestamp"] = timestamp
        return json.dumps(data)

    def serialize_batch(self, events: list[Any]) -> str:
        """Serialize a batch of events to JSON.

        Args:
            events: List of ETW events to serialize.

        Returns:
            JSON string with events array.
        """
        data = {"events": [json.loads(self.serialize(e)) for e in events]}
        return json.dumps(data)


class EventBuffer:
    """Thread-safe buffer for ETW events."""

    def __init__(self, max_size: int = 1000) -> None:
        """Initialize the event buffer.

        Args:
            max_size: Maximum number of events to store.
        """
        self._events: deque[dict[str, Any]] = deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._event_count = 0
        self._last_second_count = 0
        self._last_rate_time = time.time()
        self._events_per_second = 0.0

    def add_event(self, event: Any) -> None:
        """Add an event to the buffer.

        Args:
            event: ETW event to add.
        """
        timestamp = getattr(event, "timestamp", datetime.now())
        timestamp_str = timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp)

        event_dict = {
            "timestamp": timestamp_str,
            "provider": getattr(event, "provider_name", "Unknown"),
            "event_id": getattr(event, "event_id", 0),
            "process_id": getattr(event, "process_id", 0),
            "thread_id": getattr(event, "thread_id", 0),
            "properties": str(getattr(event, "properties", {}))[:100],
        }

        with self._lock:
            self._events.append(event_dict)
            self._event_count += 1
            self._last_second_count += 1

            # Update rate calculation
            now = time.time()
            if now - self._last_rate_time >= 1.0:
                self._events_per_second = self._last_second_count / (now - self._last_rate_time)
                self._last_second_count = 0
                self._last_rate_time = now

    def get_events(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent events efficiently.

        Args:
            limit: Maximum number of events to return.

        Returns:
            List of event dictionaries.
        """
        with self._lock:
            event_count = len(self._events)
            if event_count <= limit:
                return list(self._events)
            # Use islice to avoid full list conversion
            start_idx = event_count - limit
            return list(islice(self._events, start_idx, None))

    def get_stats(self) -> dict[str, Any]:
        """Get buffer statistics.

        Returns:
            Dictionary with statistics.
        """
        with self._lock:
            return {
                "total_events": self._event_count,
                "buffer_size": len(self._events),
                "events_per_second": round(self._events_per_second, 2),
            }

    def clear(self) -> None:
        """Clear the buffer."""
        with self._lock:
            self._events.clear()
            self._event_count = 0


class Dashboard:
    """Real-time ETW event visualization dashboard using Gradio.

    Provides a browser-based UI for real-time ETW event monitoring.

    Example:
        >>> dashboard = Dashboard(port=7860)
        >>> dashboard.add_provider("Microsoft-Windows-Kernel-Process")
        >>> dashboard.launch()  # Opens browser at http://localhost:7860
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7860,
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
        self._event_buffer = EventBuffer(self._config.event_buffer_size)
        self._session: Any = None
        self._session_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

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
        """Get the WebSocket URL (for compatibility)."""
        return f"ws://{self._host}:{self._port}/ws"

    def add_provider(self, provider_guid: str) -> Dashboard:
        """Add an ETW provider to monitor.

        Args:
            provider_guid: Provider GUID or name string.

        Returns:
            Self for method chaining.
        """
        self._providers.append(provider_guid)
        return self

    def add_event(self, event: Any) -> None:
        """Add an event to the dashboard buffer.

        Args:
            event: ETW event to display.
        """
        self._event_buffer.add_event(event)

    def _create_gradio_app(self) -> Any:
        """Create the Gradio application.

        Returns:
            Gradio Blocks application.
        """
        try:
            import gradio as gr
        except ImportError as e:
            logger.error("Failed to import Gradio: %s", e)
            raise ImportError(
                "Gradio is required for the dashboard. "
                "Install it with: pip install pyetwkit[dashboard]"
            ) from e

        import pandas as pd

        def get_events_df() -> pd.DataFrame:
            """Get events as a DataFrame."""
            events = self._event_buffer.get_events(100)
            if not events:
                return pd.DataFrame(
                    columns=["Timestamp", "Provider", "EventID", "PID", "TID", "Properties"]
                )
            return pd.DataFrame(
                [
                    {
                        "Timestamp": e["timestamp"],
                        "Provider": e["provider"],
                        "EventID": e["event_id"],
                        "PID": e["process_id"],
                        "TID": e["thread_id"],
                        "Properties": e["properties"],
                    }
                    for e in reversed(events)
                ]
            )

        def get_stats_text() -> str:
            """Get statistics as text."""
            stats = self._event_buffer.get_stats()
            return (
                f"Total Events: {stats['total_events']:,}\n"
                f"Events/sec: {stats['events_per_second']:.1f}\n"
                f"Buffer Size: {stats['buffer_size']:,}\n"
                f"Providers: {len(self._providers)}"
            )

        def get_provider_list() -> str:
            """Get provider list."""
            if not self._providers:
                return "No providers configured"
            return "\n".join(f"- {p}" for p in self._providers)

        def clear_buffer() -> tuple[pd.DataFrame, str]:
            """Clear the event buffer."""
            self._event_buffer.clear()
            return get_events_df(), get_stats_text()

        with gr.Blocks(
            title="PyETWkit Dashboard",
            theme=gr.themes.Soft(),
        ) as app:
            gr.Markdown("# PyETWkit Live Dashboard")
            gr.Markdown("Real-time ETW event monitoring")

            with gr.Row():
                with gr.Column(scale=1):
                    stats_box = gr.Textbox(
                        label="Statistics",
                        value=get_stats_text,
                        lines=4,
                        interactive=False,
                        every=1,
                    )
                    gr.Textbox(
                        label="Active Providers",
                        value=get_provider_list,
                        lines=4,
                        interactive=False,
                    )
                    clear_btn = gr.Button("Clear Events", variant="secondary")

                with gr.Column(scale=4):
                    events_table = gr.Dataframe(
                        value=get_events_df,
                        label="Recent Events (newest first)",
                        headers=["Timestamp", "Provider", "EventID", "PID", "TID", "Properties"],
                        every=0.5,
                        height=500,
                    )

            clear_btn.click(fn=clear_buffer, outputs=[events_table, stats_box])

            gr.Markdown(
                """
                ---
                **Usage:**
                - Events are automatically refreshed every 0.5 seconds
                - Statistics update every 1 second
                - Use 'Clear Events' to reset the buffer
                """
            )

        return app

    def launch(self, blocking: bool = True) -> Dashboard:
        """Launch the dashboard.

        Args:
            blocking: If True, blocks until the dashboard is closed.

        Returns:
            Self for method chaining.
        """
        if self._is_running:
            return self

        app = self._create_gradio_app()
        self._is_running = True

        app.launch(
            server_name=self._host,
            server_port=self._port,
            share=self._config.share,
            prevent_thread_lock=not blocking,
        )

        return self

    def start(self) -> Dashboard:
        """Start the dashboard (non-blocking).

        Returns:
            Self for method chaining.
        """
        return self.launch(blocking=False)

    def stop(self) -> Dashboard:
        """Stop the dashboard.

        Returns:
            Self for method chaining.
        """
        self._is_running = False
        self._stop_event.set()
        return self

    def broadcast_event(self, event: Any) -> None:
        """Add an event to the dashboard (alias for add_event).

        Args:
            event: ETW event to broadcast.
        """
        self.add_event(event)

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
    """Create an event message for transmission.

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
    """Create a stats message for transmission.

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
    """Create an error message for transmission.

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


# Keep old classes for backward compatibility
WebSocketHandler = EventBuffer  # Alias for compatibility
