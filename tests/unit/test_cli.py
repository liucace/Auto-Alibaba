from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

import app.cli as cli_module
from app.cli import app


def test_version_command() -> None:
    result = CliRunner().invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "1688-draft-automation 0.1.0"


def test_prepare_command_reports_structured_result(monkeypatch, tmp_path: Path) -> None:
    def fake_prepare(root: Path, model: str):
        assert root == tmp_path
        assert model == "W3G800-KS39-03/F01"
        return SimpleNamespace(
            model=model,
            price=10000,
            stock=10,
            source_directory=tmp_path / "data",
            artifacts_directory=tmp_path / "automation",
            images=(tmp_path / "one.jpg",) * 4,
            detail_drawing=tmp_path / "drawing.jpg",
        )

    monkeypatch.setattr(cli_module, "prepare_product", fake_prepare, raising=False)
    result = CliRunner().invoke(
        app,
        ["prepare", "W3G800-KS39-03/F01", "--root", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert '"status":"PREPARED"' in result.stdout
    assert '"model":"W3G800-KS39-03/F01"' in result.stdout
