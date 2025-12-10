EtwListener
===========

The ``EtwListener`` class provides synchronous ETW event monitoring.

.. module:: pyetwkit.listener
   :synopsis: Synchronous ETW event listener

Basic Usage
-----------

.. code-block:: python

   from pyetwkit import EtwListener

   with EtwListener("Microsoft-Windows-DNS-Client") as listener:
       for event in listener:
           print(event)

Class Reference
---------------

.. autoclass:: pyetwkit.listener.EtwListener
   :members:
   :undoc-members:
   :show-inheritance:

Configuration
-------------

Level
~~~~~

Set the trace level:

.. code-block:: python

   # Level can be: critical, error, warning, information, verbose
   listener = EtwListener("provider", level="verbose")

Keywords
~~~~~~~~

Filter events by keywords:

.. code-block:: python

   listener = EtwListener("provider", keywords=0xFFFFFFFFFFFFFFFF)

Multiple Providers
~~~~~~~~~~~~~~~~~~

Monitor multiple providers:

.. code-block:: python

   providers = [
       "Microsoft-Windows-Kernel-Process",
       "Microsoft-Windows-Kernel-File",
   ]
   listener = EtwListener(providers)

Using Profiles
~~~~~~~~~~~~~~

Use a pre-defined profile:

.. code-block:: python

   listener = EtwListener(profile="audio")

Examples
--------

Process Monitoring
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from pyetwkit import EtwListener

   with EtwListener("Microsoft-Windows-Kernel-Process") as listener:
       for event in listener:
           print(f"Process event: {event.event_id}")
           if event.properties.get("ImageFileName"):
               print(f"  Image: {event.properties['ImageFileName']}")

Statistics
~~~~~~~~~~

.. code-block:: python

   with EtwListener("provider") as listener:
       for event in listener:
           stats = listener.stats()
           print(f"Received: {stats.events_received}")
           print(f"Dropped: {stats.events_lost}")
