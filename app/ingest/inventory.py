from pathlib import Path

import openpyxl

from app.domain.errors import ModelRowNotFound
from app.domain.models import InventoryRecord
from app.ingest.model_number import normalize_model


def load_inventory(
    workbook_path: Path,
    model: str,
    *,
    default_price: int = 10000,
    default_stock: int = 50,
) -> InventoryRecord:
    wanted = normalize_model(model)
    book = openpyxl.load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        sheet = book.active
        for raw_model, price, stock, *_ in sheet.iter_rows(min_row=2, values_only=True):
            if raw_model is None or normalize_model(str(raw_model)) != wanted:
                continue
            return InventoryRecord(
                model=wanted,
                price=default_price if price in (None, "") else int(price),
                stock=default_stock if stock in (None, "") else int(stock),
            )
    finally:
        book.close()
    raise ModelRowNotFound(f"model row does not exist: {wanted}")
