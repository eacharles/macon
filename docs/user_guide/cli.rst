CLI Reference
=============

macon provides three CLI entry points for managing data locally, running
a server, and interacting with a remote server.

macon-local
-----------

Administrative CLI for local database operations.

.. code-block:: bash

   macon-local --help
   macon-local init             # Initialize database tables
   macon-local init --reset     # Drop and recreate all tables

.. click:: macon.cli.local.top:cli
   :prog: macon-local
   :nested: full

macon-server
------------

Start the FastAPI server.

.. code-block:: bash

   macon-server --help
   macon-server --reload --debug
   macon-server --host 0.0.0.0 --port 8000 --workers 4

.. click:: macon.cli.server.top:serve
   :prog: macon-server
   :nested: full

macon-remote
------------

CLI for remote API operations. Set the base URL via ``--base-url`` or
the ``MACON_BASE_URL`` environment variable.

.. code-block:: bash

   macon-remote --help
   macon-remote --base-url http://localhost:8000 test_named get-rows

.. click:: macon.cli.remote.top:cli
   :prog: macon-remote
   :nested: full
