"""Tests for provider profiles (v1.0.0 - #16, #34)."""

from pathlib import Path


class TestProfileModule:
    """Tests for profiles module structure."""

    def test_profiles_module_exists(self) -> None:
        """Test that pyetwkit.profiles module exists."""
        from pyetwkit import profiles  # noqa: F401

        assert True

    def test_load_profile_function_exists(self) -> None:
        """Test that load_profile function exists."""
        from pyetwkit.profiles import load_profile

        assert callable(load_profile)

    def test_get_profile_function_exists(self) -> None:
        """Test that get_profile function exists."""
        from pyetwkit.profiles import get_profile

        assert callable(get_profile)

    def test_list_profiles_function_exists(self) -> None:
        """Test that list_profiles function exists."""
        from pyetwkit.profiles import list_profiles

        assert callable(list_profiles)


class TestBuiltinProfiles:
    """Tests for built-in provider profiles."""

    def test_audio_profile_exists(self) -> None:
        """Test that audio profile is available."""
        from pyetwkit.profiles import get_profile

        profile = get_profile("audio")
        assert profile is not None
        assert profile.name == "audio"

    def test_network_profile_exists(self) -> None:
        """Test that network profile is available."""
        from pyetwkit.profiles import get_profile

        profile = get_profile("network")
        assert profile is not None
        assert profile.name == "network"

    def test_gpu_profile_exists(self) -> None:
        """Test that gpu profile is available."""
        from pyetwkit.profiles import get_profile

        profile = get_profile("gpu")
        assert profile is not None
        assert profile.name == "gpu"

    def test_process_profile_exists(self) -> None:
        """Test that process profile is available."""
        from pyetwkit.profiles import get_profile

        profile = get_profile("process")
        assert profile is not None
        assert profile.name == "process"

    def test_list_profiles_returns_builtin(self) -> None:
        """Test that list_profiles returns built-in profiles."""
        from pyetwkit.profiles import list_profiles

        profiles = list_profiles()
        assert len(profiles) >= 4
        names = [p.name for p in profiles]
        assert "audio" in names
        assert "network" in names


class TestProfileStructure:
    """Tests for Profile data structure."""

    def test_profile_has_name(self) -> None:
        """Test that Profile has name attribute."""
        from pyetwkit.profiles import get_profile

        profile = get_profile("audio")
        assert hasattr(profile, "name")
        assert isinstance(profile.name, str)

    def test_profile_has_description(self) -> None:
        """Test that Profile has description attribute."""
        from pyetwkit.profiles import get_profile

        profile = get_profile("audio")
        assert hasattr(profile, "description")

    def test_profile_has_providers(self) -> None:
        """Test that Profile has providers list."""
        from pyetwkit.profiles import get_profile

        profile = get_profile("audio")
        assert hasattr(profile, "providers")
        assert isinstance(profile.providers, list)
        assert len(profile.providers) > 0

    def test_provider_entry_has_required_fields(self) -> None:
        """Test that provider entry has required fields."""
        from pyetwkit.profiles import get_profile

        profile = get_profile("audio")
        provider = profile.providers[0]
        # Should have name or guid
        assert hasattr(provider, "name") or hasattr(provider, "guid")


class TestCustomProfiles:
    """Tests for custom profile loading."""

    def test_load_profile_from_yaml(self, tmp_path: Path) -> None:
        """Test loading profile from YAML file."""
        from pyetwkit.profiles import load_profile

        yaml_content = """
name: test_profile
description: Test profile for unit tests
providers:
  - name: Microsoft-Windows-Kernel-Process
    level: verbose
"""
        yaml_file = tmp_path / "test_profile.yaml"
        yaml_file.write_text(yaml_content)

        profile = load_profile(str(yaml_file))
        assert profile.name == "test_profile"
        assert len(profile.providers) == 1

    def test_load_profile_from_dict(self) -> None:
        """Test loading profile from dictionary."""
        from pyetwkit.profiles import Profile

        data = {
            "name": "dict_profile",
            "description": "Profile from dict",
            "providers": [{"name": "Microsoft-Windows-Kernel-Process", "level": "verbose"}],
        }

        profile = Profile.from_dict(data)
        assert profile.name == "dict_profile"

    def test_get_nonexistent_profile_returns_none(self) -> None:
        """Test that getting non-existent profile returns None."""
        from pyetwkit.profiles import get_profile

        profile = get_profile("nonexistent_profile_xyz")
        assert profile is None


class TestProfileProviderConfig:
    """Tests for provider configuration in profiles."""

    def test_provider_config_has_level(self) -> None:
        """Test that provider config can have level."""
        from pyetwkit.profiles import get_profile

        profile = get_profile("audio")
        provider = profile.providers[0]
        # Level should be accessible
        assert (
            hasattr(provider, "level")
            or provider.level is None
            or isinstance(provider.level, (str, int))
        )

    def test_provider_config_has_keywords(self) -> None:
        """Test that provider config can have keywords."""
        from pyetwkit.profiles import get_profile

        profile = get_profile("process")
        provider = profile.providers[0]
        # Keywords should be accessible (may be None)
        assert hasattr(provider, "keywords")
