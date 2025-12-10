"""Tests for core functionality (requires native extension)."""

import pytest


def check_extension_available() -> bool:
    """Check if native extension is available."""
    try:
        from pyetwkit._core import EtwEvent, EtwProvider, EtwSession  # noqa: F401

        return True
    except ImportError:
        return False


# Skip all tests if native extension is not available
pytestmark = pytest.mark.skipif(
    not check_extension_available(),
    reason="Native extension not built",
)


class TestEtwProvider:
    """Tests for EtwProvider class."""

    def test_provider_from_guid(self) -> None:
        """Test creating provider from GUID string."""
        from pyetwkit._core import EtwProvider

        provider = EtwProvider("22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716", "Test Provider")
        assert provider.guid == "22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716"
        assert provider.name == "Test Provider"

    def test_provider_invalid_guid(self) -> None:
        """Test that invalid GUID raises error."""
        from pyetwkit._core import EtwProvider

        with pytest.raises(ValueError):
            EtwProvider("invalid-guid")

    def test_provider_kernel_process(self) -> None:
        """Test kernel process provider factory."""
        from pyetwkit._core import EtwProvider

        provider = EtwProvider.kernel_process()
        assert provider.name == "Microsoft-Windows-Kernel-Process"

    def test_provider_dns_client(self) -> None:
        """Test DNS client provider factory."""
        from pyetwkit._core import EtwProvider

        provider = EtwProvider.dns_client()
        assert provider.name == "Microsoft-Windows-DNS-Client"

    def test_provider_powershell(self) -> None:
        """Test PowerShell provider factory."""
        from pyetwkit._core import EtwProvider

        provider = EtwProvider.powershell()
        assert provider.name == "Microsoft-Windows-PowerShell"

    def test_provider_chaining(self) -> None:
        """Test method chaining on provider."""
        from pyetwkit._core import EtwProvider

        provider = (
            EtwProvider("22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716")
            .level(4)
            .keywords_any(0xFF)
            .event_ids([1, 2, 3])
        )
        # Should not raise
        assert provider is not None


class TestEventFilter:
    """Tests for EventFilter class."""

    def test_filter_creation(self) -> None:
        """Test creating a filter."""
        from pyetwkit._core import EventFilter

        f = EventFilter()
        assert f is not None

    def test_filter_event_ids(self) -> None:
        """Test event ID filtering."""
        from pyetwkit._core import EventFilter

        f = EventFilter().event_ids([1, 2, 3])
        assert f.matches(1, 0)
        assert f.matches(2, 0)
        assert not f.matches(4, 0)

    def test_filter_opcodes(self) -> None:
        """Test opcode filtering."""
        from pyetwkit._core import EventFilter

        f = EventFilter().opcodes([10, 20])
        assert f.matches(0, 10)
        assert f.matches(0, 20)
        assert not f.matches(0, 30)

    def test_filter_chaining(self) -> None:
        """Test filter chaining."""
        from pyetwkit._core import EventFilter

        f = EventFilter().event_ids([1, 2]).opcodes([10]).process_id(1234)
        # Should match event_id=1, opcode=10
        assert f.matches(1, 10)
        # Should not match event_id=3
        assert not f.matches(3, 10)


class TestEtwSession:
    """Tests for EtwSession class."""

    def test_session_creation(self) -> None:
        """Test creating a session."""
        from pyetwkit._core import EtwSession

        session = EtwSession("TestSession")
        assert session.name == "TestSession"
        assert not session.is_running()

    def test_session_with_config(self) -> None:
        """Test creating session with config."""
        from pyetwkit._core import EtwSession

        session = EtwSession.with_config(
            name="ConfiguredSession",
            buffer_size_kb=128,
            channel_capacity=5000,
        )
        assert session.name == "ConfiguredSession"

    def test_session_add_provider(self) -> None:
        """Test adding provider to session."""
        from pyetwkit._core import EtwProvider, EtwSession

        session = EtwSession("TestSession")
        provider = EtwProvider.dns_client()
        session.add_provider(provider)
        # Should not raise

    @pytest.mark.admin
    def test_session_start_stop(self) -> None:
        """Test starting and stopping session."""
        from pyetwkit._core import EtwProvider, EtwSession

        session = EtwSession("PyETWkit-Test")
        session.add_provider(EtwProvider.dns_client())

        session.start()
        assert session.is_running()

        session.stop()
        assert not session.is_running()

    @pytest.mark.admin
    def test_session_stats(self) -> None:
        """Test getting session statistics."""
        from pyetwkit._core import EtwProvider, EtwSession

        session = EtwSession("PyETWkit-Stats-Test")
        session.add_provider(EtwProvider.dns_client())
        session.start()

        stats = session.stats()
        assert stats.events_received >= 0
        assert stats.buffer_size_kb > 0

        session.stop()

    @pytest.mark.admin
    def test_session_context_manager(self) -> None:
        """Test session as context manager."""
        from pyetwkit._core import EtwProvider, EtwSession

        with EtwSession("PyETWkit-Context-Test") as session:
            session.add_provider(EtwProvider.dns_client())
            session.start()
            assert session.is_running()

        # Session should be stopped after exiting context
