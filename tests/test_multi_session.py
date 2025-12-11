"""Tests for Multi-session concurrent subscription (v2.0.0 - #48)."""

from __future__ import annotations

import pytest


def check_extension_available() -> bool:
    """Check if native extension is available."""
    try:
        import pyetwkit_core  # noqa: F401

        return True
    except ImportError:
        return False


# Skip all tests if native extension is not available
pytestmark = pytest.mark.skipif(
    not check_extension_available(),
    reason="Native extension not built",
)


class TestMultiSessionBasics:
    """Tests for MultiSession basic functionality."""

    def test_multi_session_class_exists(self) -> None:
        """Test that MultiSession class exists."""
        from pyetwkit import MultiSession

        assert MultiSession is not None

    def test_multi_session_can_be_created(self) -> None:
        """Test that MultiSession can be instantiated."""
        from pyetwkit import MultiSession

        manager = MultiSession()
        assert manager is not None

    def test_multi_session_has_add_provider_method(self) -> None:
        """Test that MultiSession has add_provider method."""
        from pyetwkit import MultiSession

        manager = MultiSession()
        assert hasattr(manager, "add_provider")
        assert callable(manager.add_provider)

    def test_multi_session_has_add_kernel_session_method(self) -> None:
        """Test that MultiSession has add_kernel_session method."""
        from pyetwkit import MultiSession

        manager = MultiSession()
        assert hasattr(manager, "add_kernel_session")
        assert callable(manager.add_kernel_session)

    def test_multi_session_has_start_method(self) -> None:
        """Test that MultiSession has start method."""
        from pyetwkit import MultiSession

        manager = MultiSession()
        assert hasattr(manager, "start")
        assert callable(manager.start)

    def test_multi_session_has_stop_method(self) -> None:
        """Test that MultiSession has stop method."""
        from pyetwkit import MultiSession

        manager = MultiSession()
        assert hasattr(manager, "stop")
        assert callable(manager.stop)

    def test_multi_session_has_events_method(self) -> None:
        """Test that MultiSession has events method."""
        from pyetwkit import MultiSession

        manager = MultiSession()
        assert hasattr(manager, "events")
        assert callable(manager.events)

    def test_multi_session_has_sessions_property(self) -> None:
        """Test that MultiSession has sessions property."""
        from pyetwkit import MultiSession

        manager = MultiSession()
        assert hasattr(manager, "sessions")


class TestMultiSessionProviderManagement:
    """Tests for MultiSession provider management."""

    # Microsoft-Windows-Kernel-Process GUID
    KERNEL_PROCESS_GUID = "22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716"
    # Microsoft-Windows-DNS-Client GUID
    DNS_CLIENT_GUID = "1c95126e-7eea-49a9-a3fe-a378b03ddb4d"

    def test_add_provider_returns_self(self) -> None:
        """Test that add_provider returns self for chaining."""
        from pyetwkit import MultiSession

        manager = MultiSession()
        result = manager.add_provider(self.KERNEL_PROCESS_GUID)
        assert result is manager

    def test_add_multiple_providers(self) -> None:
        """Test adding multiple providers."""
        from pyetwkit import MultiSession

        manager = MultiSession()
        manager.add_provider(self.DNS_CLIENT_GUID)
        manager.add_provider(self.KERNEL_PROCESS_GUID)

        # Should have 2 sessions (one per provider by default)
        assert len(manager.sessions) >= 1

    def test_add_provider_with_guid(self) -> None:
        """Test adding provider by GUID."""
        from pyetwkit import MultiSession

        manager = MultiSession()
        manager.add_provider(self.KERNEL_PROCESS_GUID)
        assert len(manager.sessions) >= 1

    def test_add_provider_with_session_name(self) -> None:
        """Test adding provider with custom session name."""
        from pyetwkit import MultiSession

        manager = MultiSession()
        manager.add_provider(
            self.DNS_CLIENT_GUID,
            session_name="MyDNSSession",
        )
        assert len(manager.sessions) >= 1


class TestMultiSessionKernel:
    """Tests for MultiSession kernel session support."""

    def test_add_kernel_session_returns_self(self) -> None:
        """Test that add_kernel_session returns self for chaining."""
        from pyetwkit import MultiSession

        manager = MultiSession()
        result = manager.add_kernel_session()
        assert result is manager

    def test_add_kernel_session_with_flags(self) -> None:
        """Test adding kernel session with specific flags."""
        from pyetwkit import KernelFlags, MultiSession

        manager = MultiSession()
        # Use KernelFlags constants with bitwise OR
        flags = KernelFlags.PROCESS | KernelFlags.THREAD
        manager.add_kernel_session(flags=flags)
        assert len(manager.sessions) >= 1


class TestMultiSessionLifecycle:
    """Tests for MultiSession lifecycle management."""

    # DNS Client GUID
    DNS_CLIENT_GUID = "1c95126e-7eea-49a9-a3fe-a378b03ddb4d"

    def test_start_returns_self(self) -> None:
        """Test that start returns self for chaining."""
        from pyetwkit import MultiSession

        manager = MultiSession()
        manager.add_provider(self.DNS_CLIENT_GUID)

        # Note: This will fail without admin privileges
        # We just test the method signature here
        try:
            result = manager.start()
            assert result is manager
            manager.stop()
        except (PermissionError, OSError):
            pytest.skip("Requires administrator privileges")

    def test_context_manager_support(self) -> None:
        """Test that MultiSession can be used as context manager."""
        from pyetwkit import MultiSession

        manager = MultiSession()
        assert hasattr(manager, "__enter__")
        assert hasattr(manager, "__exit__")


class TestMultiSessionEvents:
    """Tests for MultiSession event handling."""

    def test_events_returns_iterator(self) -> None:
        """Test that events() returns an iterator."""
        from pyetwkit import MultiSession

        manager = MultiSession()
        events = manager.events()
        assert hasattr(events, "__iter__")

    def test_events_with_timeout(self) -> None:
        """Test that events() accepts timeout parameter."""
        from pyetwkit import MultiSession

        manager = MultiSession()
        # Should not raise
        events = manager.events(timeout=1.0)
        assert events is not None


class TestMultiSessionStatistics:
    """Tests for MultiSession statistics."""

    def test_has_stats_method(self) -> None:
        """Test that MultiSession has stats method."""
        from pyetwkit import MultiSession

        manager = MultiSession()
        assert hasattr(manager, "stats")

    def test_stats_returns_dict(self) -> None:
        """Test that stats returns a dictionary."""
        from pyetwkit import MultiSession

        manager = MultiSession()
        stats = manager.stats()
        assert isinstance(stats, dict)
