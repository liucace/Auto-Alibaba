from pathlib import Path

import openpyxl
import pytest

from app.domain.errors import ModelRowNotFound
from app.ingest.inventory import load_inventory


@pytest.fixture
def workbook_path(tmp_path: Path) -> Path:
    path = tmp_path / "price_inventory.xlsx"
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["型号", "价格", "库存"])
    sheet.append(["W3G630-NU33-03", 10000, 10])
    sheet.append(["A2E250-AL06-01", None, None])
    book.save(path)
    return path


def test_missing_model_row_stops_product(workbook_path: Path) -> None:
    with pytest.raises(ModelRowNotFound):
        load_inventory(workbook_path, "W3G630-NU33-99")


def test_blank_price_and_stock_use_defaults(workbook_path: Path) -> None:
    row = load_inventory(workbook_path, "A2E250-AL06-01")
    assert row.price == 10000
    assert row.stock == 50


def test_existing_values_are_preserved(workbook_path: Path) -> None:
    row = load_inventory(workbook_path, "W3G630-NU33-03")
    assert row.price == 10000
    assert row.stock == 10
