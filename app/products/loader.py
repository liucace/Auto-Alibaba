import json
from pathlib import Path

from app.domain.errors import ManualReviewRequired
from app.domain.models import PreparedProduct, ProductImage, ProductPayload
from app.ingest.model_number import exact_model_match, normalize_model


def find_source_directory(root: Path, model: str) -> Path:
    normalized = normalize_model(model)
    for lifecycle in ("processing", "inbox", "draft_saved"):
        candidate = root / "data" / lifecycle / normalized
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
    artifacts = root / "automation" / normalized
    payload_path = artifacts / "1688_payload.json"
    images_path = artifacts / "image_analysis.json"
    if not payload_path.is_file() or not images_path.is_file():
        raise ManualReviewRequired(
            f"prepared artifacts missing for {normalized}; run prepare before upload"
        )
    raw_payload = json.loads(payload_path.read_text(encoding="utf-8"))
    raw_images = json.loads(images_path.read_text(encoding="utf-8"))
    if not exact_model_match(str(raw_payload.get("model", "")), normalized):
        raise ManualReviewRequired("payload model does not match requested model")
    if not exact_model_match(str(raw_images.get("model", "")), normalized):
        raise ManualReviewRequired("image analysis model does not match requested model")
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
    return PreparedProduct(
        payload=payload,
        source_directory=source.resolve(),
        artifacts_directory=artifacts.resolve(),
        images=images[:4],
        local_images=local_images,
    )
