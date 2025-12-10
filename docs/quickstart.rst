Quick Start Guide
=================

This guide will help you get started with PyETWkit.

Prerequisites
-------------

- Windows 10/11 or Windows Server 2016+
- Python 3.9+
- Administrator privileges (for starting ETW sessions)

Installation
------------

Install from PyPI:

.. code-block:: bash

   pip install pyetwkit

Verify installation:

.. code-block:: python

   import pyetwkit
   print(pyetwkit.__version__)

Basic Usage
-----------

Listing Providers
~~~~~~~~~~~~~~~~~

Before monitoring events, you can list available providers:

.. code-block:: python

   from pyetwkit import list_providers, search_providers

   # List all providers
   providers = list_providers()
   print(f"Found {len(providers)} providers")

   # Search for specific providers
   kernel_providers = search_providers("Kernel")
   for p in kernel_providers[:5]:
       print(f"{p.name}: {p.guid}")

Monitoring Events
~~~~~~~~~~~~~~~~~

Use ``EtwListener`` to monitor events from a provider:

.. code-block:: python

   from pyetwkit import EtwListener

   # Requires administrator privileges
   with EtwListener("Microsoft-Windows-Kernel-Process") as listener:
       for event in listener:
           print(f"Provider: {event.provider_name}")
           print(f"Event ID: {event.event_id}")
           print(f"Properties: {event.properties}")

           # Limit to 10 events for demo
           if listener.stats().events_received >= 10:
               break

Using Profiles
~~~~~~~~~~~~~~

Profiles provide pre-configured sets of providers for common use cases:

.. code-block:: python

   from pyetwkit import EtwListener
   from pyetwkit.profiles import list_profiles

   # List available profiles
   for profile in list_profiles():
       print(f"{profile.name}: {profile.description}")

   # Use a profile
   with EtwListener(profile="network") as listener:
       for event in listener:
           print(event)

Async Support
~~~~~~~~~~~~~

For async applications, use ``EtwStreamer``:

.. code-block:: python

   import asyncio
   from pyetwkit import EtwStreamer

   async def monitor_events():
       async with EtwStreamer("Microsoft-Windows-DNS-Client") as streamer:
           async for event in streamer:
               print(f"Event: {event.event_id}")

   asyncio.run(monitor_events())

Data Export
~~~~~~~~~~~

Export events to various formats:

.. code-block:: python

   from pyetwkit import EtwListener
   from pyetwkit.export import to_dataframe, to_parquet, to_json

   with EtwListener("Microsoft-Windows-DNS-Client") as listener:
       events = list(listener.events(max_events=100))

   # To Pandas DataFrame
   df = to_dataframe(events)
   print(df.head())

   # To Parquet
   to_parquet(events, "events.parquet")

   # To JSON
   to_json(events, "events.json")

CLI Usage
---------

PyETWkit includes a command-line interface:

.. code-block:: bash

   # List providers
   pyetwkit providers

   # Search providers
   pyetwkit providers --search Audio

   # List profiles
   pyetwkit profiles

   # Monitor events (requires admin)
   pyetwkit listen Microsoft-Windows-Kernel-Process

   # Use a profile
   pyetwkit listen --profile network

   # Output to file
   pyetwkit listen --profile network --output events.jsonl --format jsonl

Next Steps
----------

- See :doc:`tutorial` for more detailed examples
- Check :doc:`profiles` for available profiles
- Read :doc:`api/listener` for API reference
