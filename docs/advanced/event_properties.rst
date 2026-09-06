Event Properties
================

Every property an event declares is decoded from its schema through TDH, so
``event.properties`` reflects whatever the provider actually publishes rather
than a fixed list of names.

.. code-block:: python

   from pyetwkit._core import EtlReader

   for event in EtlReader("dns.etl").read_all():
       print(event.event_id, event.properties)

.. code-block:: text

   3020 {'QueryName': 'docs.google.com', 'QueryType': 1, 'Status': 0,
         'ClientPID': 27436, 'QueryBlob': 2525199111760,
         'QueryResults': '142.251.24.139;142.251.24.101;...'}

Values are Python-native. Integers arrive as ``int``, binary as ``bytes``,
GUIDs and SIDs as ``str``, timestamps as ISO 8601 strings.

Arrays and nested structures
----------------------------

An array property becomes a ``list``, and a structure becomes a ``dict`` of its
members. A structure that is itself an array becomes a list of dicts.

.. code-block:: python

   event.properties["RankList"]
   # [4294967295, 4294967295, 0, 2, 4294967295, 1, ...]

   event.properties["NewPark"]
   # {'Number': 0, 'Affinity': 20672}

   event.properties["HardwareTable"]
   # [{'LogicalProcessorIndex': 0, 'WorkLoadClassIndex': 0,
   #   'PerformanceClass': 51, 'EfficiencyClass': 56}, ...]

An array of bytes comes back as ``bytes`` rather than a list of small integers.

Display strings
---------------

Typed values are the default because they are what the exporters need. TDH can
also render each property the way it would be displayed, which resolves the
manifest's value maps and output types — things a typed value cannot express.
This is off by default, since it costs an extra TDH round trip per property.

.. code-block:: python

   from pyetwkit import _core

   _core.set_property_formatting(True)

   for event in EtlReader("dns.etl").read_all():
       print(event.properties.get("DynamicAddress"))       # 1
       print(event.formatted_properties["DynamicAddress"])  # 'dynamic'
       print(event.properties.get("Address"))               # b'\x02\x00\x00\x00\xc0\xa82\x01...'
       print(event.formatted_properties["Address"])         # '192.168.50.1'

``formatted_properties`` is empty unless formatting is switched on, and omits
arrays and structures — ``properties`` reports those in full.

Events with no schema
---------------------

Some events have no schema TDH can find: WPP without format information, or a
manifest provider whose manifest is not installed on the machine doing the
decoding. Those have no property names to report a value under, so
``properties`` is empty and the payload is kept as raw bytes instead.

.. code-block:: python

   for event in EtlReader("capture.etl").read_all():
       if not event.properties and event.raw_data is not None:
           print(event.provider_id, len(event.raw_data), event.raw_data[:16])

``raw_data`` is ``None`` for any event that decoded normally, rather than a
second copy of data ``properties`` already holds.

.. _wpp-decoding:

Decoding WPP events
-------------------

WPP events carry no schema at all. Their format strings live outside the trace,
in a ``.tmf`` generated from the emitting binary's PDB, or in that PDB itself.
Without one, every WPP event decodes to the same placeholder:

.. code-block:: text

   Unknown( 10): GUID=a5bbbdd9-73f9-3bed-93aa-521a4c96d934 (No Format Information found).

Point PyETWkit at format information and the real message appears in
``FormattedString``, replacing that placeholder. There are three ways to supply
it; **the PDB is usually the one to reach for**, because it needs no SDK tooling
at all:

.. code-block:: python

   from pyetwkit import _core

   # Easiest: the PDB of the binary that emitted the events. TDH reads the
   # format information straight out of it.
   _core.set_wpp_pdb_path(r"C:\symbols\mydriver.pdb")

   # Or a directory of .tmf files, named after each trace GUID.
   _core.set_wpp_tmf_search_path(r"C:\symbols\tmf")

   # Or a single .tmf.
   _core.set_wpp_tmf_file(r"C:\symbols\tmf\a5bbbdd9-....tmf")

   for event in EtlReader("wpp.etl").read_all():
       print(event.properties.get("FormattedString"))

.. code-block:: text

   wpp probe seq=0 name=core-state value=0x50c0
   wpp probe seq=1 name=core-state value=0x50c1
   wpp probe seq=2 name=core-state value=0x50c2

Pass ``None`` to any of them to stop using that source. They apply to events
decoded from then on, so set them before reading.

A ``.tmf`` is produced from a PDB with ``tracepdb`` from the Windows SDK::

   tracepdb -f mydriver.pdb -p C:\symbols\tmf

which is worth doing if you want to hand the format information to someone who
does not have the PDB — a ``.tmf`` is a small text file, while a PDB is often
several megabytes. If you have the PDB to hand, ``set_wpp_pdb_path`` skips the
step entirely.

.. note::

   The trace GUID that names a ``.tmf`` is derived by WPP from the source file's
   full path at build time. A PDB or ``.tmf`` from a build in a different
   directory will not decode a capture made elsewhere, even from identical
   source.
