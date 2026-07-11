import json
from pathlib import Path
from typing import Any

import pymupdf

from app.domain.errors import ManualReviewRequired
from app.domain.models import DetailDrawingSpec

fitz: Any = pymupdf


def _contained_path(root: Path, relative: str, *, label: str) -> Path:
    resolved_root = root.resolve()
    resolved = (resolved_root / relative).resolve()
    if not resolved.is_relative_to(resolved_root):
        raise ManualReviewRequired(f"{label} escapes the product source directory")
    return resolved


def prepare_detail_drawing(source: Path, spec: DetailDrawingSpec) -> Path:
    output = _contained_path(source, spec.local_file, label="detail drawing output")
    if output.is_file() and output.stat().st_size > 0:
        return output
    pdf_path = _contained_path(source, spec.pdf_file, label="detail drawing PDF")
    if not pdf_path.is_file():
        raise ManualReviewRequired(f"detail drawing PDF does not exist: {pdf_path}")

    try:
        document = fitz.open(pdf_path)
    except Exception as error:
        raise ManualReviewRequired(f"detail drawing PDF cannot be opened: {pdf_path}") from error
    try:
        page_index = spec.page - 1
        if page_index >= document.page_count:
            raise ManualReviewRequired(
                f"detail drawing page {spec.page} exceeds PDF page count {document.page_count}"
            )
        page = document[page_index]
        x0, y0, x1, y1 = spec.crop
        page_rect = page.rect
        clip = fitz.Rect(
            page_rect.x0 + page_rect.width * x0,
            page_rect.y0 + page_rect.height * y0,
            page_rect.x0 + page_rect.width * x1,
            page_rect.y0 + page_rect.height * y1,
        )
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip, alpha=False)
        output.parent.mkdir(parents=True, exist_ok=True)
        pixmap.save(output, jpg_quality=90)
    finally:
        document.close()
    if not output.is_file() or output.stat().st_size == 0:
        raise ManualReviewRequired("detail drawing renderer produced no image")
    return output


def update_detail_hosted_url(path: Path, url: str) -> None:
    if not url.startswith("https://cbu01.alicdn.com/img/ibank/"):
        raise ManualReviewRequired(f"unexpected hosted detail image URL: {url}")
    loaded: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ManualReviewRequired("detail assets must be a JSON object")
    loaded["hosted_url"] = url
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(loaded, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
