"""Tests for EtwStreamer (asynchronous API)."""

import pytest


def check_extension_available() -> bool:
    """Check if native extension is available."""
    try:
        from pyetwkit._core import EtwSession  # noqa: F401

        return True
    except ImportError:
        return False


# Skip all tests if native extension is not available
pytestmark = pytest.mark.skipif(
    not check_extension_available(),
    reason="Native extension not built",
)


class TestEtwStreamer:
    """Tests for EtwStreamer class."""

    @pytest.mark.admin
    @pytest.mark.asyncio
    async def test_streamer_creation(self) -> None:
        """Test creating a streamer."""
        from pyetwkit import EtwProvider, EtwStreamer

        provider = EtwProvider.dns_client()
        streamer = EtwStreamer(providers=[provider])
        assert streamer.name is not None
        assert not streamer.is_running

    @pytest.mark.admin
    @pytest.mark.asyncio
    async def test_streamer_context_manager(self) -> None:
        """Test streamer as async context manager."""
        from pyetwkit import EtwProvider, EtwStreamer

        provider = EtwProvider.dns_client()
        async with EtwStreamer(providers=[provider]) as streamer:
            assert streamer.is_running

        assert not streamer.is_running

    @pytest.mark.admin
    @pytest.mark.asyncio
    async def test_streamer_start_stop(self) -> None:
        """Test manual start/stop."""
        from pyetwkit import EtwProvider, EtwStreamer

        provider = EtwProvider.kernel_process()
        streamer = EtwStreamer(providers=[provider])

        await streamer.start()
        assert streamer.is_running

        await streamer.stop()
        assert not streamer.is_running

    @pytest.mark.admin
    @pytest.mark.asyncio
    async def test_streamer_double_start(self) -> None:
        """Test that double start raises error."""
        from pyetwkit import EtwProvider, EtwStreamer

        provider = EtwProvider.dns_client()
        streamer = EtwStreamer(providers=[provider])
        await streamer.start()

        with pytest.raises(RuntimeError, match="already running"):
            await streamer.start()

        await streamer.stop()

    @pytest.mark.admin
    @pytest.mark.asyncio
    async def test_streamer_stats(self) -> None:
        """Test getting streamer statistics."""
        from pyetwkit import EtwProvider, EtwStreamer

        provider = EtwProvider.dns_client()
        async with EtwStreamer(providers=[provider]) as streamer:
            stats = streamer.stats()
            assert stats.events_received >= 0
            assert stats.events_lost >= 0

    @pytest.mark.admin
    @pytest.mark.asyncio
    async def test_streamer_repr(self) -> None:
        """Test streamer string representation."""
        from pyetwkit import EtwProvider, EtwStreamer

        provider = EtwProvider.dns_client()
        streamer = EtwStreamer(providers=[provider])

        repr_str = repr(streamer)
        assert "EtwStreamer" in repr_str
        assert "stopped" in repr_str

    @pytest.mark.admin
    @pytest.mark.asyncio
    async def test_events_without_start(self) -> None:
        """Test that iterating without start raises error."""
        from pyetwkit import EtwProvider, EtwStreamer

        provider = EtwProvider.dns_client()
        streamer = EtwStreamer(providers=[provider])

        with pytest.raises(RuntimeError, match="not running"):
            async for _ in streamer.events(timeout=1.0, max_events=1):
                pass

    @pytest.mark.admin
    @pytest.mark.asyncio
    async def test_streamer_timeout(self) -> None:
        """Test streamer with timeout."""
        from pyetwkit import EtwProvider, EtwStreamer

        provider = EtwProvider.dns_client()
        async with EtwStreamer(providers=[provider]) as streamer:
            count = 0
            async for _ in streamer.events(timeout=1.0, max_events=10):
                count += 1
            # We may or may not receive events, but no error should occur
            assert count >= 0
