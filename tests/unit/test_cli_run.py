from pathlib import Path

from typer.testing import CliRunner

import app.cli as cli_module
from app.publisher.orchestrator import UploadResult


def test_task_state_records_evidence_driven_detail_metadata(tmp_path: Path) -> None:
    html = tmp_path / "detail.html"
    result = UploadResult(
        model="W3G710-NU31-03",
        errors=0,
        advice=("视频",),
        ready_to_save=True,
        detail_drawing_url="https://cbu01.alicdn.com/img/ibank/drawing.jpg",
        detail_html_path=html,
        detail_image_count=5,
    )

    state = cli_module.build_task_state(
        result=result,
        cdp_url="http://127.0.0.1:9223",
        page_url="https://offer-new.1688.com/industry/publish.htm",
    )

    assert state["status"] == "READY_TO_SAVE"
    assert state["detail"] == {
        "template_version": "evidence-driven-v2",
        "local_html": str(html),
        "drawing_url": "https://cbu01.alicdn.com/img/ibank/drawing.jpg",
        "image_count": 5,
    }


def test_run_command_is_dry_run_and_reports_ready(monkeypatch, tmp_path: Path) -> None:
    async def fake_run(*, root: Path, model: str, cdp_url: str):
        assert root == tmp_path
        assert model == "W3G630-NU33-03"
        assert cdp_url == "http://127.0.0.1:9223"
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
    async def fake_run(*, root: Path, model: str, cdp_url: str):
        return cli_module.CommandResult(model=model, errors=2, advice=(), ready=False)

    monkeypatch.setattr(cli_module, "run_product", fake_run)
    result = CliRunner().invoke(
        cli_module.app,
        ["run", "W3G630-NU33-03", "--root", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert "BLOCKED" in result.stdout
