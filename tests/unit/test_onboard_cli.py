import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import app.cli as cli_module
from app.domain.errors import ManualReviewRequired
from app.products.onboarding import OnboardingResult


def _result(tmp_path: Path, status: str) -> OnboardingResult:
    model = None if status == "NEEDS_MODEL" else "REAL-AC-FAN/01"
    folder_key = None if model is None else "REAL-AC-FAN01"
    return OnboardingResult(
        ok=status == "READY_TO_UPLOAD",
        status=status,
        model=model,
        folder_key=folder_key,
        created=(),
        checks={},
        paths={
            "project_root": str(tmp_path),
            "inventory_workbook": str(tmp_path / "price_inventory.xlsx"),
            "source_directory": str(
                tmp_path / "data" / "draft_saved" / "REAL-AC-FAN01"
            ),
        },
        next_action="下一步",
        message="状态说明",
    )


def test_onboard_without_model_returns_actionable_state_and_exit_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    expected = _result(tmp_path, "NEEDS_MODEL")
    monkeypatch.setattr(cli_module, "onboard_product", lambda root, model: expected)

    result = CliRunner().invoke(cli_module.app, ["onboard", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == expected.to_dict()


def test_onboard_forwards_explicit_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}

    def fake(root: Path, model: str | None) -> OnboardingResult:
        captured.update(root=root, model=model)
        return _result(tmp_path, "NEEDS_PRICE_STOCK")

    monkeypatch.setattr(cli_module, "onboard_product", fake)
    result = CliRunner().invoke(
        cli_module.app,
        ["onboard", "--root", str(tmp_path), "--model", "REAL-AC-FAN/01"],
    )

    assert result.exit_code == 0
    assert captured["root"] == tmp_path.resolve()
    assert captured["model"] == "REAL-AC-FAN/01"


def test_onboard_open_opens_only_inventory_and_source_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    expected = _result(tmp_path, "NEEDS_SOURCE_FILES")
    opened: list[Path] = []
    monkeypatch.setattr(cli_module, "onboard_product", lambda root, model: expected)
    monkeypatch.setattr(cli_module, "open_local_path", opened.append)

    result = CliRunner().invoke(
        cli_module.app,
        [
            "onboard",
            "--root",
            str(tmp_path),
            "--model",
            "REAL-AC-FAN/01",
            "--open",
        ],
    )

    assert result.exit_code == 0
    assert opened == [
        Path(expected.paths["inventory_workbook"]),
        Path(expected.paths["source_directory"]),
    ]


def test_onboard_open_without_model_does_not_open_any_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    expected = _result(tmp_path, "NEEDS_MODEL")

    def unexpected(path: Path) -> None:
        raise AssertionError(f"unexpected path open: {path}")

    monkeypatch.setattr(cli_module, "onboard_product", lambda root, model: expected)
    monkeypatch.setattr(cli_module, "open_local_path", unexpected)

    result = CliRunner().invoke(
        cli_module.app, ["onboard", "--root", str(tmp_path), "--open"]
    )

    assert result.exit_code == 0


def test_open_local_path_rejects_missing_target_without_creating_it(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing"

    with pytest.raises(ManualReviewRequired, match="路径不存在"):
        cli_module.open_local_path(missing)

    assert not missing.exists()


def test_onboard_blocked_is_json_and_exit_two(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fail(root: Path, model: str | None) -> OnboardingResult:
        raise ManualReviewRequired("库存表被占用或格式错误；未覆盖原文件")

    monkeypatch.setattr(cli_module, "onboard_product", fail)
    result = CliRunner().invoke(
        cli_module.app,
        ["onboard", "--root", str(tmp_path), "--model", "REAL-AC-FAN/01"],
    )

    payload = json.loads(result.stdout)
    assert result.exit_code == 2
    assert payload["status"] == "BLOCKED"
    assert "未覆盖原文件" in payload["message"]
