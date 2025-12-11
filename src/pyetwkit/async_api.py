"""Enhanced async API for ETW event streaming.

This module provides improved async/await support for ETW event streaming,
including:
- Async context managers
- Async iterators with filtering
- Concurrent event processing
- Integration with asyncio patterns
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from pyetwkit._core import EtwEvent, EtwProvider, SessionStats

from pyetwkit.typed_events import TypedEvent, to_typed_event

T = TypeVar("T")


class AsyncEtwSession:
    """Async ETW session with modern Python async patterns.

    Provides a high-level async interface for ETW event consumption
    with support for typed events, filtering, and concurrent processing.

    Example:
        >>> async def monitor():
        ...     async with AsyncEtwSession() as session:
        ...         session.add_provider("Microsoft-Windows-DNS-Client")
        ...         async for event in session.typed_events():
        ...             if isinstance(event, DnsQueryEvent):
        ...                 print(f"DNS: {event.query_name}")
    """

    def __init__(
        self,
        name: str | None = None,
        *,
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
        self._started = False
        self._poll_interval_ms = poll_interval_ms
        self._event_callbacks: list[Callable[[EtwEvent], Awaitable[None]]] = []
        self._filter_callbacks: list[Callable[[EtwEvent], bool]] = []

    def add_provider(
        self,
        provider: EtwProvider | str,
        *,
        level: int = 4,
        keywords: int = 0xFFFFFFFFFFFFFFFF,
    ) -> AsyncEtwSession:
        """Add a provider to the session.

        Args:
            provider: EtwProvider instance or provider name/GUID string
            level: Trace level (1=Critical to 5=Verbose)
            keywords: Event keywords to enable

        Returns:
            Self for method chaining
        """
        from pyetwkit._core import EtwProvider as CoreProvider

        if isinstance(provider, str):
            # Try to use static methods for known providers
            if provider.lower() == "microsoft-windows-dns-client" or "dns" in provider.lower():
                prov = CoreProvider.dns_client().level(level)
            elif provider.lower() == "microsoft-windows-kernel-process" or "process" in provider.lower():
                prov = CoreProvider.kernel_process().level(level)
            elif provider.lower() == "microsoft-windows-powershell" or "powershell" in provider.lower():
                prov = CoreProvider.powershell().level(level)
            else:
                # Assume it's a GUID
                prov = CoreProvider(provider, provider).level(level)
        else:
            prov = provider

        self._session.add_provider(prov)
        return self

    def on_event(
        self, callback: Callable[[EtwEvent], Awaitable[None]]
    ) -> AsyncEtwSession:
        """Register an async callback for each event.

        Args:
            callback: Async function called for each event

        Returns:
            Self for method chaining

        Example:
            >>> async def log_event(event):
            ...     await db.insert(event.to_dict())
            ...
            >>> session.on_event(log_event)
        """
        self._event_callbacks.append(callback)
        return self

    def filter(self, predicate: Callable[[EtwEvent], bool]) -> AsyncEtwSession:
        """Add an event filter.

        Args:
            predicate: Function returning True for events to keep

        Returns:
            Self for method chaining

        Example:
            >>> session.filter(lambda e: e.event_id in [1, 2])
        """
        self._filter_callbacks.append(predicate)
        return self

    async def start(self) -> None:
        """Start the ETW session."""
        if self._started:
            raise RuntimeError("Session already started")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._session.start)
        self._started = True

    async def stop(self) -> None:
        """Stop the ETW session."""
        if not self._started:
            return

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._session.stop)
        self._started = False

    @property
    def is_running(self) -> bool:
        """Check if session is running."""
        return self._started and self._session.is_running()

    def stats(self) -> SessionStats:
        """Get session statistics."""
        return self._session.stats()

    def _should_process(self, event: EtwEvent) -> bool:
        """Check if event passes all filters."""
        for predicate in self._filter_callbacks:
            if not predicate(event):
                return False
        return True

    async def _process_callbacks(self, event: EtwEvent) -> None:
        """Process all registered callbacks for an event."""
        for callback in self._event_callbacks:
            await callback(event)

    async def events(
        self,
        *,
        timeout: float | None = None,
        max_events: int | None = None,
    ) -> AsyncIterator[EtwEvent]:
        """Async iterate over raw events.

        Args:
            timeout: Maximum total time in seconds
            max_events: Maximum events to yield

        Yields:
            EtwEvent objects

        Note:
            Auto-starts the session if not already started.
        """
        if not self._started:
            await self.start()

        count = 0
        start_time = asyncio.get_event_loop().time()

        while max_events is None or count < max_events:
            if timeout is not None:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= timeout:
                    break

            event = self._session.try_next_event()

            if event is None:
                await asyncio.sleep(self._poll_interval_ms / 1000.0)
                continue

            if not self._should_process(event):
                continue

            await self._process_callbacks(event)
            yield event
            count += 1

    async def typed_events(
        self,
        *,
        timeout: float | None = None,
        max_events: int | None = None,
    ) -> AsyncIterator[TypedEvent]:
        """Async iterate over typed events.

        Automatically converts raw events to their typed equivalents
        based on provider and event ID.

        Args:
            timeout: Maximum total time in seconds
            max_events: Maximum events to yield

        Yields:
            TypedEvent subclass instances

        Example:
            >>> async for event in session.typed_events():
            ...     if isinstance(event, ProcessStartEvent):
            ...         print(f"Process: {event.image_file_name}")
        """
        async for event in self.events(timeout=timeout, max_events=max_events):
            yield to_typed_event(event)

    def __aiter__(self) -> AsyncIterator[EtwEvent]:
        """Async iteration over events."""
        return self.events()

    async def __aenter__(self) -> AsyncEtwSession:
        """Async context manager entry.

        Note: Does NOT auto-start the session. Call start() explicitly
        after adding providers, or use events() which auto-starts.
        """
        return self

    async def __aexit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """Async context manager exit."""
        await self.stop()
        return False


async def gather_events(
    *sessions: AsyncEtwSession,
    timeout: float | None = None,
    max_per_session: int | None = None,
) -> list[list[EtwEvent]]:
    """Gather events from multiple sessions concurrently.

    Args:
        *sessions: AsyncEtwSession instances
        timeout: Maximum time to collect
        max_per_session: Max events per session

    Returns:
        List of event lists, one per session

    Example:
        >>> dns_session = AsyncEtwSession().add_provider("DNS-Client")
        >>> net_session = AsyncEtwSession().add_provider("Kernel-Network")
        >>> dns_events, net_events = await gather_events(
        ...     dns_session, net_session, timeout=10.0
        ... )
    """

    async def collect(session: AsyncEtwSession) -> list[EtwEvent]:
        events = []
        async for event in session.events(
            timeout=timeout, max_events=max_per_session
        ):
            events.append(event)
        return events

    results = await asyncio.gather(*[collect(s) for s in sessions])
    return list(results)


async def stream_to_queue(
    session: AsyncEtwSession,
    queue: asyncio.Queue[EtwEvent | None],
    *,
    timeout: float | None = None,
    max_events: int | None = None,
) -> int:
    """Stream events from session to an asyncio queue.

    Args:
        session: AsyncEtwSession to stream from
        queue: Queue to put events into
        timeout: Maximum streaming time
        max_events: Maximum events to stream

    Returns:
        Number of events streamed

    Example:
        >>> queue = asyncio.Queue()
        >>> async def producer():
        ...     await stream_to_queue(session, queue, timeout=60)
        ...     await queue.put(None)  # Signal completion
        >>> async def consumer():
        ...     while (event := await queue.get()) is not None:
        ...         process(event)
    """
    count = 0
    async for event in session.events(timeout=timeout, max_events=max_events):
        await queue.put(event)
        count += 1
    return count


class EventBatcher:
    """Batch events for efficient processing.

    Collects events and yields them in batches, useful for
    bulk database inserts or batch processing.

    Example:
        >>> batcher = EventBatcher(batch_size=100, timeout=1.0)
        >>> async for batch in batcher.batches(session):
        ...     await db.insert_many([e.to_dict() for e in batch])
    """

    def __init__(
        self,
        batch_size: int = 100,
        timeout: float = 1.0,
    ) -> None:
        self.batch_size = batch_size
        self.timeout = timeout

    async def batches(
        self,
        session: AsyncEtwSession,
        *,
        max_batches: int | None = None,
    ) -> AsyncIterator[list[EtwEvent]]:
        """Yield batches of events.

        Args:
            session: Session to read from
            max_batches: Maximum batches to yield

        Yields:
            Lists of events
        """
        batch: list[EtwEvent] = []
        batch_count = 0
        last_yield = asyncio.get_event_loop().time()

        async for event in session.events():
            batch.append(event)
            now = asyncio.get_event_loop().time()

            should_yield = (
                len(batch) >= self.batch_size or (now - last_yield) >= self.timeout
            )

            if should_yield and batch:
                yield batch
                batch = []
                batch_count += 1
                last_yield = now

                if max_batches and batch_count >= max_batches:
                    break

        # Yield remaining events
        if batch:
            yield batch


__all__ = [
    "AsyncEtwSession",
    "gather_events",
    "stream_to_queue",
    "EventBatcher",
]
