from pathlib import Path

import fitz
import pytest
from pydantic import ValidationError

from app.domain.errors import ManualReviewRequired
from app.domain.models import DetailDrawingSpec
from app.products.detail_assets import prepare_detail_drawing


def _make_pdf(path: Path) -> None:
    document = fitz.open()
    document.new_page()
    page = document.new_page(width=600, height=800)
    page.insert_text((80, 100), "W3G710-NU31-03", fontsize=24)
    page.draw_rect(fitz.Rect(80, 140, 520, 560), width=3)
    document.save(path)
    document.close()


def _spec(**updates: object) -> DetailDrawingSpec:
    values: dict[str, object] = {
        "model": "W3G710-NU31-03",
        "pdf_file": "sheet.pdf",
        "page": 2,
        "crop": (0.05, 0.08, 0.95, 0.75),
        "local_file": "upload_optimized/detail-drawing.jpg",
    }
    values.update(updates)
    return DetailDrawingSpec.model_validate(values)


def test_prepare_detail_drawing_renders_configured_page_and_crop(tmp_path: Path) -> None:
    _make_pdf(tmp_path / "sheet.pdf")

    result = prepare_detail_drawing(tmp_path, _spec())

    assert result == (tmp_path / "upload_optimized" / "detail-drawing.jpg").resolve()
    assert result.is_file()
    assert result.stat().st_size > 0
    pixmap = fitz.Pixmap(result)
    assert pixmap.width > pixmap.height


def test_prepare_detail_drawing_reuses_nonempty_cache(tmp_path: Path) -> None:
    _make_pdf(tmp_path / "sheet.pdf")
    result = prepare_detail_drawing(tmp_path, _spec())
    modified = result.stat().st_mtime_ns

    assert prepare_detail_drawing(tmp_path, _spec()) == result
    assert result.stat().st_mtime_ns == modified


@pytest.mark.parametrize(
    "crop",
    [
        (-0.1, 0.1, 0.9, 0.8),
        (0.1, 0.1, 1.1, 0.8),
        (0.9, 0.1, 0.1, 0.8),
        (0.1, 0.8, 0.9, 0.1),
    ],
)
def test_detail_drawing_spec_rejects_invalid_crop(crop: tuple[float, ...]) -> None:
    with pytest.raises(ValidationError):
        _spec(crop=crop)


def test_detail_drawing_spec_rejects_page_zero() -> None:
    with pytest.raises(ValidationError):
        _spec(page=0)


def test_prepare_detail_drawing_rejects_missing_pdf(tmp_path: Path) -> None:
    with pytest.raises(ManualReviewRequired, match="PDF"):
        prepare_detail_drawing(tmp_path, _spec())


def test_prepare_detail_drawing_rejects_page_out_of_range(tmp_path: Path) -> None:
    _make_pdf(tmp_path / "sheet.pdf")

    with pytest.raises(ManualReviewRequired, match="page"):
        prepare_detail_drawing(tmp_path, _spec(page=3))
