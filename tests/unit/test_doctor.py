from pathlib import Path

from typer.testing import CliRunner

import app.cli as cli_module


def test_doctor_reports_required_dependencies(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        cli_module,
        "doctor_checks",
        lambda root, cdp_url: [
            ("Python 3.12+", True, "3.14"),
            ("price_inventory.xlsx", True, str(root)),
            ("Chrome CDP 9223", True, cdp_url),
        ],
    )

    result = CliRunner().invoke(
        cli_module.app,
        ["doctor", "--root", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert "Python 3.12+: OK" in result.stdout
    assert "Chrome CDP 9223: OK" in result.stdout
