"""Tests for CLI tool (v1.0.0 - #15)."""


class TestCliModule:
    """Tests for CLI module structure."""

    def test_cli_module_exists(self) -> None:
        """Test that pyetwkit.cli module exists."""
        from pyetwkit import cli  # noqa: F401

        assert True

    def test_main_function_exists(self) -> None:
        """Test that main function exists."""
        from pyetwkit.cli import main

        assert callable(main)


class TestCliCommands:
    """Tests for CLI commands."""

    def test_cli_help(self) -> None:
        """Test that --help works."""
        from click.testing import CliRunner

        from pyetwkit.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_cli_version(self) -> None:
        """Test that --version works."""
        from click.testing import CliRunner

        from pyetwkit.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0

    def test_cli_providers_command(self) -> None:
        """Test that providers command exists."""
        from click.testing import CliRunner

        from pyetwkit.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["providers", "--help"])
        assert result.exit_code == 0

    def test_cli_listen_command(self) -> None:
        """Test that listen command exists."""
        from click.testing import CliRunner

        from pyetwkit.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["listen", "--help"])
        assert result.exit_code == 0

    def test_cli_profiles_command(self) -> None:
        """Test that profiles command exists."""
        from click.testing import CliRunner

        from pyetwkit.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["profiles", "--help"])
        assert result.exit_code == 0


class TestProvidersCommand:
    """Tests for providers command."""

    def test_providers_list(self) -> None:
        """Test listing providers."""
        from click.testing import CliRunner

        from pyetwkit.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["providers"])
        assert result.exit_code == 0
        # Should list some providers
        assert "Microsoft" in result.output or "Provider" in result.output

    def test_providers_search(self) -> None:
        """Test searching providers."""
        from click.testing import CliRunner

        from pyetwkit.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["providers", "--search", "Kernel"])
        assert result.exit_code == 0


class TestProfilesCommand:
    """Tests for profiles command."""

    def test_profiles_list(self) -> None:
        """Test listing profiles."""
        from click.testing import CliRunner

        from pyetwkit.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["profiles"])
        assert result.exit_code == 0
        # Should show built-in profiles
        assert "audio" in result.output.lower() or "network" in result.output.lower()


class TestListenCommand:
    """Tests for listen command."""

    def test_listen_requires_provider_or_profile(self) -> None:
        """Test that listen requires provider or profile."""
        from click.testing import CliRunner

        from pyetwkit.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["listen"])
        # Should fail or show error without provider/profile
        assert (
            result.exit_code != 0
            or "error" in result.output.lower()
            or "usage" in result.output.lower()
        )

    def test_listen_format_option(self) -> None:
        """Test that listen has format option."""
        from click.testing import CliRunner

        from pyetwkit.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["listen", "--help"])
        assert "--format" in result.output or "-f" in result.output

    def test_listen_output_option(self) -> None:
        """Test that listen has output option."""
        from click.testing import CliRunner

        from pyetwkit.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["listen", "--help"])
        assert "--output" in result.output or "-o" in result.output
