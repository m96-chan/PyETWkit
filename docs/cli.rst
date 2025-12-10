Command Line Interface
======================

PyETWkit includes a command-line interface for quick ETW monitoring.

Installation
------------

The CLI is installed automatically with PyETWkit:

.. code-block:: bash

   pip install pyetwkit

Usage
-----

.. code-block:: bash

   pyetwkit --help

Commands
--------

providers
~~~~~~~~~

List available ETW providers on the system.

.. code-block:: bash

   # List all providers (limited to 50 by default)
   pyetwkit providers

   # Search for providers
   pyetwkit providers --search Kernel

   # Show more providers
   pyetwkit providers --limit 100

   # JSON output
   pyetwkit providers --format json

profiles
~~~~~~~~

List available provider profiles.

.. code-block:: bash

   # List profiles
   pyetwkit profiles

   # JSON output
   pyetwkit profiles --format json

listen
~~~~~~

Monitor ETW events from a provider or profile.

.. note::
   This command requires administrator privileges.

.. code-block:: bash

   # Listen to a specific provider
   pyetwkit listen Microsoft-Windows-Kernel-Process

   # Use a profile
   pyetwkit listen --profile audio

   # Specify output format
   pyetwkit listen --profile network --format json

   # Save to file
   pyetwkit listen --profile network --output events.jsonl --format jsonl

   # Limit events
   pyetwkit listen Microsoft-Windows-DNS-Client --max-events 100

   # Set trace level
   pyetwkit listen --profile network --level verbose

Options
^^^^^^^

``PROVIDER``
    ETW provider name or GUID to monitor.

``--profile, -p``
    Use a provider profile instead of specifying a provider.

``--format, -f``
    Output format: ``table``, ``json``, or ``jsonl``. Default: ``table``.

``--output, -o``
    Output file path. If not specified, prints to stdout.

``--max-events, -n``
    Maximum number of events to capture.

``--level, -l``
    Trace level: ``critical``, ``error``, ``warning``, ``info``, ``verbose``.
    Default: ``info``.

Examples
--------

Provider Discovery
~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Find audio-related providers
   pyetwkit providers --search Audio

   # Find process-related providers
   pyetwkit providers --search "Kernel-Process"

   # Export provider list to JSON
   pyetwkit providers --format json > providers.json

Quick Monitoring
~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Monitor DNS queries (requires admin)
   pyetwkit listen Microsoft-Windows-DNS-Client

   # Monitor network with profile (requires admin)
   pyetwkit listen --profile network

Recording Events
~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Record events to JSON Lines file
   pyetwkit listen --profile network --output events.jsonl --format jsonl

   # Record limited events
   pyetwkit listen Microsoft-Windows-DNS-Client --max-events 1000 --output dns.jsonl --format jsonl

Exit Codes
----------

- ``0``: Success
- ``1``: Error (invalid arguments, missing admin privileges, etc.)
