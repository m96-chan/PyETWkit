"""Provider discovery example.

This example shows how to discover and search for
ETW providers on the system.
"""

from pyetwkit._core import get_provider_info, list_providers, search_providers


def main():
    # List all providers (limited to first 10)
    print("=== First 10 ETW Providers ===")
    providers = list_providers()[:10]
    for p in providers:
        print(f"  {p.name}")
        print(f"    GUID: {p.guid}")
        print(f"    Source: {p.source}")

    # Search for specific providers
    print("\n=== Searching for 'Kernel' providers ===")
    kernel_providers = search_providers("Kernel")[:5]
    for p in kernel_providers:
        print(f"  {p.name}")

    # Get detailed info about a specific provider
    print("\n=== Provider Details: Microsoft-Windows-Kernel-Process ===")
    info = get_provider_info("Microsoft-Windows-Kernel-Process")
    if info:
        print(f"  Name: {info.name}")
        print(f"  GUID: {info.guid}")
        print(f"  Source: {info.source}")

    # Search for DNS-related providers
    print("\n=== DNS-related providers ===")
    dns_providers = search_providers("DNS")
    for p in dns_providers:
        print(f"  {p.name}")


if __name__ == "__main__":
    main()
