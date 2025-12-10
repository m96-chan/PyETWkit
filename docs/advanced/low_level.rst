Low-Level API
=============

PyETWkit provides low-level access to ETW functionality for advanced use cases.

Direct Session Control
----------------------

.. code-block:: python

   from pyetwkit._core import EtwSession, EtwProvider

   # Create session
   session = EtwSession("MySession")

   # Add provider with specific settings
   provider = EtwProvider("22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716", "Kernel-Process")
   provider = provider.with_level(5)  # Verbose
   provider = provider.with_keywords(0xFFFFFFFFFFFFFFFF)
   session.add_provider(provider)

   # Start session
   session.start()

   # Process events
   try:
       while True:
           event = session.next_event_timeout(1000)
           if event:
               print(f"Event: {event.event_id}")
   except KeyboardInterrupt:
       pass
   finally:
       session.stop()

Provider Discovery
------------------

.. code-block:: python

   from pyetwkit._core import list_providers, search_providers, get_provider_info

   # List all providers
   providers = list_providers()
   print(f"Total: {len(providers)}")

   # Search
   results = search_providers("Audio")

   # Get details
   info = get_provider_info("Microsoft-Windows-Audio")
   print(f"GUID: {info.guid}")

ETL File Reading
----------------

.. code-block:: python

   from pyetwkit._core import EtlReader

   # Read ETL file
   with EtlReader("trace.etl") as reader:
       for event in reader:
           print(f"{event.provider_id}: {event.event_id}")

   # Read all events
   reader = EtlReader("trace.etl")
   events = reader.read_all()

Event Properties
----------------

.. code-block:: python

   # Event attributes
   event.provider_id      # Provider GUID
   event.provider_name    # Provider name (if known)
   event.event_id         # Event ID
   event.version          # Event version
   event.level            # Trace level
   event.opcode           # Opcode
   event.keyword          # Keywords
   event.timestamp        # Event timestamp
   event.process_id       # Process ID
   event.thread_id        # Thread ID
   event.properties       # Event properties dict

   # Convert to dict
   event_dict = event.to_dict()

Stack Trace Support
-------------------

Enable stack trace capture:

.. code-block:: python

   from pyetwkit._core import EtwProvider, EnableProperty

   provider = EtwProvider("guid", "name")
   provider = provider.with_enable_property(EnableProperty.STACK_TRACE)

   # Access stack trace
   for event in listener:
       if event.stack_trace:
           for addr in event.stack_trace:
               print(f"  0x{addr:016x}")

Kernel Sessions
---------------

For kernel-level monitoring:

.. code-block:: python

   from pyetwkit._core import KernelSession, KernelFlags

   session = KernelSession()
   session.enable_flags(KernelFlags.PROCESS | KernelFlags.THREAD)
   session.start()

   # Process events
   for event in session:
       print(event)

Schema Information
------------------

.. code-block:: python

   from pyetwkit._core import SchemaCache, EventSchema

   cache = SchemaCache()

   # Get schema for event
   schema = cache.get_schema(provider_id, event_id, version)
   if schema:
       print(f"Event: {schema.event_name}")
       for prop in schema.properties:
           print(f"  {prop.name}: {prop.property_type}")

Session Statistics
------------------

.. code-block:: python

   stats = session.stats()
   print(f"Events received: {stats.events_received}")
   print(f"Events lost: {stats.events_lost}")
   print(f"Buffers processed: {stats.buffers_processed}")
