Filtering
=========

macon provides a flexible filtering system for database queries with support
for various comparison operators, logical operators, and ordering.

Filter Operators
----------------

.. list-table::
   :header-rows: 1
   :widths: 15 15 70

   * - Operator
     - ``FilterOp``
     - Description
   * - Equal
     - ``EQ``
     - Exact match (``==``)
   * - Not Equal
     - ``NE``
     - Not equal (``!=``)
   * - Less Than
     - ``LT``
     - Less than (``<``)
   * - Less or Equal
     - ``LE``
     - Less than or equal (``<=``)
   * - Greater Than
     - ``GT``
     - Greater than (``>``)
   * - Greater or Equal
     - ``GE``
     - Greater than or equal (``>=``)
   * - In List
     - ``IN``
     - Value is in a list
   * - Not In List
     - ``NOT_IN``
     - Value is not in a list
   * - Like
     - ``LIKE``
     - SQL LIKE pattern (use ``%`` wildcard)
   * - ILike
     - ``ILIKE``
     - Case-insensitive LIKE
   * - Is Null
     - ``IS_NULL``
     - Value is NULL
   * - Is Not Null
     - ``IS_NOT_NULL``
     - Value is not NULL
   * - Between
     - ``BETWEEN``
     - Value between two bounds
   * - Contains
     - ``CONTAINS``
     - Array contains (PostgreSQL)
   * - Starts With
     - ``STARTS_WITH``
     - String prefix match
   * - Ends With
     - ``ENDS_WITH``
     - String suffix match

Usage Examples
--------------

Basic filtering:

.. code-block:: python

   from macon.models import Filter, FilterOp, OrderBy
   from macon.db_funcs.filter import filter_rows

   # Exact match
   results = await filter_rows(
       User, session,
       filters=[Filter(field="name", op=FilterOp.EQ, value="Alice")],
   )

   # Multiple conditions with AND
   results = await filter_rows(
       User, session,
       filters=[
           Filter(field="age", op=FilterOp.GE, value=18),
           Filter(field="status", op=FilterOp.EQ, value="active"),
       ],
       logical_op="and",
   )

   # OR logic
   results = await filter_rows(
       User, session,
       filters=[
           Filter(field="role", op=FilterOp.EQ, value="admin"),
           Filter(field="role", op=FilterOp.EQ, value="moderator"),
       ],
       logical_op="or",
   )

Ordering:

.. code-block:: python

   # Single ordering
   results = await filter_rows(
       User, session,
       order_by=OrderBy(field="created_at", descending=True),
   )

   # Multiple ordering
   results = await filter_rows(
       User, session,
       order_by=[
           OrderBy(field="role", descending=False),
           OrderBy(field="name", descending=False),
       ],
   )

Pagination:

.. code-block:: python

   # Skip first 20, return next 10
   results = await filter_rows(
       User, session,
       skip=20,
       limit=10,
   )

Convenience Functions
---------------------

.. code-block:: python

   from macon.db_funcs.filter import find_by, find_one_by, filter_one

   # Find by equality on fields
   active_admins = await find_by(User, session, role="admin", status="active")

   # Find exactly one
   user = await find_one_by(User, session, email="alice@example.com")

   # Filter to exactly one (raises if 0 or >1)
   user = await filter_one(
       User, session,
       filters=[Filter(field="email", op=FilterOp.EQ, value="alice@example.com")],
   )

Via REST API
------------

The filter endpoints accept JSON request bodies:

.. code-block:: bash

   curl -X POST http://localhost:8000/api/v1/users/filter_rows \
     -H "Content-Type: application/json" \
     -d '{
       "filters": [
         {"field": "name", "op": "starts_with", "value": "A"}
       ],
       "logical_op": "and",
       "order_by": {"field": "name", "descending": false},
       "skip": 0,
       "limit": 100
     }'
