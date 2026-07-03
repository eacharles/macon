import click
import uvicorn

from ...router.app import create_fastapi_app
from . import options

# ============================================================================
# CLI ENTRY POINT
# ============================================================================


@click.command()
@options.host()
@options.port()
@options.reload()
@options.workers()
@options.log_level()
@options.api_prefix()
@options.enable_rate_limiting()
@options.rate_limit_storage()
@options.enable_cors()
@options.cors_origins()
@options.debug()
def serve(
    *,
    host: str,
    port: int,
    reload: bool,
    workers: int,
    log_level: str,
    api_prefix: str,
    enable_rate_limiting: bool,
    rate_limit_storage: str,
    enable_cors: bool,
    cors_origins: str,
    debug: bool,
) -> None:
    """Start the FastAPI server.

    Examples:
        # Development mode with auto-reload
        rail-svc-server --reload --debug

        # Production mode with multiple workers
        rail-svc-server --host 0.0.0.0 --port 8000 --workers 4

        # Custom API prefix
        rail-svc-server --api-prefix /api/v2

        # With Redis rate limiting
        rail-svc-server --rate-limit-storage redis://localhost:6379
    """
    # Parse CORS origins
    cors_origins_list = [origin.strip() for origin in cors_origins.split(",")]

    # Create the app with CLI options
    from ...router.test_classes import all_routers

    app = create_fastapi_app(
        all_routers,
        title="Database API",
        description="RESTful API for database operations with full CRUD support",
        version="1.0.0",
        enable_rate_limiting=enable_rate_limiting,
        rate_limits=["1000 per day", "100 per hour"],
        rate_limit_storage=rate_limit_storage,
        enable_cors=enable_cors,
        cors_origins=cors_origins_list,
        api_prefix=api_prefix,
        debug=debug,
    )

    # Configure uvicorn
    uvicorn_config = {
        "host": host,
        "port": port,
        "log_level": log_level,
    }

    if reload:
        # Development mode with auto-reload
        uvicorn_config["reload"] = True
        click.echo(f"Starting server in development mode at http://{host}:{port}")
        click.echo("Auto-reload is enabled")
    else:
        # Production mode with workers
        uvicorn_config["workers"] = workers
        click.echo(f"Starting server in production mode at http://{host}:{port}")
        click.echo(f"Using {workers} worker(s)")

    click.echo(f"API endpoints available at http://{host}:{port}{api_prefix}")
    click.echo(f"Health check at http://{host}:{port}/health")
    click.echo(f"Interactive docs at http://{host}:{port}/docs")

    # Run the server
    uvicorn.run(app, **uvicorn_config)  # type: ignore
