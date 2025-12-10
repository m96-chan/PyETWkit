PyETWkit Documentation
======================

**PyETWkit** is a high-performance ETW (Event Tracing for Windows) consumer library for Python,
built with Rust for maximum performance.

.. note::
   ETW sessions require administrator privileges on Windows.

Features
--------

- **High Performance**: Rust-based core for low-latency event processing
- **Pythonic API**: Clean, easy-to-use Python interface
- **Async Support**: Native asyncio integration with ``EtwStreamer``
- **Provider Profiles**: Pre-configured profiles for common use cases
- **CLI Tool**: Command-line interface for quick monitoring
- **Data Export**: Export to Parquet, Arrow, Pandas, CSV, JSON

Quick Start
-----------

Installation
~~~~~~~~~~~~

.. code-block:: bash

   pip install pyetwkit

Basic Usage
~~~~~~~~~~~

.. code-block:: python

   from pyetwkit import EtwListener

   # Listen to process events
   with EtwListener("Microsoft-Windows-Kernel-Process") as listener:
       for event in listener:
           print(f"Event: {event.event_id}")

Using Profiles
~~~~~~~~~~~~~~

.. code-block:: python

   from pyetwkit import EtwListener

   # Use a pre-defined profile
   with EtwListener(profile="audio") as listener:
       for event in listener:
           print(event)

CLI Usage
~~~~~~~~~

.. code-block:: bash

   # List providers
   pyetwkit providers --search Kernel

   # List profiles
   pyetwkit profiles

   # Monitor events (requires admin)
   pyetwkit listen Microsoft-Windows-Kernel-Process

Documentation
-------------

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   quickstart
   tutorial
   profiles
   cli

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/listener
   api/streamer
   api/export
   api/profiles

.. toctree::
   :maxdepth: 1
   :caption: Advanced

   advanced/low_level
   advanced/etw_basics

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
