import json
from pathlib import Path

from typer.testing import CliRunner

import app.cli as cli_module
from app.domain.errors import ManualReviewRequired
from app.products.input_onboarding import InputRequirement, ProductInputResult


def test_init_product_emits_needs_input_json_and_exit_two(
    monkeypatch, tmp_path: Path
) -> None:
    expected = ProductInputResult(
        ok=False,
        status="NEEDS_INPUT",
        model="W3G800-KS39-03/F01",
        folder_key="W3G800-KS39-03F01",
        created=(str(tmp_path / "price_inventory.xlsx"),),
        checks={"pdf_files": 0, "source_images": 0},
        requirements=(
            InputRequirement(
                key="inventory",
                path=str(tmp_path / "price_inventory.xlsx"),
                purpose="提供当前完整型号的1688价格和库存。",
                action="打开表格核对数据。",
                ready=False,
            ),
        ),
        message="请补充资料。",
    )
    monkeypatch.setattr(cli_module, "initialize_product_inputs", lambda root, model: expected)

    result = CliRunner().invoke(
        cli_module.app,
        ["init-product", "W3G800-KS39-03/F01", "--root", str(tmp_path)],
    )

    assert result.exit_code == 2
    assert json.loads(result.stdout) == expected.to_dict()


def test_init_product_emits_ready_json_and_exit_zero(monkeypatch, tmp_path: Path) -> None:
    expected = ProductInputResult(
        ok=True,
        status="READY",
        model="W3G800-KS39-03/F01",
        folder_key="W3G800-KS39-03F01",
        created=(),
        checks={"pdf_files": 1, "source_images": 4},
        requirements=(),
        message="商品资料已齐全。",
    )
    monkeypatch.setattr(cli_module, "initialize_product_inputs", lambda root, model: expected)

    result = CliRunner().invoke(
        cli_module.app,
        ["init-product", "W3G800-KS39-03/F01", "--root", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout)["status"] == "READY"


def test_init_product_reports_safe_block_for_invalid_workbook(
    monkeypatch, tmp_path: Path
) -> None:
    def fail(root: Path, model: str) -> ProductInputResult:
        raise ManualReviewRequired("库存表无法读取，未覆盖原文件")

    monkeypatch.setattr(cli_module, "initialize_product_inputs", fail)
    result = CliRunner().invoke(
        cli_module.app,
        ["init-product", "W3G800-KS39-03/F01", "--root", str(tmp_path)],
    )

    payload = json.loads(result.stdout)
    assert result.exit_code == 2
    assert payload["status"] == "BLOCKED"
    assert "未覆盖原文件" in payload["message"]
