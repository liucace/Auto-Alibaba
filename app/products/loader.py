import json
from pathlib import Path

from app.domain.errors import ManualReviewRequired
from app.domain.models import DetailDrawingSpec, PreparedProduct, ProductImage, ProductPayload
from app.ingest.model_number import exact_model_match, model_folder_key, normalize_model
from app.products.detail_assets import prepare_detail_drawing


def find_source_directory(root: Path, model: str) -> Path:
    normalized = normalize_model(model)
    folder_key = model_folder_key(normalized)
    for lifecycle in ("processing", "inbox", "draft_saved"):
        candidate = root / "data" / lifecycle / folder_key
        if candidate.is_dir():
            return candidate
    raise ManualReviewRequired(f"source directory does not exist for {normalized}")


def load_prepared_product(
    root: Path,
    model: str,
    *,
    price: int,
    stock: int,
) -> PreparedProduct:
    normalized = normalize_model(model)
    artifacts = root / "automation" / model_folder_key(normalized)
    payload_path = artifacts / "1688_payload.json"
    images_path = artifacts / "image_analysis.json"
    detail_assets_path = artifacts / "detail_assets.json"
    if not payload_path.is_file() or not images_path.is_file():
        raise ManualReviewRequired(
            f"prepared artifacts missing for {normalized}; run prepare before upload"
        )
    if not detail_assets_path.is_file():
        raise ManualReviewRequired(
            f"detail assets missing for {normalized}; run prepare before upload"
        )
    raw_payload = json.loads(payload_path.read_text(encoding="utf-8"))
    raw_images = json.loads(images_path.read_text(encoding="utf-8"))
    raw_detail = json.loads(detail_assets_path.read_text(encoding="utf-8"))
    if not exact_model_match(str(raw_payload.get("model", "")), normalized):
        raise ManualReviewRequired("payload model does not match requested model")
    if not exact_model_match(str(raw_images.get("model", "")), normalized):
        raise ManualReviewRequired("image analysis model does not match requested model")
    if not exact_model_match(str(raw_detail.get("model", "")), normalized):
        raise ManualReviewRequired("detail assets model does not match requested model")
    source = find_source_directory(root, normalized)
    images = tuple(ProductImage.model_validate(item) for item in raw_images.get("images", []))
    if len(images) < 4:
        raise ManualReviewRequired("four current-model images are required")
    local_images = tuple((source / image.local_file).resolve() for image in images[:4])
    missing = [path for path in local_images if not path.is_file()]
    if missing:
        raise ManualReviewRequired(f"local product images missing: {missing}")
    raw_payload["price"] = price
    raw_payload["stock"] = stock
    payload = ProductPayload.model_validate(raw_payload)
    detail_drawing = DetailDrawingSpec.model_validate(raw_detail)
    local_detail_drawing = prepare_detail_drawing(source, detail_drawing)
    return PreparedProduct(
        payload=payload,
        source_directory=source.resolve(),
        artifacts_directory=artifacts.resolve(),
        images=images[:4],
        local_images=local_images,
        detail_drawing=detail_drawing,
        local_detail_drawing=local_detail_drawing,
    )
