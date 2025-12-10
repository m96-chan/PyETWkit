Provider Profiles
=================

PyETWkit includes pre-configured provider profiles for common monitoring scenarios.

Built-in Profiles
-----------------

audio
~~~~~

Audio-related providers for monitoring WASAPI, Media Foundation, and MMCSS.

**Providers:**

- Microsoft-Windows-Audio
- Microsoft-Windows-MediaFoundation-Platform
- Microsoft-Windows-MMCSS

**Use cases:**

- Audio latency debugging
- Media playback issues
- Audio device problems

.. code-block:: python

   with EtwListener(profile="audio") as listener:
       for event in listener:
           print(event)

network
~~~~~~~

Network-related providers for TCP/IP, DNS, and NDIS monitoring.

**Providers:**

- Microsoft-Windows-TCPIP
- Microsoft-Windows-DNS-Client
- Microsoft-Windows-NDIS

**Use cases:**

- Network connectivity issues
- DNS resolution problems
- Network performance analysis

gpu
~~~

GPU-related providers for DXGI, D3D, and DWM monitoring.

**Providers:**

- Microsoft-Windows-DXGI
- Microsoft-Windows-D3D9
- Microsoft-Windows-Dwm-Core

**Use cases:**

- GPU performance issues
- Display problems
- Graphics debugging

process
~~~~~~~

Process-related providers for monitoring process creation and termination.

**Providers:**

- Microsoft-Windows-Kernel-Process

**Use cases:**

- Process monitoring
- Security analysis
- Performance profiling

file
~~~~

File I/O related providers.

**Providers:**

- Microsoft-Windows-Kernel-File

**Use cases:**

- File access monitoring
- I/O performance analysis

security
~~~~~~~~

Security-related providers.

**Providers:**

- Microsoft-Windows-Security-Auditing

**Use cases:**

- Security monitoring
- Audit logging

powershell
~~~~~~~~~~

PowerShell-related providers.

**Providers:**

- Microsoft-Windows-PowerShell

**Use cases:**

- Script monitoring
- PowerShell debugging

Custom Profiles
---------------

You can create custom profiles using YAML:

.. code-block:: yaml

   # my_profile.yaml
   name: my_profile
   description: My custom monitoring profile
   providers:
     - name: Microsoft-Windows-DNS-Client
       level: verbose
       keywords: 0xFFFFFFFFFFFFFFFF
     - name: Microsoft-Windows-TCPIP
       level: information

Load and use:

.. code-block:: python

   from pyetwkit.profiles import load_profile

   profile = load_profile("my_profile.yaml")

   with EtwListener(profile=profile.name) as listener:
       for event in listener:
           print(event)

Profile API
-----------

.. code-block:: python

   from pyetwkit.profiles import (
       get_profile,
       list_profiles,
       load_profile,
       register_profile,
       Profile,
       ProviderConfig,
   )

   # Get a profile
   audio = get_profile("audio")

   # List all profiles
   for profile in list_profiles():
       print(f"{profile.name}: {profile.description}")

   # Create programmatically
   custom = Profile(
       name="custom",
       description="Custom profile",
       providers=[
           ProviderConfig(name="Microsoft-Windows-DNS-Client"),
       ]
   )
   register_profile(custom)
