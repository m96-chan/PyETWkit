"""
EtwStreamer - Asynchronous ETW event streamer

Provides a Pythonic async API for consuming ETW events with
async iterator support and async context manager.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyetwkit._core import EtwEvent, EtwProvider, SessionStats


class EtwStreamer:
    """Asynchronous ETW event streamer.

    A high-level, Pythonic interface for consuming ETW events asynchronously.
    Supports async context manager protocol and async iterator access.

    Args:
        providers: List of EtwProvider instances to enable.
        name: Optional session name. If not provided, a unique name is generated.
        buffer_size_kb: Buffer size in KB (default: 64).
        channel_capacity: Maximum number of events to buffer (default: 10000).
        poll_interval_ms: Interval between event polls in milliseconds (default: 10).

    Example:
        >>> from pyetwkit import EtwStreamer, EtwProvider
        >>> import asyncio
        >>>
        >>> async def monitor_processes():
        ...     provider = EtwProvider.kernel_process()
        ...     async with EtwStreamer(providers=[provider]) as streamer:
        ...         async for event in streamer:
        ...             if event.event_id == 1:  # Process start
        ...                 print(f"Process started: PID {event.process_id}")

        >>> # With timeout and max events
        >>> async def limited_monitor():
        ...     provider = EtwProvider.dns_client()
        ...     async with EtwStreamer(providers=[provider]) as streamer:
        ...         async for event in streamer.events(timeout=30.0, max_events=1000):
        ...             print(f"DNS: {event.get_string('QueryName')}")
    """

    def __init__(
        self,
        providers: Sequence[EtwProvider],
        *,
        name: str | None = None,
        buffer_size_kb: int = 64,
        channel_capacity: int = 10000,
        poll_interval_ms: int = 10,
    ) -> None:
        from pyetwkit._core import EtwSession

        self._session = EtwSession.with_config(
            name=name,
            buffer_size_kb=buffer_size_kb,
            min_buffers=64,
            max_buffers=128,
            channel_capacity=channel_capacity,
        )
        self._providers = list(providers)
        self._started = False
        self._poll_interval_ms = poll_interval_ms

        # Add providers to session
        for provider in self._providers:
            self._session.add_provider(provider)

    async def start(self) -> None:
        """Start the ETW trace session.

        Raises:
            RuntimeError: If the session is already running.
            OSError: If administrator privileges are required.
        """
        if self._started:
            raise RuntimeError("Streamer is already running")

        # Start in thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._session.start)
        self._started = True

    async def stop(self) -> None:
        """Stop the ETW trace session.

        Raises:
            RuntimeError: If the session is not running.
        """
        if not self._started:
            raise RuntimeError("Streamer is not running")

        # Stop in thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._session.stop)
        self._started = False

    @property
    def is_running(self) -> bool:
        """Check if the streamer is running."""
        return self._started and self._session.is_running()

    @property
    def name(self) -> str | None:
        """Get the session name."""
        return self._session.name

    def stats(self) -> SessionStats:
        """Get current session statistics.

        Returns:
            SessionStats object with event counts, loss information, etc.
        """
        return self._session.stats()

    async def events(
        self,
        *,
        timeout: float | None = None,
        max_events: int | None = None,
    ) -> AsyncIterator[EtwEvent]:
        """Async iterate over events with optional timeout and count limit.

        Args:
            timeout: Maximum total time to wait in seconds.
                     None means wait indefinitely.
            max_events: Maximum number of events to yield.
                        None means no limit.

        Yields:
            EtwEvent objects as they are received.

        Example:
            >>> async for event in streamer.events(timeout=60.0, max_events=1000):
            ...     await process_event(event)
        """
        if not self._started:
            raise RuntimeError("Streamer is not running. Call start() first.")

        count = 0
        start_time = asyncio.get_event_loop().time()

        while max_events is None or count < max_events:
            # Check timeout
            if timeout is not None:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= timeout:
                    break

            # Try to get event (non-blocking)
            event = self._session.try_next_event()

            if event is None:
                # No event available, yield control to event loop
                await asyncio.sleep(self._poll_interval_ms / 1000.0)
                continue

            yield event
            count += 1

    def __aiter__(self) -> AsyncIterator[EtwEvent]:
        """Async iterate over events indefinitely.

        This is equivalent to calling events() with no arguments.
        """
        return self.events()

    async def __aenter__(self) -> EtwStreamer:
        """Async context manager entry - starts the streamer."""
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> bool:
        """Async context manager exit - stops the streamer."""
        if self._started:
            await self.stop()
        return False

    def __repr__(self) -> str:
        status = "running" if self.is_running else "stopped"
        return f"EtwStreamer(name={self.name!r}, providers={len(self._providers)}, {status})"


class EventQueue:
    """Async queue for buffering events.

    Provides backpressure handling and overflow detection.
    """

    def __init__(self, maxsize: int = 10000) -> None:
        self._queue: asyncio.Queue[EtwEvent] = asyncio.Queue(maxsize=maxsize)
        self._overflow_count = 0

    async def put(self, event: EtwEvent) -> bool:
        """Put an event into the queue.

        Returns:
            True if the event was added, False if the queue is full.
        """
        try:
            self._queue.put_nowait(event)
            return True
        except asyncio.QueueFull:
            self._overflow_count += 1
            return False

    async def get(self) -> EtwEvent:
        """Get the next event from the queue.

        Blocks until an event is available.
        """
        return await self._queue.get()

    def get_nowait(self) -> EtwEvent | None:
        """Get the next event without blocking.

        Returns:
            The next event, or None if the queue is empty.
        """
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    @property
    def overflow_count(self) -> int:
        """Number of events dropped due to queue overflow."""
        return self._overflow_count

    @property
    def qsize(self) -> int:
        """Current queue size."""
        return self._queue.qsize()

    def empty(self) -> bool:
        """Check if the queue is empty."""
        return self._queue.empty()

    def full(self) -> bool:
        """Check if the queue is full."""
        return self._queue.full()
