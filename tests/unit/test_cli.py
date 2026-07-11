from typer.testing import CliRunner

from app.cli import app


def test_version_command() -> None:
    result = CliRunner().invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "1688-draft-automation 0.1.0"
