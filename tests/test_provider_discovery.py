"""Tests for provider discovery functionality (v0.2.0 - #12, #35)."""

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


class TestListProviders:
    """Tests for list_providers function."""

    def test_list_providers_returns_list(self) -> None:
        """Test that list_providers returns a non-empty list."""
        import pyetwkit_core

        providers = pyetwkit_core.list_providers()
        assert isinstance(providers, list)
        assert len(providers) > 0

    def test_list_providers_contains_kernel_process(self) -> None:
        """Test that kernel process provider is in the list."""
        import pyetwkit_core

        providers = pyetwkit_core.list_providers()
        names = [p.name for p in providers]
        # At least one kernel provider should exist
        kernel_providers = [n for n in names if "Kernel" in n]
        assert len(kernel_providers) > 0

    def test_provider_info_has_guid(self) -> None:
        """Test that provider info includes GUID."""
        import pyetwkit_core

        providers = pyetwkit_core.list_providers()
        assert len(providers) > 0
        provider = providers[0]
        assert hasattr(provider, "guid")
        assert isinstance(provider.guid, str)
        # GUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        assert len(provider.guid) == 36

    def test_provider_info_has_name(self) -> None:
        """Test that provider info includes name."""
        import pyetwkit_core

        providers = pyetwkit_core.list_providers()
        assert len(providers) > 0
        provider = providers[0]
        assert hasattr(provider, "name")
        assert isinstance(provider.name, str)


class TestSearchProviders:
    """Tests for search_providers function."""

    def test_search_providers_by_keyword(self) -> None:
        """Test searching providers by keyword."""
        import pyetwkit_core

        results = pyetwkit_core.search_providers("Kernel")
        assert isinstance(results, list)
        # All results should contain "Kernel" in the name
        for provider in results:
            assert "Kernel" in provider.name or "kernel" in provider.name.lower()

    def test_search_providers_case_insensitive(self) -> None:
        """Test that search is case insensitive."""
        import pyetwkit_core

        results_lower = pyetwkit_core.search_providers("kernel")
        results_upper = pyetwkit_core.search_providers("KERNEL")
        # Should return same providers regardless of case
        assert len(results_lower) == len(results_upper)

    def test_search_providers_no_match(self) -> None:
        """Test searching with no matching providers."""
        import pyetwkit_core

        results = pyetwkit_core.search_providers("xyznonexistent123")
        assert isinstance(results, list)
        assert len(results) == 0


class TestGetProviderInfo:
    """Tests for get_provider_info function."""

    def test_get_provider_info_by_name(self) -> None:
        """Test getting provider info by name."""
        import pyetwkit_core

        info = pyetwkit_core.get_provider_info("Microsoft-Windows-Kernel-Process")
        assert info is not None
        assert info.name == "Microsoft-Windows-Kernel-Process"
        assert info.guid == "22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716"

    def test_get_provider_info_by_guid(self) -> None:
        """Test getting provider info by GUID."""
        import pyetwkit_core

        info = pyetwkit_core.get_provider_info("22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716")
        assert info is not None
        assert "Kernel" in info.name or "Process" in info.name

    def test_get_provider_info_not_found(self) -> None:
        """Test getting info for non-existent provider."""
        import pyetwkit_core

        info = pyetwkit_core.get_provider_info("nonexistent-provider")
        assert info is None

    def test_get_provider_info_has_keywords(self) -> None:
        """Test that provider info includes keywords."""
        import pyetwkit_core

        info = pyetwkit_core.get_provider_info("Microsoft-Windows-Kernel-Process")
        assert info is not None
        assert hasattr(info, "keywords")
        # keywords should be a list or dict
        assert isinstance(info.keywords, (list, dict))


class TestProviderInfo:
    """Tests for ProviderInfo class."""

    def test_provider_info_repr(self) -> None:
        """Test ProviderInfo string representation."""
        import pyetwkit_core

        providers = pyetwkit_core.list_providers()
        assert len(providers) > 0
        repr_str = repr(providers[0])
        assert "ProviderInfo" in repr_str or providers[0].name in repr_str

    def test_provider_info_equality(self) -> None:
        """Test ProviderInfo equality comparison."""
        import pyetwkit_core

        providers1 = pyetwkit_core.list_providers()
        providers2 = pyetwkit_core.list_providers()
        # Same provider should be equal
        assert providers1[0].guid == providers2[0].guid
