Tutorial
========

This tutorial covers common use cases for PyETWkit.

Provider Discovery
------------------

Finding the right ETW provider is the first step:

.. code-block:: python

   from pyetwkit import list_providers, search_providers, get_provider_info

   # List all registered providers
   all_providers = list_providers()
   print(f"Total providers: {len(all_providers)}")

   # Search by keyword
   audio_providers = search_providers("Audio")
   for p in audio_providers:
       print(f"  {p.name}")

   # Get detailed info
   info = get_provider_info("Microsoft-Windows-Kernel-Process")
   print(f"Name: {info.name}")
   print(f"GUID: {info.guid}")

Event Monitoring
----------------

Basic Monitoring
~~~~~~~~~~~~~~~~

.. code-block:: python

   from pyetwkit import EtwListener

   with EtwListener("Microsoft-Windows-DNS-Client") as listener:
       for event in listener:
           print(f"[{event.timestamp}] Event {event.event_id}")
           print(f"  Properties: {event.properties}")

           if listener.stats().events_received >= 10:
               break

Multiple Providers
~~~~~~~~~~~~~~~~~~

Monitor multiple providers simultaneously:

.. code-block:: python

   from pyetwkit import EtwListener

   providers = [
       "Microsoft-Windows-Kernel-Process",
       "Microsoft-Windows-Kernel-File",
   ]

   with EtwListener(providers) as listener:
       for event in listener:
           print(f"{event.provider_name}: {event.event_id}")

Event Filtering
~~~~~~~~~~~~~~~

Filter events by various criteria:

.. code-block:: python

   from pyetwkit import EtwListener, EventFilter

   # Filter by process ID
   filter = EventFilter().process_id(1234)

   with EtwListener("Microsoft-Windows-Kernel-Process", filter=filter) as listener:
       for event in listener:
           print(event)

Using Profiles
--------------

Profiles provide curated sets of providers:

.. code-block:: python

   from pyetwkit import EtwListener
   from pyetwkit.profiles import get_profile

   # Check what's in a profile
   audio = get_profile("audio")
   print(f"Profile: {audio.name}")
   print(f"Description: {audio.description}")
   for p in audio.providers:
       print(f"  - {p.name}")

   # Use the profile
   with EtwListener(profile="audio") as listener:
       for event in listener:
           print(event)

Custom Profiles
~~~~~~~~~~~~~~~

Create your own profiles:

.. code-block:: python

   from pyetwkit.profiles import Profile, ProviderConfig, load_profile

   # From code
   custom = Profile(
       name="my_profile",
       description="My custom profile",
       providers=[
           ProviderConfig(name="Microsoft-Windows-DNS-Client"),
           ProviderConfig(name="Microsoft-Windows-TCPIP"),
       ]
   )

   # From YAML file
   profile = load_profile("my_profile.yaml")

Example YAML profile:

.. code-block:: yaml

   name: my_profile
   description: My custom profile
   providers:
     - name: Microsoft-Windows-DNS-Client
       level: verbose
     - name: Microsoft-Windows-TCPIP
       level: information
       keywords: 0xFFFFFFFF

Data Export
-----------

Export captured events for analysis:

.. code-block:: python

   from pyetwkit import EtwListener
   from pyetwkit.export import (
       to_dataframe,
       to_parquet,
       to_csv,
       to_json,
       to_jsonl,
   )

   # Capture events
   with EtwListener("Microsoft-Windows-DNS-Client") as listener:
       events = list(listener.events(max_events=100))

   # To Pandas DataFrame
   df = to_dataframe(events)
   print(df.info())

   # To Parquet (efficient for large datasets)
   to_parquet(events, "events.parquet")

   # To CSV
   to_csv(events, "events.csv")

   # To JSON
   to_json(events, "events.json", indent=2)

   # To JSON Lines (streaming friendly)
   to_jsonl(events, "events.jsonl")

Async Programming
-----------------

For async applications:

.. code-block:: python

   import asyncio
   from pyetwkit import EtwStreamer

   async def monitor():
       async with EtwStreamer("Microsoft-Windows-DNS-Client") as streamer:
           async for event in streamer:
               print(f"Event: {event.event_id}")

               # Stop after 10 events
               if streamer.stats().events_received >= 10:
                   break

   asyncio.run(monitor())

ETL File Processing
-------------------

Read events from ETL files:

.. code-block:: python

   from pyetwkit import EtlReader

   with EtlReader("trace.etl") as reader:
       for event in reader:
           print(f"{event.provider_name}: {event.event_id}")

   # Or read all at once
   events = reader.read_all()
   print(f"Read {len(events)} events")
