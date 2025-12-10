"""Tests for dynamic provider switching functionality (v0.2.0 - #28)."""

import pytest


def check_extension_available() -> bool:
    """Check if native extension is available."""
    try:
        from pyetwkit import _core  # noqa: F401

        return True
    except ImportError:
        return False


# Skip all tests if native extension is not available
pytestmark = pytest.mark.skipif(
    not check_extension_available(),
    reason="Native extension not built",
)


class TestDynamicProviderAPI:
    """Tests for dynamic provider switching API."""

    def test_session_has_add_provider_method(self) -> None:
        """Test that session has add_provider method."""
        from pyetwkit._core import EtwSession

        session = EtwSession("DynamicTest")
        assert hasattr(session, "add_provider")
        assert callable(session.add_provider)

    def test_session_has_remove_provider_method(self) -> None:
        """Test that session has remove_provider method."""
        from pyetwkit._core import EtwSession

        session = EtwSession("DynamicTest")
        assert hasattr(session, "remove_provider")
        assert callable(session.remove_provider)

    def test_session_has_list_providers_method(self) -> None:
        """Test that session has method to list active providers."""
        from pyetwkit._core import EtwSession

        session = EtwSession("DynamicTest")
        # Could be list_providers, providers, or get_providers
        has_list = (
            hasattr(session, "list_providers")
            or hasattr(session, "providers")
            or hasattr(session, "get_providers")
        )
        assert has_list

    def test_add_provider_before_start(self) -> None:
        """Test adding provider before session starts."""
        from pyetwkit._core import EtwProvider, EtwSession

        session = EtwSession("DynamicTest")
        provider = EtwProvider(
            "22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716",
            "Microsoft-Windows-Kernel-Process",
        )
        # Should not raise
        session.add_provider(provider)

    def test_add_multiple_providers(self) -> None:
        """Test adding multiple providers."""
        from pyetwkit._core import EtwProvider, EtwSession

        session = EtwSession("DynamicTest")

        provider1 = EtwProvider(
            "22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716",
            "Microsoft-Windows-Kernel-Process",
        )
        provider2 = EtwProvider(
            "edd08927-9cc4-4e65-b970-c2560fb5c289",
            "Microsoft-Windows-Kernel-File",
        )

        session.add_provider(provider1)
        session.add_provider(provider2)
        # Should have both providers


class TestRemoveProvider:
    """Tests for removing providers."""

    def test_remove_provider_by_guid(self) -> None:
        """Test removing provider by GUID."""
        from pyetwkit._core import EtwProvider, EtwSession

        session = EtwSession("RemoveTest")
        provider = EtwProvider(
            "22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716",
            "Microsoft-Windows-Kernel-Process",
        )
        session.add_provider(provider)

        # Remove by GUID string
        result = session.remove_provider("22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716")
        # Should return True if removed, or not raise
        assert result is True or result is None

    def test_remove_nonexistent_provider(self) -> None:
        """Test removing provider that doesn't exist."""
        from pyetwkit._core import EtwSession

        session = EtwSession("RemoveTest")

        # Should return False or raise specific error
        try:
            result = session.remove_provider("00000000-0000-0000-0000-000000000000")
            assert result is False or result is None
        except (ValueError, KeyError):
            pass  # Also acceptable


@pytest.mark.admin
class TestDynamicProviderIntegration:
    """Integration tests for dynamic provider switching (require admin)."""

    def test_add_provider_while_running(self) -> None:
        """Test adding provider while session is running."""
        from pyetwkit._core import EtwProvider, EtwSession

        session = EtwSession("DynamicIntegrationTest")
        provider1 = EtwProvider(
            "22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716",
            "Microsoft-Windows-Kernel-Process",
        )

        session.add_provider(provider1)
        session.start()

        try:
            # Add second provider while running
            provider2 = EtwProvider(
                "edd08927-9cc4-4e65-b970-c2560fb5c289",
                "Microsoft-Windows-Kernel-File",
            )
            session.add_provider(provider2)

            # Both providers should now be active
            assert session.is_running()
        finally:
            session.stop()

    def test_remove_provider_while_running(self) -> None:
        """Test removing provider while session is running."""
        from pyetwkit._core import EtwProvider, EtwSession

        session = EtwSession("DynamicIntegrationTest")
        provider = EtwProvider(
            "22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716",
            "Microsoft-Windows-Kernel-Process",
        )

        session.add_provider(provider)
        session.start()

        try:
            # Remove provider while running
            session.remove_provider("22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716")
            # Session should still be running
            assert session.is_running()
        finally:
            session.stop()
