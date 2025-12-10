ETW Basics
==========

Event Tracing for Windows (ETW) is a high-performance event logging mechanism built into Windows.

What is ETW?
------------

ETW provides:

- **Low overhead**: Designed for production systems
- **Structured events**: Rich event data with schemas
- **Real-time processing**: Events can be consumed as they occur
- **File-based logging**: Events can be saved to ETL files

Components
----------

Providers
~~~~~~~~~

Providers are components that generate events:

- **Manifest-based providers**: Define events in XML manifest
- **TraceLogging providers**: Define events at runtime
- **MOF providers**: Legacy format

Each provider has:

- **GUID**: Unique identifier
- **Name**: Human-readable name
- **Events**: Set of defined events
- **Keywords**: Event categories
- **Levels**: Event severity

Sessions
~~~~~~~~

Sessions (also called traces) collect events:

- Control which providers are enabled
- Set buffer sizes and other parameters
- Direct events to files or real-time consumers

Consumers
~~~~~~~~~

Consumers receive and process events:

- **Real-time**: Process events as they occur
- **File-based**: Read from ETL files

Trace Levels
------------

Events have severity levels:

.. list-table::
   :header-rows: 1

   * - Level
     - Value
     - Description
   * - Critical
     - 1
     - Critical errors
   * - Error
     - 2
     - Error conditions
   * - Warning
     - 3
     - Warning conditions
   * - Information
     - 4
     - Informational messages
   * - Verbose
     - 5
     - Detailed debug information

Keywords
--------

Keywords are bit flags that categorize events:

.. code-block:: python

   # Enable all keywords
   provider = EtwProvider("guid", "name")
   provider = provider.with_keywords(0xFFFFFFFFFFFFFFFF)

   # Enable specific keywords
   provider = provider.with_keywords(0x0000000000000010)

Common Providers
----------------

.. list-table::
   :header-rows: 1

   * - Provider
     - Description
   * - Microsoft-Windows-Kernel-Process
     - Process creation/termination
   * - Microsoft-Windows-Kernel-File
     - File I/O operations
   * - Microsoft-Windows-Kernel-Network
     - Network operations
   * - Microsoft-Windows-DNS-Client
     - DNS queries
   * - Microsoft-Windows-TCPIP
     - TCP/IP stack events
   * - Microsoft-Windows-Security-Auditing
     - Security events

Finding Providers
-----------------

Use ``logman`` to list providers:

.. code-block:: bash

   logman query providers

Or use PyETWkit:

.. code-block:: python

   from pyetwkit import list_providers, search_providers

   # List all
   providers = list_providers()

   # Search
   results = search_providers("Kernel")

ETL Files
---------

ETL (Event Trace Log) files store captured events:

.. code-block:: bash

   # Start trace to file
   logman start mytrace -p Microsoft-Windows-DNS-Client -o trace.etl -ets

   # Stop trace
   logman stop mytrace -ets

Read with PyETWkit:

.. code-block:: python

   from pyetwkit import EtlReader

   with EtlReader("trace.etl") as reader:
       for event in reader:
           print(event)

Resources
---------

- `ETW Documentation <https://docs.microsoft.com/en-us/windows/win32/etw/event-tracing-portal>`_
- `Providers Reference <https://docs.microsoft.com/en-us/windows/win32/etw/event-tracing-reference>`_
- `Performance Toolkit <https://docs.microsoft.com/en-us/windows-hardware/test/wpt/>`_
