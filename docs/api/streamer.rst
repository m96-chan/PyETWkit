EtwStreamer
===========

The ``EtwStreamer`` class provides asynchronous ETW event monitoring.

.. module:: pyetwkit.streamer
   :synopsis: Asynchronous ETW event streamer

Basic Usage
-----------

.. code-block:: python

   import asyncio
   from pyetwkit import EtwStreamer

   async def monitor():
       async with EtwStreamer("Microsoft-Windows-DNS-Client") as streamer:
           async for event in streamer:
               print(event)

   asyncio.run(monitor())

Class Reference
---------------

.. autoclass:: pyetwkit.streamer.EtwStreamer
   :members:
   :undoc-members:
   :show-inheritance:

Async Iteration
---------------

``EtwStreamer`` supports async iteration:

.. code-block:: python

   async with EtwStreamer("provider") as streamer:
       async for event in streamer:
           await process_event(event)

Event Methods
~~~~~~~~~~~~~

.. code-block:: python

   # Get next event with timeout
   event = await streamer.next_event(timeout=1.0)

   # Try to get event without waiting
   event = streamer.try_next_event()

Multiple Providers
------------------

.. code-block:: python

   providers = [
       "Microsoft-Windows-Kernel-Process",
       "Microsoft-Windows-Kernel-File",
   ]

   async with EtwStreamer(providers) as streamer:
       async for event in streamer:
           print(f"{event.provider_name}: {event.event_id}")

Using Profiles
--------------

.. code-block:: python

   async with EtwStreamer(profile="network") as streamer:
       async for event in streamer:
           print(event)

Examples
--------

Async Processing
~~~~~~~~~~~~~~~~

.. code-block:: python

   import asyncio
   from pyetwkit import EtwStreamer

   async def process_events():
       async with EtwStreamer("Microsoft-Windows-DNS-Client") as streamer:
           async for event in streamer:
               # Async processing
               await save_to_database(event)

               if streamer.stats().events_received >= 100:
                   break

   asyncio.run(process_events())

Concurrent Monitoring
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import asyncio
   from pyetwkit import EtwStreamer

   async def monitor(profile: str):
       async with EtwStreamer(profile=profile) as streamer:
           async for event in streamer:
               print(f"[{profile}] {event.event_id}")

   async def main():
       await asyncio.gather(
           monitor("network"),
           monitor("process"),
       )

   asyncio.run(main())
