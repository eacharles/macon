Configuration
=============

macon uses `pydantic-settings <https://docs.pydantic.dev/latest/concepts/pydantic_settings/>`_
for configuration. Settings are loaded from environment variables and ``.env`` files.

Environment Variables
---------------------

All nested settings use the ``__`` (double underscore) delimiter.

Database
~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Variable
     - Default
     - Description
   * - ``DB__URL``
     - ``sqlite+aiosqlite:///macon.db``
     - Database connection URL
   * - ``DB__PASSWORD``
     - None
     - Database password
   * - ``DB__TABLE_SCHEMA``
     - None
     - Schema name (PostgreSQL)
   * - ``DB__ECHO``
     - ``false``
     - SQLAlchemy echo mode

ASGI Server
~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Variable
     - Default
     - Description
   * - ``ASGI__TITLE``
     - ``macon``
     - Application title
   * - ``ASGI__HOST``
     - ``0.0.0.0``
     - Bind address
   * - ``ASGI__PORT``
     - ``8080``
     - Bind port
   * - ``ASGI__PREFIX``
     - ``/macon``
     - URL prefix for API
   * - ``ASGI__RELOAD``
     - ``true``
     - Auto-reload on code change

Client
~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Variable
     - Default
     - Description
   * - ``MACON_SERVICE_URL``
     - ``http://0.0.0.0:8000``
     - Remote service URL
   * - ``MACON_AUTH_TOKEN``
     - None
     - Bearer token for auth
   * - ``MACON_TIMEOUT``
     - None
     - Request timeout (seconds)

Storage
~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Variable
     - Default
     - Description
   * - ``STORAGE__ARCHIVE``
     - ``archive``
     - Path for archived files
   * - ``STORAGE__IMPORT_AREA``
     - ``import``
     - Path for file imports
   * - ``STORAGE__DOWNLOAD_AREA``
     - ``macon_downloads``
     - Path for downloads

Logging
~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Variable
     - Default
     - Description
   * - ``LOGGING__HANDLE``
     - ``macon``
     - Logger name
   * - ``LOGGING__LEVEL``
     - ``INFO``
     - Log level
   * - ``LOGGING__PROFILE``
     - ``development``
     - Logging profile

.env File
---------

Settings can also be placed in a ``.env`` file in the project root:

.. code-block:: bash

   DB__URL=postgresql+asyncpg://user:pass@localhost/mydb
   DB__ECHO=false
   LOGGING__LEVEL=DEBUG

The client also reads from ``~/.macon``:

.. code-block:: bash

   MACON_SERVICE_URL=https://api.example.com
   MACON_AUTH_TOKEN=my-secret-token

Programmatic Access
-------------------

.. code-block:: python

   from macon.config import config

   print(config.db.url)
   print(config.asgi.port)
   print(config.client.service_url)
