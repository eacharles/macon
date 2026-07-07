"""Tests for macon.cli.server — server CLI command and options."""

from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from macon.cli.server.top import serve
from macon.cli.server import options


class TestServerOptions:
    def test_host_option(self):
        assert options.host is not None

    def test_port_option(self):
        assert options.port is not None

    def test_reload_option(self):
        assert options.reload is not None

    def test_workers_option(self):
        assert options.workers is not None

    def test_log_level_option(self):
        assert options.log_level is not None

    def test_api_prefix_option(self):
        assert options.api_prefix is not None

    def test_enable_rate_limiting_option(self):
        assert options.enable_rate_limiting is not None

    def test_rate_limit_storage_option(self):
        assert options.rate_limit_storage is not None

    def test_enable_cors_option(self):
        assert options.enable_cors is not None

    def test_cors_origins_option(self):
        assert options.cors_origins is not None

    def test_debug_option(self):
        assert options.debug is not None


class TestServeCommand:
    @patch("macon.cli.server.top.uvicorn.run")
    @patch("macon.cli.server.top.create_fastapi_app")
    def test_serve_defaults(self, mock_create_app, mock_uvicorn_run):
        mock_create_app.return_value = MagicMock()
        runner = CliRunner()

        result = runner.invoke(serve)

        assert result.exit_code == 0
        mock_create_app.assert_called_once()
        mock_uvicorn_run.assert_called_once()
        call_kwargs = mock_uvicorn_run.call_args[1]
        assert call_kwargs["host"] == "0.0.0.0"
        assert call_kwargs["port"] == 8000
        assert call_kwargs["log_level"] == "info"
        assert call_kwargs["workers"] == 1

    @patch("macon.cli.server.top.uvicorn.run")
    @patch("macon.cli.server.top.create_fastapi_app")
    def test_serve_with_reload(self, mock_create_app, mock_uvicorn_run):
        mock_create_app.return_value = MagicMock()
        runner = CliRunner()

        result = runner.invoke(serve, ["--reload"])

        assert result.exit_code == 0
        call_kwargs = mock_uvicorn_run.call_args[1]
        assert call_kwargs["reload"] is True
        assert "workers" not in call_kwargs
        assert "development mode" in result.output

    @patch("macon.cli.server.top.uvicorn.run")
    @patch("macon.cli.server.top.create_fastapi_app")
    def test_serve_production_mode(self, mock_create_app, mock_uvicorn_run):
        mock_create_app.return_value = MagicMock()
        runner = CliRunner()

        result = runner.invoke(serve, ["--workers", "4", "--port", "9000", "--host", "127.0.0.1"])

        assert result.exit_code == 0
        call_kwargs = mock_uvicorn_run.call_args[1]
        assert call_kwargs["workers"] == 4
        assert call_kwargs["port"] == 9000
        assert call_kwargs["host"] == "127.0.0.1"
        assert "production mode" in result.output

    @patch("macon.cli.server.top.uvicorn.run")
    @patch("macon.cli.server.top.create_fastapi_app")
    def test_serve_with_debug(self, mock_create_app, mock_uvicorn_run):
        mock_create_app.return_value = MagicMock()
        runner = CliRunner()

        result = runner.invoke(serve, ["--debug"])

        assert result.exit_code == 0
        create_kwargs = mock_create_app.call_args[1]
        assert create_kwargs["debug"] is True

    @patch("macon.cli.server.top.uvicorn.run")
    @patch("macon.cli.server.top.create_fastapi_app")
    def test_serve_custom_api_prefix(self, mock_create_app, mock_uvicorn_run):
        mock_create_app.return_value = MagicMock()
        runner = CliRunner()

        result = runner.invoke(serve, ["--api-prefix", "/api/v2"])

        assert result.exit_code == 0
        create_kwargs = mock_create_app.call_args[1]
        assert create_kwargs["api_prefix"] == "/api/v2"

    @patch("macon.cli.server.top.uvicorn.run")
    @patch("macon.cli.server.top.create_fastapi_app")
    def test_serve_rate_limiting(self, mock_create_app, mock_uvicorn_run):
        mock_create_app.return_value = MagicMock()
        runner = CliRunner()

        result = runner.invoke(serve, ["--enable-rate-limiting", "--rate-limit-storage", "redis://host"])

        assert result.exit_code == 0
        create_kwargs = mock_create_app.call_args[1]
        assert create_kwargs["enable_rate_limiting"] is True
        assert create_kwargs["rate_limit_storage"] == "redis://host"

    @patch("macon.cli.server.top.uvicorn.run")
    @patch("macon.cli.server.top.create_fastapi_app")
    def test_serve_cors_options(self, mock_create_app, mock_uvicorn_run):
        mock_create_app.return_value = MagicMock()
        runner = CliRunner()

        result = runner.invoke(serve, ["--enable-cors", "--cors-origins", "http://a.com,http://b.com"])

        assert result.exit_code == 0
        create_kwargs = mock_create_app.call_args[1]
        assert create_kwargs["enable_cors"] is True
        assert create_kwargs["cors_origins"] == ["http://a.com", "http://b.com"]

    @patch("macon.cli.server.top.uvicorn.run")
    @patch("macon.cli.server.top.create_fastapi_app")
    def test_serve_no_rate_limiting(self, mock_create_app, mock_uvicorn_run):
        mock_create_app.return_value = MagicMock()
        runner = CliRunner()

        result = runner.invoke(serve, ["--no-rate-limiting"])

        assert result.exit_code == 0
        create_kwargs = mock_create_app.call_args[1]
        assert create_kwargs["enable_rate_limiting"] is False

    @patch("macon.cli.server.top.uvicorn.run")
    @patch("macon.cli.server.top.create_fastapi_app")
    def test_serve_output_messages(self, mock_create_app, mock_uvicorn_run):
        mock_create_app.return_value = MagicMock()
        runner = CliRunner()

        result = runner.invoke(serve, ["--port", "5000", "--api-prefix", "/v1"])

        assert result.exit_code == 0
        assert "5000" in result.output
        assert "/v1" in result.output
        assert "/health" in result.output
        assert "/docs" in result.output
