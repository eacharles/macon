"""CLI entry point for rail-svc-client remote operations."""

import click

from ... import __version__
from .test_classes import test_named_group, test_ref_group, test_list_pair_group


@click.group(
    name="macon-remote",
    commands=[test_named_group, test_ref_group, test_list_pair_group],
)
@click.version_option(version=__version__)
@click.option(
    "--base-url",
    envvar="RAIL_SVC_BASE_URL",
    help="Base URL of the rail-svc API server",
)
@click.option(
    "--timeout",
    type=float,
    default=30.0,
    help="Request timeout in seconds (default: 30.0)",
)
@click.option(
    "--auth-token",
    envvar="RAIL_SVC_AUTH_TOKEN",
    help="Authentication token for API requests",
)
@click.pass_context
def cli(ctx: click.Context, base_url: str | None, timeout: float, auth_token: str | None) -> None:
    """Administrative CLI for rail-svc remote operations.

    This CLI interacts with a remote rail-svc API server via HTTP.
    Configure the base URL with --base-url or RAIL_SVC_BASE_URL env var.

    Examples:
        rail-svc-client-remote --base-url http://localhost:8000 algorithm get-rows
        RAIL_SVC_BASE_URL=http://api.example.com rail-svc-client-remote band count
    """
    # Store configuration in context for potential use by subcommands
    ctx.ensure_object(dict)
    ctx.obj["base_url"] = base_url
    ctx.obj["timeout"] = timeout
    ctx.obj["auth_token"] = auth_token


if __name__ == "__main__":
    cli()  # pylint: disable=no-value-for-parameter
