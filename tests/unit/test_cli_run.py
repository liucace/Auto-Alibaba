from pathlib import Path

from typer.testing import CliRunner

import app.cli as cli_module


def test_run_command_is_dry_run_and_reports_ready(monkeypatch, tmp_path: Path) -> None:
    async def fake_run(*, root: Path, model: str, cdp_url: str, albums: tuple[str, ...]):
        assert root == tmp_path
        assert model == "W3G630-NU33-03"
        assert cdp_url == "http://127.0.0.1:9223"
        assert albums[0] == "ebm(L)"
        return cli_module.CommandResult(model=model, errors=0, advice=("视频",), ready=True)

    monkeypatch.setattr(cli_module, "run_product", fake_run)

    result = CliRunner().invoke(
        cli_module.app,
        ["run", "W3G630-NU33-03", "--root", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert "READY_TO_SAVE" in result.stdout
    assert "stopped before save" in result.stdout


def test_run_command_returns_nonzero_for_blocking_errors(monkeypatch, tmp_path: Path) -> None:
    async def fake_run(*, root: Path, model: str, cdp_url: str, albums: tuple[str, ...]):
        return cli_module.CommandResult(model=model, errors=2, advice=(), ready=False)

    monkeypatch.setattr(cli_module, "run_product", fake_run)
    result = CliRunner().invoke(
        cli_module.app,
        ["run", "W3G630-NU33-03", "--root", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert "BLOCKED" in result.stdout
