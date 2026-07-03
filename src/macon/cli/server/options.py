import click

from ..common_options import PartialOption

host = PartialOption(
    "--host",
    default="0.0.0.0",
    help="Host to bind to (default: 0.0.0.0)",
)

port = PartialOption(
    "--port",
    default=8000,
    type=int,
    help="Port to bind to (default: 8000)",
)

reload = PartialOption(
    "--reload",
    is_flag=True,
    help="Enable auto-reload for development",
)

workers = PartialOption(
    "--workers",
    default=1,
    type=int,
    help="Number of worker processes (default: 1)",
)

log_level = PartialOption(
    "--log-level",
    default="info",
    type=click.Choice(["critical", "error", "warning", "info", "debug", "trace"]),
    help="Log level (default: info)",
)

api_prefix = PartialOption(
    "--api-prefix",
    default="/api/v1",
    help="API route prefix (default: /api/v1)",
)

enable_rate_limiting = PartialOption(
    "--enable-rate-limiting/--no-rate-limiting",
    default=True,
    help="Enable rate limiting (default: enabled)",
)

rate_limit_storage = PartialOption(
    "--rate-limit-storage",
    default="memory://",
    help="Rate limit storage URI (default: memory://)",
)

enable_cors = PartialOption(
    "--enable-cors/--no-cors",
    default=True,
    help="Enable CORS (default: enabled)",
)

cors_origins = PartialOption(
    "--cors-origins",
    default="*",
    help="Allowed CORS origins (comma-separated, default: *)",
)

debug = PartialOption(
    "--debug/--no-debug",
    default=False,
    help="Enable debug mode (default: disabled)",
)
