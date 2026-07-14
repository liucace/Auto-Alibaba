import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.domain.errors import ManualReviewRequired
from app.domain.models import DetailDrawingSpec, PackageInfo, ProductImage, ProductPayload
from app.ingest.inventory import load_inventory
from app.ingest.model_number import exact_model_match, model_folder_key, normalize_model
from app.products.detail_assets import prepare_detail_drawing
from app.products.loader import find_source_directory
from app.products.main_images import prepare_square_image


class DrawingEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    page: int = Field(ge=1)
    crop: tuple[float, float, float, float]


class PreparationEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: str
    brand: str = Field(min_length=1)
    pdf_file: str
    title: str
    attributes: dict[str, str]
    specification: dict[str, str | int | float]
    package: PackageInfo
    images: tuple[ProductImage, ...]
    drawing: DrawingEvidence


@dataclass(frozen=True)
class PrepareResult:
    model: str
    price: int
    stock: int
    source_directory: Path
    artifacts_directory: Path
    images: tuple[Path, ...]
    detail_drawing: Path


def _contained(source: Path, relative_value: str, *, label: str) -> Path:
    relative = Path(relative_value)
    if relative.is_absolute():
        raise ManualReviewRequired(f"{label} must be relative to the product source directory")
    resolved_source = source.resolve()
    resolved = (resolved_source / relative).resolve()
    if not resolved.is_relative_to(resolved_source):
        raise ManualReviewRequired(f"{label} escapes the product source directory")
    return resolved


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _pdf_contains_exact_model(path: Path, model: str) -> bool:
    token = re.compile(
        rf"(?<![A-Z0-9/_-]){re.escape(model)}(?![A-Z0-9/_-])",
        flags=re.IGNORECASE,
    )
    labeled_parts = []
    for index, character in enumerate(model):
        if character != "-":
            continue
        left = re.escape(model[:index])
        right = re.escape(model[index + 1 :])
        labeled_parts.append(
            (
                re.compile(
                    rf"(?<![A-Z0-9])MODEL\s*(?:[:：]\s*|\s+)"
                    rf"(?<![A-Z0-9/_-]){left}(?![A-Z0-9/_-])",
                    flags=re.IGNORECASE,
                ),
                re.compile(
                    rf"(?<![A-Z0-9])P\s*/\s*N\s*(?:[:：]\s*|\s+)"
                    rf"(?<![A-Z0-9/_-]){right}(?![A-Z0-9/_-])",
                    flags=re.IGNORECASE,
                ),
            )
        )
    try:
        with fitz.open(path) as document:
            for page in document:
                text = page.get_text("text")
                if token.search(text) is not None:
                    return True
                if any(
                    model_token.search(text) is not None
                    and part_number_token.search(text) is not None
                    for model_token, part_number_token in labeled_parts
                ):
                    return True
            return False
    except (OSError, RuntimeError, ValueError) as error:
        raise ManualReviewRequired(f"product PDF cannot be read: {path}") from error


def prepare_product(root: Path, model: str) -> PrepareResult:
    root = root.resolve()
    normalized = normalize_model(model)
    source = find_source_directory(root, normalized).resolve()
    artifacts = (root / "automation" / model_folder_key(normalized)).resolve()
    evidence_path = artifacts / "preparation_evidence.json"
    if not evidence_path.is_file():
        raise ManualReviewRequired(f"preparation evidence missing: {evidence_path}")
    try:
        evidence = PreparationEvidence.model_validate_json(
            evidence_path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, ValidationError) as error:
        raise ManualReviewRequired(f"preparation evidence is invalid: {evidence_path}") from error
    if not exact_model_match(evidence.model, normalized):
        raise ManualReviewRequired("preparation evidence model does not match requested model")
    if not exact_model_match(str(evidence.specification.get("规格型号", "")), normalized):
        raise ManualReviewRequired("preparation specification model does not match requested model")
    if len(evidence.images) != 4:
        raise ManualReviewRequired("preparation evidence requires exactly four current-model images")

    pdf = _contained(source, evidence.pdf_file, label="product PDF")
    if not pdf.is_file() or not _pdf_contains_exact_model(pdf, normalized):
        raise ManualReviewRequired("product PDF does not contain the exact requested model")
    inventory = load_inventory(root / "price_inventory.xlsx", normalized)

    prepared_items: list[ProductImage] = []
    prepared_paths: list[Path] = []
    for index, image in enumerate(evidence.images, start=1):
        source_image = _contained(source, image.local_file, label=f"main image {index}")
        if not source_image.is_file() or source_image.stat().st_size == 0:
            raise ManualReviewRequired(f"main image does not exist or is empty: {source_image}")
        relative_output = Path("upload_optimized") / f"{source_image.stem}-square.jpg"
        output = _contained(source, str(relative_output), label=f"prepared main image {index}")
        try:
            prepare_square_image(source_image, output)
        except (OSError, ValueError) as error:
            raise ManualReviewRequired(
                f"main image cannot be prepared: {source_image}: {error}"
            ) from error
        prepared_paths.append(output)
        prepared_items.append(
            ProductImage(local_file=relative_output.as_posix(), role=image.role, hosted_url=None)
        )

    payload = ProductPayload(
        model=normalized,
        brand=evidence.brand,
        title=evidence.title,
        category_id=1034320,
        industry_category_id=2293,
        attributes=evidence.attributes,
        specification=evidence.specification,
        price=inventory.price,
        stock=inventory.stock,
        delivery_time="48小时发货",
        shipping_template="运费",
        package=evidence.package,
    )
    detail = DetailDrawingSpec(
        model=normalized,
        pdf_file=evidence.pdf_file,
        page=evidence.drawing.page,
        crop=evidence.drawing.crop,
        local_file="upload_optimized/detail-drawing.jpg",
        hosted_url=None,
    )
    drawing = prepare_detail_drawing(source, detail)
    _write_json(artifacts / "1688_payload.json", payload.model_dump(mode="json"))
    _write_json(
        artifacts / "image_analysis.json",
        {"model": normalized, "images": [item.model_dump(mode="json") for item in prepared_items]},
    )
    _write_json(artifacts / "detail_assets.json", detail.model_dump(mode="json"))
    return PrepareResult(
        model=normalized,
        price=inventory.price,
        stock=inventory.stock,
        source_directory=source,
        artifacts_directory=artifacts,
        images=tuple(prepared_paths),
        detail_drawing=drawing,
    )
