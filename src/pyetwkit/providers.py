"""
Pre-configured ETW providers for common use cases.

These providers come with sensible defaults and are ready to use
without needing to know specific GUIDs or keywords.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyetwkit._core import EtwProvider


class KernelProvider:
    """Factory for kernel-related ETW providers."""

    # Provider GUIDs for kernel events
    KERNEL_PROCESS = "22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716"
    KERNEL_FILE = "edd08927-9cc4-4e65-b970-c2560fb5c289"
    KERNEL_NETWORK = "7dd42a49-5329-4832-8dfd-43d979153a88"
    KERNEL_REGISTRY = "70eb4f03-c1de-4f73-a051-33d13d5413bd"
    KERNEL_MEMORY = "d1d93ef7-e1f2-4f45-9943-03d245fe6c00"
    KERNEL_DISK_IO = "3d6fa8d4-fe05-11d0-9dda-00c04fd7ba7c"

    @classmethod
    def process(cls) -> EtwProvider:
        """Create a provider for kernel process events.

        Captures process creation, termination, and related events.
        """
        from pyetwkit._core import EtwProvider

        return EtwProvider(cls.KERNEL_PROCESS, "Microsoft-Windows-Kernel-Process")

    @classmethod
    def file(cls) -> EtwProvider:
        """Create a provider for kernel file events.

        Captures file creation, deletion, read, write operations.
        """
        from pyetwkit._core import EtwProvider

        return EtwProvider(cls.KERNEL_FILE, "Microsoft-Windows-Kernel-File")

    @classmethod
    def network(cls) -> EtwProvider:
        """Create a provider for kernel network events.

        Captures network connections, data transfer events.
        """
        from pyetwkit._core import EtwProvider

        return EtwProvider(cls.KERNEL_NETWORK, "Microsoft-Windows-Kernel-Network")

    @classmethod
    def registry(cls) -> EtwProvider:
        """Create a provider for kernel registry events.

        Captures registry key/value operations.
        """
        from pyetwkit._core import EtwProvider

        return EtwProvider(cls.KERNEL_REGISTRY, "Microsoft-Windows-Kernel-Registry")


class ProcessProvider:
    """Factory for process-related ETW providers."""

    PROCESS_GUID = "22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716"

    # Event IDs
    PROCESS_START = 1
    PROCESS_STOP = 2
    THREAD_START = 3
    THREAD_STOP = 4
    IMAGE_LOAD = 5
    IMAGE_UNLOAD = 6

    @classmethod
    def all(cls) -> EtwProvider:
        """Create a provider for all process events."""
        from pyetwkit._core import EtwProvider

        return EtwProvider(cls.PROCESS_GUID, "Microsoft-Windows-Kernel-Process")

    @classmethod
    def process_lifecycle(cls) -> EtwProvider:
        """Create a provider for process start/stop events only."""
        from pyetwkit._core import EtwProvider

        provider = EtwProvider(cls.PROCESS_GUID, "Microsoft-Windows-Kernel-Process")
        return provider.event_ids([cls.PROCESS_START, cls.PROCESS_STOP])

    @classmethod
    def image_loads(cls) -> EtwProvider:
        """Create a provider for DLL/image load events only."""
        from pyetwkit._core import EtwProvider

        provider = EtwProvider(cls.PROCESS_GUID, "Microsoft-Windows-Kernel-Process")
        return provider.event_ids([cls.IMAGE_LOAD, cls.IMAGE_UNLOAD])


class NetworkProvider:
    """Factory for network-related ETW providers."""

    DNS_CLIENT = "1c95126e-7eea-49a9-a3fe-a378b03ddb4d"
    TCPIP = "2f07e2ee-15db-40f1-90ef-9d7ba282188a"
    WINSOCK_AFD = "e53c6823-7bb8-44bb-90dc-3f86090d48a6"

    @classmethod
    def dns(cls) -> EtwProvider:
        """Create a provider for DNS query events."""
        from pyetwkit._core import EtwProvider

        return EtwProvider(cls.DNS_CLIENT, "Microsoft-Windows-DNS-Client")

    @classmethod
    def tcpip(cls) -> EtwProvider:
        """Create a provider for TCP/IP events."""
        from pyetwkit._core import EtwProvider

        return EtwProvider(cls.TCPIP, "Microsoft-Windows-TCPIP")

    @classmethod
    def winsock(cls) -> EtwProvider:
        """Create a provider for Winsock events."""
        from pyetwkit._core import EtwProvider

        return EtwProvider(cls.WINSOCK_AFD, "Microsoft-Windows-Winsock-AFD")


class FileProvider:
    """Factory for file-related ETW providers."""

    KERNEL_FILE = "edd08927-9cc4-4e65-b970-c2560fb5c289"
    NTFS = "dd70bc80-ef44-421b-8ac3-cd31da613a4e"

    @classmethod
    def kernel(cls) -> EtwProvider:
        """Create a provider for kernel file events."""
        from pyetwkit._core import EtwProvider

        return EtwProvider(cls.KERNEL_FILE, "Microsoft-Windows-Kernel-File")

    @classmethod
    def ntfs(cls) -> EtwProvider:
        """Create a provider for NTFS events."""
        from pyetwkit._core import EtwProvider

        return EtwProvider(cls.NTFS, "Microsoft-Windows-Ntfs")


class RegistryProvider:
    """Factory for registry-related ETW providers."""

    KERNEL_REGISTRY = "70eb4f03-c1de-4f73-a051-33d13d5413bd"

    @classmethod
    def all(cls) -> EtwProvider:
        """Create a provider for all registry events."""
        from pyetwkit._core import EtwProvider

        return EtwProvider(cls.KERNEL_REGISTRY, "Microsoft-Windows-Kernel-Registry")


class SecurityProvider:
    """Factory for security-related ETW providers."""

    SECURITY_AUDITING = "54849625-5478-4994-a5ba-3e3b0328c30d"
    THREAT_INTELLIGENCE = "f4e1897c-bb5d-5668-f1d8-040f4d8dd344"

    @classmethod
    def auditing(cls) -> EtwProvider:
        """Create a provider for security auditing events."""
        from pyetwkit._core import EtwProvider

        return EtwProvider(cls.SECURITY_AUDITING, "Microsoft-Windows-Security-Auditing")

    @classmethod
    def threat_intelligence(cls) -> EtwProvider:
        """Create a provider for threat intelligence events (ETW-TI).

        Note: Requires special privileges and may not be available on all systems.
        """
        from pyetwkit._core import EtwProvider

        return EtwProvider(cls.THREAT_INTELLIGENCE, "Microsoft-Windows-Threat-Intelligence")


class PowerShellProvider:
    """Factory for PowerShell-related ETW providers."""

    POWERSHELL = "a0c1853b-5c40-4b15-8766-3cf1c58f985a"
    POWERSHELL_OPERATIONAL = "fb4a3e52-c5f9-4d73-b8f6-7af4c4d2f15a"

    @classmethod
    def all(cls) -> EtwProvider:
        """Create a provider for all PowerShell events."""
        from pyetwkit._core import EtwProvider

        return EtwProvider(cls.POWERSHELL, "Microsoft-Windows-PowerShell")


class DotNetProvider:
    """Factory for .NET-related ETW providers."""

    CLR = "e13c0d23-ccbc-4e12-931b-d9cc2eee27e4"
    CLR_RUNDOWN = "a669021c-c450-4609-a035-5af59af4df18"

    @classmethod
    def clr(cls) -> EtwProvider:
        """Create a provider for CLR events."""
        from pyetwkit._core import EtwProvider

        return EtwProvider(cls.CLR, "Microsoft-Windows-DotNETRuntime")

    @classmethod
    def clr_rundown(cls) -> EtwProvider:
        """Create a provider for CLR rundown events."""
        from pyetwkit._core import EtwProvider

        return EtwProvider(cls.CLR_RUNDOWN, "Microsoft-Windows-DotNETRuntimeRundown")
