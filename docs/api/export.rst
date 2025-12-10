Data Export
===========

PyETWkit provides functions to export captured events to various formats.

.. module:: pyetwkit.export
   :synopsis: Event data export utilities

Functions
---------

to_dataframe
~~~~~~~~~~~~

Convert events to a Pandas DataFrame:

.. code-block:: python

   from pyetwkit.export import to_dataframe

   df = to_dataframe(events)
   print(df.head())

   # Flatten nested properties
   df = to_dataframe(events, flatten=True)

to_parquet
~~~~~~~~~~

Export events to Parquet format (requires pyarrow):

.. code-block:: python

   from pyetwkit.export import to_parquet

   to_parquet(events, "events.parquet")

   # With compression
   to_parquet(events, "events.parquet", compression="snappy")

to_arrow
~~~~~~~~

Convert events to Arrow Table (requires pyarrow):

.. code-block:: python

   from pyetwkit.export import to_arrow

   table = to_arrow(events)
   print(table.schema)

to_csv
~~~~~~

Export events to CSV:

.. code-block:: python

   from pyetwkit.export import to_csv

   to_csv(events, "events.csv")

to_json
~~~~~~~

Export events to JSON:

.. code-block:: python

   from pyetwkit.export import to_json

   # To file
   to_json(events, "events.json")

   # With indentation
   to_json(events, "events.json", indent=2)

   # To string
   json_str = to_json(events)

to_jsonl
~~~~~~~~

Export events to JSON Lines (one JSON object per line):

.. code-block:: python

   from pyetwkit.export import to_jsonl

   to_jsonl(events, "events.jsonl")

API Reference
-------------

.. autofunction:: pyetwkit.export.to_dataframe

.. autofunction:: pyetwkit.export.to_parquet

.. autofunction:: pyetwkit.export.to_arrow

.. autofunction:: pyetwkit.export.to_csv

.. autofunction:: pyetwkit.export.to_json

.. autofunction:: pyetwkit.export.to_jsonl

Examples
--------

Capture and Export
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from pyetwkit import EtwListener
   from pyetwkit.export import to_dataframe, to_parquet

   # Capture events
   with EtwListener("Microsoft-Windows-DNS-Client") as listener:
       events = list(listener.events(max_events=1000))

   # To DataFrame for analysis
   df = to_dataframe(events)
   print(df.describe())

   # Save for later
   to_parquet(events, "dns_events.parquet")

Streaming Export
~~~~~~~~~~~~~~~~

For large event streams, use JSON Lines:

.. code-block:: python

   from pyetwkit import EtwListener
   from pyetwkit.export import to_jsonl

   with EtwListener("Microsoft-Windows-Kernel-Process") as listener:
       # Batch export
       batch = []
       batch_num = 0

       for event in listener:
           batch.append(event)

           if len(batch) >= 10000:
               to_jsonl(batch, f"events_{batch_num}.jsonl")
               batch = []
               batch_num += 1

Analysis with Pandas
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from pyetwkit.export import to_dataframe

   df = to_dataframe(events)

   # Filter by event ID
   process_start = df[df["event_id"] == 1]

   # Group by provider
   by_provider = df.groupby("provider_name").size()

   # Time-based analysis
   df["timestamp"] = pd.to_datetime(df["timestamp"])
   events_per_second = df.resample("1s", on="timestamp").size()
