"""Tests for EtwListener (synchronous API)."""

import pytest

# Skip all tests if native extension is not available
pytestmark = pytest.mark.skipif(
    True,  # Will be replaced with actual import check
    reason="Native extension not built",
)


@pytest.fixture
def mock_session():
    """Mock EtwSession for testing without admin privileges."""
    # This would be replaced with actual mocking when testing
    pass


class TestEtwListener:
    """Tests for EtwListener class."""

    @pytest.mark.admin
    def test_listener_creation(self) -> None:
        """Test creating a listener."""
        from pyetwkit import EtwListener, EtwProvider

        provider = EtwProvider.dns_client()
        listener = EtwListener(providers=[provider])
        assert listener.name is not None
        assert not listener.is_running

    @pytest.mark.admin
    def test_listener_context_manager(self) -> None:
        """Test listener as context manager."""
        from pyetwkit import EtwListener, EtwProvider

        provider = EtwProvider.dns_client()
        with EtwListener(providers=[provider]) as listener:
            assert listener.is_running

        assert not listener.is_running

    @pytest.mark.admin
    def test_listener_start_stop(self) -> None:
        """Test manual start/stop."""
        from pyetwkit import EtwListener, EtwProvider

        provider = EtwProvider.kernel_process()
        listener = EtwListener(providers=[provider])

        listener.start()
        assert listener.is_running

        listener.stop()
        assert not listener.is_running

    @pytest.mark.admin
    def test_listener_double_start(self) -> None:
        """Test that double start raises error."""
        from pyetwkit import EtwListener, EtwProvider

        provider = EtwProvider.dns_client()
        listener = EtwListener(providers=[provider])
        listener.start()

        with pytest.raises(RuntimeError, match="already running"):
            listener.start()

        listener.stop()

    @pytest.mark.admin
    def test_listener_stats(self) -> None:
        """Test getting listener statistics."""
        from pyetwkit import EtwListener, EtwProvider

        provider = EtwProvider.dns_client()
        with EtwListener(providers=[provider]) as listener:
            stats = listener.stats()
            assert stats.events_received >= 0
            assert stats.events_lost >= 0

    @pytest.mark.admin
    def test_listener_repr(self) -> None:
        """Test listener string representation."""
        from pyetwkit import EtwListener, EtwProvider

        provider = EtwProvider.dns_client()
        listener = EtwListener(providers=[provider])

        repr_str = repr(listener)
        assert "EtwListener" in repr_str
        assert "stopped" in repr_str

    @pytest.mark.admin
    def test_events_without_start(self) -> None:
        """Test that iterating without start raises error."""
        from pyetwkit import EtwListener, EtwProvider

        provider = EtwProvider.dns_client()
        listener = EtwListener(providers=[provider])

        with pytest.raises(RuntimeError, match="not running"):
            for _ in listener.events(timeout=1.0, max_events=1):
                pass
