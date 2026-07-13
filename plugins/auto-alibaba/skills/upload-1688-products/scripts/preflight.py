from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image

MAX_MAIN_IMAGE_BYTES = 5_000_000
EXPECTED_CATEGORY_ID = 1034320
EXPECTED_INDUSTRY_CATEGORY_ID = 2293
EXPECTED_DELIVERY = "48小时发货"
EXPECTED_SHIPPING = "运费"


def _load_project_api(root: Path) -> dict[str, Any]:
    resolved = str(root.resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)
    from app.domain.models import DetailDrawingSpec, ProductImage, ProductPayload
    from app.ingest.inventory import load_inventory
    from app.ingest.model_number import exact_model_match, model_folder_key, normalize_model
    from app.products.loader import find_source_directory
    from app.products.main_images import media_fingerprint
    from app.publisher.form_plan import build_form_plan

    return {
        "DetailDrawingSpec": DetailDrawingSpec,
        "ProductImage": ProductImage,
        "ProductPayload": ProductPayload,
        "load_inventory": load_inventory,
        "exact_model_match": exact_model_match,
        "model_folder_key": model_folder_key,
        "media_fingerprint": media_fingerprint,
        "normalize_model": normalize_model,
        "find_source_directory": find_source_directory,
        "build_form_plan": build_form_plan,
    }


def _read_object(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"JSON must contain an object: {path}")
    return loaded


def _contained_path(source: Path, value: str, *, label: str) -> Path:
    relative = Path(value)
    if relative.is_absolute():
        raise ValueError(f"{label} escapes the selected product source directory")
    resolved_source = source.resolve()
    resolved = (resolved_source / relative).resolve()
    if not resolved.is_relative_to(resolved_source):
        raise ValueError(f"{label} escapes the selected product source directory")
    return resolved


def image_dimensions(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def _check_product(root: Path, model: str, *, reuse_main_images: bool) -> dict[str, Any]:
    api = _load_project_api(root)
    normalized = api["normalize_model"](model)
    inventory = api["load_inventory"](root / "price_inventory.xlsx", normalized)
    source = api["find_source_directory"](root, normalized).resolve()
    artifacts = (root / "automation" / api["model_folder_key"](normalized)).resolve()

    paths = {
        "payload": artifacts / "1688_payload.json",
        "images": artifacts / "image_analysis.json",
        "detail": artifacts / "detail_assets.json",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise ValueError(f"prepared artifacts missing: {missing}")

    raw_payload = _read_object(paths["payload"])
    raw_images = _read_object(paths["images"])
    raw_detail = _read_object(paths["detail"])
    exact = api["exact_model_match"]
    for label, loaded in (
        ("payload", raw_payload),
        ("image analysis", raw_images),
        ("detail assets", raw_detail),
    ):
        if not exact(str(loaded.get("model", "")), normalized):
            raise ValueError(f"{label} model does not match requested model")

    raw_payload["price"] = inventory.price
    raw_payload["stock"] = inventory.stock
    payload = api["ProductPayload"].model_validate(raw_payload)
    if not payload.title.strip():
        raise ValueError("product title is empty")
    if payload.category_id != EXPECTED_CATEGORY_ID:
        raise ValueError(f"category_id must be {EXPECTED_CATEGORY_ID}")
    if payload.industry_category_id != EXPECTED_INDUSTRY_CATEGORY_ID:
        raise ValueError(f"industry_category_id must be {EXPECTED_INDUSTRY_CATEGORY_ID}")
    if payload.delivery_time != EXPECTED_DELIVERY:
        raise ValueError(f"delivery_time must be {EXPECTED_DELIVERY}")
    if payload.shipping_template != EXPECTED_SHIPPING:
        raise ValueError(f"shipping_template must be {EXPECTED_SHIPPING}")
    package_values = (
        payload.package.length_cm,
        payload.package.width_cm,
        payload.package.height_cm,
        payload.package.weight_g,
    )
    if any(value <= 0 for value in package_values):
        raise ValueError("all package dimensions and weight must be greater than zero")
    api["build_form_plan"](payload)
    if not exact(str(payload.specification.get("规格型号", "")), normalized):
        raise ValueError("specification model does not match requested model")

    raw_image_items = raw_images.get("images")
    if not isinstance(raw_image_items, list) or len(raw_image_items) < 4:
        raise ValueError("four current-model images are required")
    images = [api["ProductImage"].model_validate(item) for item in raw_image_items[:4]]
    local_images: list[Path] = []
    image_sizes: list[int] = []
    dimensions: list[tuple[int, int]] = []
    for index, image in enumerate(images):
        path = _contained_path(source, image.local_file, label=f"main image {index + 1}")
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"main image does not exist or is empty: {path}")
        size = path.stat().st_size
        width, height = image_dimensions(path)
        if width != height:
            raise ValueError(f"main image must have a 1:1 aspect ratio: {path} ({width}x{height})")
        if not reuse_main_images and size >= MAX_MAIN_IMAGE_BYTES:
            raise ValueError(
                f"main image must be strictly smaller than 5,000,000 bytes: {path} ({size})"
            )
        local_images.append(path)
        image_sizes.append(size)
        dimensions.append((width, height))

    detail = api["DetailDrawingSpec"].model_validate(raw_detail)
    pdf = _contained_path(source, detail.pdf_file, label="detail drawing PDF")
    drawing = _contained_path(source, detail.local_file, label="detail drawing output")
    if not pdf.is_file() or pdf.stat().st_size == 0:
        raise ValueError(f"detail drawing PDF does not exist or is empty: {pdf}")

    return {
        "ok": True,
        "status": "READY",
        "model": normalized,
        "checks": {
            "inventory": True,
            "fixed_business_rules": True,
            "paths_contained": True,
            "main_images": 4,
            "main_image_bytes": image_sizes,
            "main_image_dimensions": dimensions,
            "main_image_sha256": api["media_fingerprint"](tuple(local_images)),
            "reuse_main_images": reuse_main_images,
            "pdf": True,
        },
        "message": "Prepared product passed local read-only preflight.",
        "price": inventory.price,
        "stock": inventory.stock,
        "source_directory": str(source),
        "artifacts_directory": str(artifacts),
        "detail_drawing": str(drawing),
        "local_images": [str(path) for path in local_images],
    }


def check_product(root: Path, model: str, *, reuse_main_images: bool) -> dict[str, Any]:
    try:
        return _check_product(root.resolve(), model, reuse_main_images=reuse_main_images)
    except Exception as error:
        return {
            "ok": False,
            "status": "BLOCKED",
            "model": model,
            "checks": {},
            "message": f"{type(error).__name__}: {error}",
        }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--existing-main-images", type=int, default=0)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = check_product(
        args.root,
        args.model,
        reuse_main_images=args.existing_main_images == 4,
    )
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
