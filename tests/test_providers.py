"""Tests for provider factory classes."""

# These tests don't require the native extension
from pyetwkit.providers import (
    DotNetProvider,
    FileProvider,
    KernelProvider,
    NetworkProvider,
    PowerShellProvider,
    ProcessProvider,
    RegistryProvider,
    SecurityProvider,
)


class TestKernelProvider:
    """Tests for KernelProvider factory."""

    def test_process_guid(self) -> None:
        """Test kernel process GUID is valid."""
        assert KernelProvider.KERNEL_PROCESS == "22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716"

    def test_file_guid(self) -> None:
        """Test kernel file GUID is valid."""
        assert KernelProvider.KERNEL_FILE == "edd08927-9cc4-4e65-b970-c2560fb5c289"

    def test_network_guid(self) -> None:
        """Test kernel network GUID is valid."""
        assert KernelProvider.KERNEL_NETWORK == "7dd42a49-5329-4832-8dfd-43d979153a88"

    def test_registry_guid(self) -> None:
        """Test kernel registry GUID is valid."""
        assert KernelProvider.KERNEL_REGISTRY == "70eb4f03-c1de-4f73-a051-33d13d5413bd"


class TestProcessProvider:
    """Tests for ProcessProvider factory."""

    def test_event_ids(self) -> None:
        """Test process event IDs are defined."""
        assert ProcessProvider.PROCESS_START == 1
        assert ProcessProvider.PROCESS_STOP == 2
        assert ProcessProvider.THREAD_START == 3
        assert ProcessProvider.THREAD_STOP == 4
        assert ProcessProvider.IMAGE_LOAD == 5
        assert ProcessProvider.IMAGE_UNLOAD == 6


class TestNetworkProvider:
    """Tests for NetworkProvider factory."""

    def test_dns_guid(self) -> None:
        """Test DNS client GUID is valid."""
        assert NetworkProvider.DNS_CLIENT == "1c95126e-7eea-49a9-a3fe-a378b03ddb4d"

    def test_tcpip_guid(self) -> None:
        """Test TCP/IP GUID is valid."""
        assert NetworkProvider.TCPIP == "2f07e2ee-15db-40f1-90ef-9d7ba282188a"


class TestFileProvider:
    """Tests for FileProvider factory."""

    def test_kernel_file_guid(self) -> None:
        """Test kernel file GUID is valid."""
        assert FileProvider.KERNEL_FILE == "edd08927-9cc4-4e65-b970-c2560fb5c289"

    def test_ntfs_guid(self) -> None:
        """Test NTFS GUID is valid."""
        assert FileProvider.NTFS == "dd70bc80-ef44-421b-8ac3-cd31da613a4e"


class TestRegistryProvider:
    """Tests for RegistryProvider factory."""

    def test_kernel_registry_guid(self) -> None:
        """Test kernel registry GUID is valid."""
        assert RegistryProvider.KERNEL_REGISTRY == "70eb4f03-c1de-4f73-a051-33d13d5413bd"


class TestSecurityProvider:
    """Tests for SecurityProvider factory."""

    def test_security_auditing_guid(self) -> None:
        """Test security auditing GUID is valid."""
        assert SecurityProvider.SECURITY_AUDITING == "54849625-5478-4994-a5ba-3e3b0328c30d"

    def test_threat_intelligence_guid(self) -> None:
        """Test threat intelligence GUID is valid."""
        assert SecurityProvider.THREAT_INTELLIGENCE == "f4e1897c-bb5d-5668-f1d8-040f4d8dd344"


class TestPowerShellProvider:
    """Tests for PowerShellProvider factory."""

    def test_powershell_guid(self) -> None:
        """Test PowerShell GUID is valid."""
        assert PowerShellProvider.POWERSHELL == "a0c1853b-5c40-4b15-8766-3cf1c58f985a"


class TestDotNetProvider:
    """Tests for DotNetProvider factory."""

    def test_clr_guid(self) -> None:
        """Test CLR GUID is valid."""
        assert DotNetProvider.CLR == "e13c0d23-ccbc-4e12-931b-d9cc2eee27e4"

    def test_clr_rundown_guid(self) -> None:
        """Test CLR rundown GUID is valid."""
        assert DotNetProvider.CLR_RUNDOWN == "a669021c-c450-4609-a035-5af59af4df18"
