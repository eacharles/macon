"""Coverage tests for macon.router.app — lines 95-98 and 212 are unreachable.

Lines 95-98: slowapi ImportError handler inside add_rate_limiting, but slowapi
is imported at the top of the module — if the import fails, the module itself
fails to load. This except ImportError block is dead code.

Line 212: general_exception_handler registered via @app.exception_handler(Exception)
but modern FastAPI/Starlette doesn't route handler exceptions through this path.

These lines cannot be practically covered without monkeypatching internals.
This file exists to document that analysis.
"""
