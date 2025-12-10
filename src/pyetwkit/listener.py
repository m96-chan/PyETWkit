"""
EtwListener - Synchronous ETW event listener

Provides a Pythonic synchronous API for consuming ETW events with
iterator-based access and context manager support.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator, Sequence

if TYPE_CHECKING:
    from pyetwkit._core import EtwEvent, EtwProvider, EtwSession, SessionStats


class EtwListener:
    """Synchronous ETW event listener.

    A high-level, Pythonic interface for consuming ETW events synchronously.
    Supports context manager protocol and iterator-based event access.

    Args:
        providers: List of EtwProvider instances to enable.
        name: Optional session name. If not provided, a unique name is generated.
        buffer_size_kb: Buffer size in KB (default: 64).
        channel_capacity: Maximum number of events to buffer (default: 10000).

    Example:
        >>> from pyetwkit import EtwListener, EtwProvider
        >>>
        >>> # Monitor DNS queries
        >>> provider = EtwProvider.dns_client()
        >>> with EtwListener(providers=[provider]) as listener:
        ...     for event in listener.events(timeout=10.0, max_events=100):
        ...         print(f"DNS Query: {event.get_string('QueryName')}")

        >>> # Using iteration directly
        >>> listener = EtwListener(providers=[EtwProvider.kernel_process()])
        >>> listener.start()
        >>> try:
        ...     for event in listener:
        ...         if event.event_id == 1:  # Process start
        ...             print(f"Process started: PID {event.process_id}")
        ... finally:
        ...     listener.stop()
    """

    def __init__(
        self,
        providers: Sequence[EtwProvider],
        *,
        name: str | None = None,
        buffer_size_kb: int = 64,
        channel_capacity: int = 10000,
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

        # Add providers to session
        for provider in self._providers:
            self._session.add_provider(provider)

    def start(self) -> None:
        """Start the ETW trace session.

        Raises:
            RuntimeError: If the session is already running.
            OSError: If administrator privileges are required.
        """
        if self._started:
            raise RuntimeError("Listener is already running")

        self._session.start()
        self._started = True

    def stop(self) -> None:
        """Stop the ETW trace session.

        Raises:
            RuntimeError: If the session is not running.
        """
        if not self._started:
            raise RuntimeError("Listener is not running")

        self._session.stop()
        self._started = False

    @property
    def is_running(self) -> bool:
        """Check if the listener is running."""
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

    def events(
        self,
        *,
        timeout: float | None = None,
        max_events: int | None = None,
    ) -> Iterator[EtwEvent]:
        """Iterate over events with optional timeout and count limit.

        Args:
            timeout: Maximum time to wait for each event in seconds.
                     None means wait indefinitely.
            max_events: Maximum number of events to yield.
                        None means no limit.

        Yields:
            EtwEvent objects as they are received.

        Example:
            >>> # Get up to 100 events, waiting up to 5 seconds for each
            >>> for event in listener.events(timeout=5.0, max_events=100):
            ...     process_event(event)
        """
        if not self._started:
            raise RuntimeError("Listener is not running. Call start() first.")

        count = 0
        timeout_ms = int(timeout * 1000) if timeout is not None else None

        while max_events is None or count < max_events:
            if timeout_ms is not None:
                event = self._session.next_event_timeout(timeout_ms)
            else:
                event = self._session.next_event()

            if event is None:
                if timeout is not None:
                    # Timeout occurred
                    break
                continue

            yield event
            count += 1

    def __iter__(self) -> Iterator[EtwEvent]:
        """Iterate over events indefinitely.

        This is equivalent to calling events() with no arguments.
        """
        return self.events()

    def __enter__(self) -> EtwListener:
        """Context manager entry - starts the listener."""
        self.start()
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object) -> bool:
        """Context manager exit - stops the listener."""
        if self._started:
            self.stop()
        return False

    def __repr__(self) -> str:
        status = "running" if self.is_running else "stopped"
        return f"EtwListener(name={self.name!r}, providers={len(self._providers)}, {status})"
