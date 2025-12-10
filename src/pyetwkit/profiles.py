"""Provider profiles for common use cases.

This module provides pre-configured provider profiles for common ETW monitoring scenarios
such as audio, network, GPU, and process monitoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ProviderConfig:
    """Configuration for a single ETW provider within a profile."""

    name: str
    """Provider name or GUID."""

    guid: str | None = None
    """Provider GUID (optional if name is sufficient)."""

    level: str | int = "verbose"
    """Trace level: critical, error, warning, information, verbose, or 0-5."""

    keywords: int | None = None
    """Keywords bitmask for filtering events."""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProviderConfig:
        """Create ProviderConfig from dictionary."""
        return cls(
            name=data.get("name", ""),
            guid=data.get("guid"),
            level=data.get("level", "verbose"),
            keywords=data.get("keywords"),
        )


@dataclass
class Profile:
    """A provider profile containing multiple provider configurations."""

    name: str
    """Profile name."""

    description: str = ""
    """Profile description."""

    providers: list[ProviderConfig] = field(default_factory=list)
    """List of provider configurations."""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Profile:
        """Create Profile from dictionary."""
        providers = [
            ProviderConfig.from_dict(p) if isinstance(p, dict) else p
            for p in data.get("providers", [])
        ]
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            providers=providers,
        )

    @classmethod
    def from_yaml(cls, yaml_str: str) -> Profile:
        """Create Profile from YAML string."""
        data = yaml.safe_load(yaml_str)
        return cls.from_dict(data)


# Built-in profiles
_BUILTIN_PROFILES: dict[str, Profile] = {}


def _init_builtin_profiles() -> None:
    """Initialize built-in profiles."""
    global _BUILTIN_PROFILES

    # Audio profile
    _BUILTIN_PROFILES["audio"] = Profile(
        name="audio",
        description="Audio-related providers (WASAPI, Media Foundation, Audio)",
        providers=[
            ProviderConfig(
                name="Microsoft-Windows-Audio",
                guid="ae4bd3be-f36f-45b6-8d21-bdd6fb832853",
                level="verbose",
            ),
            ProviderConfig(
                name="Microsoft-Windows-MediaFoundation-Platform",
                guid="bc97b970-d001-482f-8745-b8d7d5759f99",
                level="information",
            ),
            ProviderConfig(
                name="Microsoft-Windows-MMCSS",
                guid="36008301-e154-466c-acec-5f4cbd6b4694",
                level="verbose",
            ),
        ],
    )

    # Network profile
    _BUILTIN_PROFILES["network"] = Profile(
        name="network",
        description="Network-related providers (TCP/IP, DNS, NDIS)",
        providers=[
            ProviderConfig(
                name="Microsoft-Windows-TCPIP",
                guid="2f07e2ee-15db-40f1-90ef-9d7ba282188a",
                level="information",
            ),
            ProviderConfig(
                name="Microsoft-Windows-DNS-Client",
                guid="1c95126e-7eea-49a9-a3fe-a378b03ddb4d",
                level="information",
            ),
            ProviderConfig(
                name="Microsoft-Windows-NDIS",
                guid="cdead503-17f5-4a3e-b7ae-df8cc2902eb9",
                level="information",
            ),
        ],
    )

    # GPU profile
    _BUILTIN_PROFILES["gpu"] = Profile(
        name="gpu",
        description="GPU-related providers (DXGI, D3D, DWM)",
        providers=[
            ProviderConfig(
                name="Microsoft-Windows-DXGI",
                guid="ca11c036-0102-4a2d-a6ad-f03cfed5d3c9",
                level="information",
            ),
            ProviderConfig(
                name="Microsoft-Windows-D3D9",
                guid="783aca0a-790e-4d7f-8451-aa850511c6b9",
                level="information",
            ),
            ProviderConfig(
                name="Microsoft-Windows-Dwm-Core",
                guid="9e9bba3c-2e38-40cb-99f4-9e8281425164",
                level="information",
            ),
        ],
    )

    # Process profile
    _BUILTIN_PROFILES["process"] = Profile(
        name="process",
        description="Process-related providers (Kernel-Process)",
        providers=[
            ProviderConfig(
                name="Microsoft-Windows-Kernel-Process",
                guid="22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716",
                level="information",
                keywords=0x10,  # WINEVENT_KEYWORD_PROCESS
            ),
        ],
    )

    # File I/O profile
    _BUILTIN_PROFILES["file"] = Profile(
        name="file",
        description="File I/O related providers",
        providers=[
            ProviderConfig(
                name="Microsoft-Windows-Kernel-File",
                guid="edd08927-9cc4-4e65-b970-c2560fb5c289",
                level="information",
            ),
        ],
    )

    # Security profile
    _BUILTIN_PROFILES["security"] = Profile(
        name="security",
        description="Security-related providers",
        providers=[
            ProviderConfig(
                name="Microsoft-Windows-Security-Auditing",
                guid="54849625-5478-4994-a5ba-3e3b0328c30d",
                level="information",
            ),
        ],
    )

    # PowerShell profile
    _BUILTIN_PROFILES["powershell"] = Profile(
        name="powershell",
        description="PowerShell-related providers",
        providers=[
            ProviderConfig(
                name="Microsoft-Windows-PowerShell",
                guid="a0c1853b-5c40-4b15-8766-3cf1c58f985a",
                level="verbose",
            ),
        ],
    )


# Initialize built-in profiles
_init_builtin_profiles()


def get_profile(name: str) -> Profile | None:
    """Get a profile by name.

    Args:
        name: Profile name (e.g., "audio", "network", "gpu")

    Returns:
        Profile if found, None otherwise

    Example:
        >>> from pyetwkit.profiles import get_profile
        >>> profile = get_profile("audio")
        >>> print(profile.description)
    """
    return _BUILTIN_PROFILES.get(name)


def list_profiles() -> list[Profile]:
    """List all available profiles.

    Returns:
        List of all registered profiles

    Example:
        >>> from pyetwkit.profiles import list_profiles
        >>> for profile in list_profiles():
        ...     print(f"{profile.name}: {profile.description}")
    """
    return list(_BUILTIN_PROFILES.values())


def load_profile(path: str | Path) -> Profile:
    """Load a profile from a YAML file.

    Args:
        path: Path to YAML file

    Returns:
        Loaded Profile

    Example:
        >>> from pyetwkit.profiles import load_profile
        >>> profile = load_profile("my_profile.yaml")
    """
    path = Path(path)
    yaml_content = path.read_text(encoding="utf-8")
    profile = Profile.from_yaml(yaml_content)

    # Register the loaded profile
    _BUILTIN_PROFILES[profile.name] = profile

    return profile


def register_profile(profile: Profile) -> None:
    """Register a custom profile.

    Args:
        profile: Profile to register

    Example:
        >>> from pyetwkit.profiles import Profile, register_profile
        >>> profile = Profile(name="custom", providers=[...])
        >>> register_profile(profile)
    """
    _BUILTIN_PROFILES[profile.name] = profile


__all__ = [
    "Profile",
    "ProviderConfig",
    "get_profile",
    "list_profiles",
    "load_profile",
    "register_profile",
]
