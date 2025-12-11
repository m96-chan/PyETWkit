"""Multi-session concurrent subscription support (v2.0.0 - #48).

This module provides the ability to manage multiple ETW sessions simultaneously,
with unified event delivery from all providers.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from queue import Empty, Queue
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyetwkit._core import EtwEvent


@dataclass
class SessionInfo:
    """Information about a managed session."""

    name: str
    session_type: str  # "user" or "kernel"
    providers: list[str] = field(default_factory=list)
    is_running: bool = False


class MultiSession:
    """Manager for multiple concurrent ETW sessions.

    Enables simultaneous subscription to multiple ETW sessions (Kernel + User + Custom providers)
    with unified event delivery to Python.

    Example:
        >>> manager = MultiSession()
        >>> manager.add_kernel_session(flags=KernelFlags().with_process().with_network())
        >>> manager.add_provider("Microsoft-Windows-DNS-Client")
        >>> manager.start()
        >>> for event in manager.events():
        ...     print(f"[{event.source}] {event.provider_name}: {event.event_id}")
    """

    def __init__(self, name_prefix: str = "PyETWkit") -> None:
        """Initialize MultiSession manager.

        Args:
            name_prefix: Prefix for auto-generated session names.
        """
        self._name_prefix = name_prefix
        self._sessions: dict[str, Any] = {}  # name -> session object
        self._session_info: dict[str, SessionInfo] = {}  # name -> info
        self._event_queue: Queue[Any] = Queue()
        self._threads: list[threading.Thread] = []
        self._running = False
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    @property
    def sessions(self) -> dict[str, SessionInfo]:
        """Get information about all managed sessions."""
        return dict(self._session_info)

    def add_provider(
        self,
        provider: str,
        *,
        session_name: str | None = None,
        level: int = 5,
        keywords_any: int = 0xFFFFFFFFFFFFFFFF,
        keywords_all: int = 0,
    ) -> MultiSession:
        """Add a provider to the multi-session manager.

        Args:
            provider: Provider GUID string (e.g., "22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716").
            session_name: Optional custom session name. Auto-generated if not provided.
            level: Trace level (0=Always to 5=Verbose).
            keywords_any: Keywords to match (any).
            keywords_all: Keywords that must all match.

        Returns:
            Self for method chaining.
        """
        from pyetwkit._core import EtwProvider, EtwSession

        if session_name is None:
            session_name = f"{self._name_prefix}-{uuid.uuid4().hex[:8]}"

        with self._lock:
            if session_name not in self._sessions:
                session = EtwSession(session_name)
                self._sessions[session_name] = session
                self._session_info[session_name] = SessionInfo(
                    name=session_name,
                    session_type="user",
                    providers=[],
                )

            # Add provider to session - provider must be a GUID string
            etw_provider = EtwProvider(provider).level(level)
            etw_provider = etw_provider.keywords_any(keywords_any)
            etw_provider = etw_provider.keywords_all(keywords_all)

            self._sessions[session_name].add_provider(etw_provider)
            self._session_info[session_name].providers.append(provider)

        return self

    def add_kernel_session(
        self,
        *,
        flags: int | None = None,
        session_name: str | None = None,
    ) -> MultiSession:
        """Add a kernel session to the manager.

        Args:
            flags: Kernel trace flags (use KernelFlags constants like
                   KernelFlags.PROCESS | KernelFlags.THREAD).
                   Defaults to KernelFlags.ALL_BASIC if not specified.
            session_name: Optional custom session name.

        Returns:
            Self for method chaining.
        """
        from pyetwkit._core import KernelFlags, KernelSession

        if session_name is None:
            session_name = f"{self._name_prefix}-Kernel"

        if flags is None:
            flags = KernelFlags.ALL_BASIC

        with self._lock:
            session = KernelSession()
            session.set_categories(flags)
            self._sessions[session_name] = session
            self._session_info[session_name] = SessionInfo(
                name=session_name,
                session_type="kernel",
                providers=["NT Kernel Logger"],
            )

        return self

    def start(self) -> MultiSession:
        """Start all sessions and begin event collection.

        Returns:
            Self for method chaining.

        Raises:
            PermissionError: If administrator privileges are required but not available.
            RuntimeError: If sessions fail to start.
        """
        if self._running:
            return self

        self._running = True
        self._stop_event.clear()

        with self._lock:
            for name, session in self._sessions.items():
                # Start session
                session.start()
                self._session_info[name].is_running = True

                # Create thread to collect events
                thread = threading.Thread(
                    target=self._collect_events,
                    args=(name, session),
                    daemon=True,
                )
                thread.start()
                self._threads.append(thread)

        return self

    def stop(self) -> MultiSession:
        """Stop all sessions.

        Returns:
            Self for method chaining.
        """
        if not self._running:
            return self

        self._stop_event.set()
        self._running = False

        import contextlib

        with self._lock:
            for name, session in self._sessions.items():
                with contextlib.suppress(Exception):
                    session.stop()
                self._session_info[name].is_running = False

        # Wait for threads to finish
        for thread in self._threads:
            thread.join(timeout=1.0)

        self._threads.clear()
        return self

    def _collect_events(self, session_name: str, session: Any) -> None:
        """Collect events from a session and put them in the unified queue.

        Args:
            session_name: Name of the session for tagging events.
            session: The session object to collect from.
        """
        try:
            for event in session.events():
                if self._stop_event.is_set():
                    break

                # Tag event with source session
                event._source_session = session_name  # type: ignore
                self._event_queue.put(event)
        except Exception:
            pass  # Session ended or error occurred

    def events(self, *, timeout: float | None = None) -> Iterator[EtwEvent]:
        """Get unified event stream from all sessions.

        Args:
            timeout: Timeout in seconds for waiting for events.
                     None means wait indefinitely.

        Yields:
            Events from all managed sessions.
        """
        while self._running or not self._event_queue.empty():
            try:
                event = self._event_queue.get(timeout=timeout or 0.1)
                yield event
            except Empty:
                if not self._running:
                    break
                if timeout is not None:
                    break

    def stats(self) -> dict[str, Any]:
        """Get statistics for all sessions.

        Returns:
            Dictionary containing statistics for each session.
        """
        result: dict[str, Any] = {
            "total_sessions": len(self._sessions),
            "running": self._running,
            "queue_size": self._event_queue.qsize(),
            "sessions": {},
        }

        with self._lock:
            for name, session in self._sessions.items():
                try:
                    session_stats = session.stats()
                    result["sessions"][name] = {
                        "type": self._session_info[name].session_type,
                        "providers": self._session_info[name].providers,
                        "is_running": self._session_info[name].is_running,
                        "stats": session_stats,
                    }
                except Exception:
                    result["sessions"][name] = {
                        "type": self._session_info[name].session_type,
                        "providers": self._session_info[name].providers,
                        "is_running": self._session_info[name].is_running,
                        "stats": None,
                    }

        return result

    def __enter__(self) -> MultiSession:
        """Context manager entry."""
        return self.start()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Context manager exit."""
        self.stop()
        return False
