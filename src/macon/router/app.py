import logging
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from ..db.session import init_db
from .base import all_routers

# Configure logging
logger = logging.getLogger(__name__)


def register_all_routers(app: FastAPI, all_routers: list[APIRouter], prefix: str = "/api/v1") -> None:
    """Register all routers with a FastAPI app.

    Parameters
    ----------
    app : FastAPI
        The FastAPI application instance
    all_routers : 
    prefix : str
        URL prefix for all API routes (default: "/api/v1")

    Example
    -------
    >>> from fastapi import FastAPI
    >>> app = FastAPI()
    >>> register_all_routers(app, prefix="/api/v2")
    """
    for router in all_routers:
        # Include router with the API version prefix
        app.include_router(router, prefix=prefix)
        logger.info(f"Registered router: {router.prefix} at {prefix}{router.prefix}")

    logger.info(f"Registered router: {funcs_router.prefix} at {prefix}{funcs_router.prefix}")


def add_rate_limiting(
    app: FastAPI, default_limits: Sequence[str] | None = None, storage_uri: str = "memory://"
) -> Limiter | None:
    """Add rate limiting to the FastAPI app.

    Parameters
    ----------
    app : FastAPI
        The FastAPI application instance
    default_limits : list[str] | None
        Default rate limits (e.g., ["200 per day", "50 per hour"])
        If None, defaults to ["1000 per day", "100 per hour"]
    storage_uri : str
        Storage URI for rate limit data (default: "memory://")
        For production, use Redis: "redis://localhost:6379"

    Returns
    -------
    Limiter | None
        The limiter instance, or None if slowapi is not installed

    Example
    -------
    >>> from fastapi import FastAPI
    >>> app = FastAPI()
    >>> limiter = add_rate_limiting(
    ...     app,
    ...     ["1000 per day", "100 per hour"],
    ...     storage_uri="redis://localhost:6379"
    ... )

    Note
    ----
    Requires: pip install slowapi
    For production, use Redis storage instead of in-memory storage
    """
    try:
        if default_limits is None:
            default_limits = ["1000 per day", "100 per hour"]

        limiter = Limiter(
            key_func=get_remote_address,
            default_limits=list(default_limits),
            storage_uri=storage_uri,
        )

        # Add limiter to app state so it's accessible in routes
        app.state.limiter = limiter

        # Add exception handler for rate limit exceeded
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore

        logger.info(f"Rate limiting enabled: {default_limits}")
        return limiter
    except ImportError:
        logger.warning("slowapi not installed. Rate limiting not available.")
        logger.warning("Install with: pip install slowapi")
        return None


def add_health_check(app: FastAPI) -> None:
    """Add a health check endpoint to the app.

    Parameters
    ----------
    app : FastAPI
        The FastAPI application instance

    Note
    ----
    The health check endpoint is available at /health
    Returns 200 if healthy, 503 if unhealthy
    """

    @app.get("/health", tags=["health"])
    async def health_check() -> JSONResponse:
        """Health check endpoint.

        Returns
        -------
        dict[str, Any]
            Status information

        Responses
        ---------
        200: Service is healthy
        503: Service is unhealthy
        """
        try:
            # Add any health checks here (database connection, etc.)
            return JSONResponse(
                status_code=200, content={"status": "healthy", "service": "api", "version": "1.0.0"}
            )
        except Exception as uexc:
            logger.exception("Health check failed")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "unhealthy", "error": str(uexc) if app.debug else "Service unavailable"},
            )

    logger.info("Health check endpoint added at /health")


def add_error_handlers(app: FastAPI) -> None:
    """Add global error handlers to the app.

    Parameters
    ----------
    app : FastAPI
        The FastAPI application instance

    Note
    ----
    Adds handlers for:
    - 404 Not Found
    - 405 Method Not Allowed
    - 422 Validation Error
    - 500 Internal Server Error
    - General exceptions
    """

    @app.exception_handler(404)
    async def not_found_handler(request: Request, _exc: Any) -> JSONResponse:
        """Handle 404 errors."""
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "Endpoint not found",
                "request": request.url.path,
            },
        )

    @app.exception_handler(405)
    async def method_not_allowed_handler(request: Request, _exc: Any) -> JSONResponse:
        """Handle 405 errors."""
        return JSONResponse(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            content={
                "error": "Method not allowed",
                "path": request.url.path,  # Changed from request object
                "method": request.method,  # Add method info
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Handle validation errors."""
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Validation error",
                "path": request.url.path,  # Changed from request object
                "details": exc.errors(),
            },
        )

    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc: Any) -> JSONResponse:  # pragma: no cover
        """Handle 500 errors."""
        logger.exception("Internal server error")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "request": request.url.path,
                "details": str(exc) if app.debug else None,
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle all other exceptions."""
        logger.exception("Unhandled exception")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "request": request.url.path,
                "details": str(exc) if app.debug else "An unexpected error occurred",
            },
        )

    logger.info("Global error handlers added")


def add_cors_middleware(
    app: FastAPI,
    *,
    allow_origins: list[str] | None = None,
    allow_credentials: bool = True,
    allow_methods: list[str] | None = None,
    allow_headers: list[str] | None = None,
) -> None:
    """Add CORS middleware to the app.

    Parameters
    ----------
    app : FastAPI
        The FastAPI application instance
    allow_origins : list[str] | None
        Allowed origins (default: ["*"])
        In production, specify exact origins instead of "*"
    allow_credentials : bool
        Whether to allow credentials (default: True)
    allow_methods : list[str] | None
        Allowed HTTP methods (default: ["*"])
    allow_headers : list[str] | None
        Allowed headers (default: ["*"])

    Warning
    -------
    Using ["*"] for origins is not recommended in production.
    Specify exact origins for better security.

    Example
    -------
    >>> app = FastAPI()
    >>> add_cors_middleware(
    ...     app,
    ...     allow_origins=["https://example.com", "https://app.example.com"],
    ...     allow_credentials=True
    ... )
    """
    if allow_origins is None:
        allow_origins = ["*"]  # In production, specify exact origins

    if allow_methods is None:
        allow_methods = ["*"]

    if allow_headers is None:
        allow_headers = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=allow_credentials,
        allow_methods=allow_methods,
        allow_headers=allow_headers,
    )

    logger.info(f"CORS middleware added with origins: {allow_origins}")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager for startup and shutdown events.

    Parameters
    ----------
    _app : FastAPI
        The FastAPI application instance

    Yields
    ------
    None
        Control is yielded during app lifetime

    Note
    ----
    Add startup logic before yield and cleanup logic after yield.

    Example
    -------
    >>> @asynccontextmanager
    >>> async def lifespan(app: FastAPI):
    ...     # Startup
    ...     db = await init_database()
    ...     yield
    ...     # Shutdown
    ...     await db.close()
    """
    # Startup
    logger.info("Starting up application...")
    # Add any startup logic here (database connections, etc.)

    yield

    # Shutdown
    logger.info("Shutting down application...")
    # Add any cleanup logic here (close database connections, etc.)


def create_fastapi_app(
    all_routers: list[APIRouter],
    title: str = "API",
    description: str = "FastAPI application",
    version: str = "1.0.0",    
    *,
    enable_rate_limiting: bool = False,
    rate_limits: list[str] | None = None,
    rate_limit_storage: str = "memory://",
    enable_cors: bool = False,
    cors_origins: list[str] | None = None,
    api_prefix: str = "/api/v1",
    debug: bool = False,
) -> FastAPI:
    """Create and configure a FastAPI application.

    Parameters
    ----------
    all_routers: 
        All of the routers to put in the app
    title : str
        Application title (default: "API")
    description : str
        Application description (default: "FastAPI application")
    version : str
        Application version (default: "1.0.0")
    enable_rate_limiting : bool
        Whether to enable rate limiting (default: False)
    rate_limits : list[str] | None
        Rate limit rules (default: ["1000 per day", "100 per hour"])
    rate_limit_storage : str
        Storage URI for rate limiting (default: "memory://")
        For production: "redis://localhost:6379"
    enable_cors : bool
        Whether to enable CORS (default: False)
    cors_origins : list[str] | None
        Allowed CORS origins (default: ["*"])
    api_prefix : str
        API route prefix (default: "/api/v1")
    debug : bool
        Debug mode (default: False)

    Returns
    -------
    FastAPI
        Configured FastAPI application instance

    Example
    -------
    >>> app = create_fastapi_app(
    ...     title="My API",
    ...     version="2.0.0",
    ...     enable_rate_limiting=True,
    ...     rate_limits=["500 per day", "50 per hour"],
    ...     rate_limit_storage="redis://localhost:6379",
    ...     enable_cors=True,
    ...     cors_origins=["https://example.com"],
    ...     api_prefix="/api/v2",
    ...     debug=True
    ... )
    """
    app = FastAPI(
        title=title,
        description=description,
        version=version,
        lifespan=lifespan,
        debug=debug,
    )

    # Add CORS if enabled (must be added before routes)
    if enable_cors:
        add_cors_middleware(app, allow_origins=cors_origins)

    # Register all routers
    register_all_routers(app, all_routers, prefix=api_prefix)

    # Add health check
    add_health_check(app)

    # Add error handlers
    add_error_handlers(app)

    # Add rate limiting if enabled
    if enable_rate_limiting:
        add_rate_limiting(app, default_limits=rate_limits, storage_uri=rate_limit_storage)

    logger.info(f"FastAPI app '{title}' v{version} setup complete")

    init_db()

    return app


def setup_fastapi_app(        
    app: FastAPI,
    all_routers: list[APIRouter],    
    *,
    enable_rate_limiting: bool = False,
    rate_limits: list[str] | None = None,
    rate_limit_storage: str = "memory://",
    enable_cors: bool = False,
    cors_origins: list[str] | None = None,
    api_prefix: str = "/api/v1",
) -> None:
    """Complete setup for an existing FastAPI app with all routers and optional features.

    Parameters
    ----------
    app : FastAPI
        The FastAPI application instance
    all_routers: 
        All of the routers to put in the app
    enable_rate_limiting : bool
        Whether to enable rate limiting (default: False)
    rate_limits : list[str] | None
        Rate limit rules (default: ["1000 per day", "100 per hour"])
    rate_limit_storage : str
        Storage URI for rate limiting (default: "memory://")
    enable_cors : bool
        Whether to enable CORS (default: False)
    cors_origins : list[str] | None
        Allowed CORS origins (default: ["*"])
    api_prefix : str
        API route prefix (default: "/api/v1")

    Example
    -------
    >>> from fastapi import FastAPI
    >>> app = FastAPI()
    >>> setup_fastapi_app(
    ...     app,
    ...     enable_rate_limiting=True,
    ...     enable_cors=True,
    ...     api_prefix="/api/v2"
    ... )

    Note
    ----
    This function modifies the app in-place.
    CORS middleware must be added before routes.
    """
    # Add CORS if enabled (must be added before routes)
    if enable_cors:
        add_cors_middleware(app, allow_origins=cors_origins)

    # Register all routers
    register_all_routers(app, all_routers, prefix=api_prefix)

    # Add health check
    add_health_check(app)

    # Add error handlers
    add_error_handlers(app)

    # Optional features
    if enable_rate_limiting:
        add_rate_limiting(app, default_limits=rate_limits, storage_uri=rate_limit_storage)

    logger.info("FastAPI app setup complete")
