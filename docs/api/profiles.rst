Profiles Module
===============

The profiles module provides pre-configured provider sets for common use cases.

.. module:: pyetwkit.profiles
   :synopsis: Provider profile management

Classes
-------

Profile
~~~~~~~

.. autoclass:: pyetwkit.profiles.Profile
   :members:
   :undoc-members:

ProviderConfig
~~~~~~~~~~~~~~

.. autoclass:: pyetwkit.profiles.ProviderConfig
   :members:
   :undoc-members:

Functions
---------

get_profile
~~~~~~~~~~~

.. autofunction:: pyetwkit.profiles.get_profile

list_profiles
~~~~~~~~~~~~~

.. autofunction:: pyetwkit.profiles.list_profiles

load_profile
~~~~~~~~~~~~

.. autofunction:: pyetwkit.profiles.load_profile

register_profile
~~~~~~~~~~~~~~~~

.. autofunction:: pyetwkit.profiles.register_profile

Usage Examples
--------------

Getting a Profile
~~~~~~~~~~~~~~~~~

.. code-block:: python

   from pyetwkit.profiles import get_profile

   audio = get_profile("audio")
   print(f"Name: {audio.name}")
   print(f"Description: {audio.description}")
   for p in audio.providers:
       print(f"  - {p.name} ({p.level})")

Listing Profiles
~~~~~~~~~~~~~~~~

.. code-block:: python

   from pyetwkit.profiles import list_profiles

   for profile in list_profiles():
       print(f"{profile.name}: {profile.description}")

Creating Custom Profiles
~~~~~~~~~~~~~~~~~~~~~~~~

From code:

.. code-block:: python

   from pyetwkit.profiles import Profile, ProviderConfig, register_profile

   custom = Profile(
       name="my_custom",
       description="My custom profile",
       providers=[
           ProviderConfig(
               name="Microsoft-Windows-DNS-Client",
               level="verbose",
           ),
           ProviderConfig(
               name="Microsoft-Windows-TCPIP",
               level="information",
               keywords=0xFFFFFFFF,
           ),
       ],
   )
   register_profile(custom)

From YAML file:

.. code-block:: python

   from pyetwkit.profiles import load_profile

   profile = load_profile("my_profile.yaml")

YAML Profile Format
-------------------

.. code-block:: yaml

   name: my_profile
   description: Description of the profile
   providers:
     - name: Microsoft-Windows-Provider-Name
       guid: optional-guid-if-needed
       level: verbose  # critical, error, warning, information, verbose
       keywords: 0xFFFFFFFFFFFFFFFF  # optional keyword filter
     - name: Another-Provider
       level: information
