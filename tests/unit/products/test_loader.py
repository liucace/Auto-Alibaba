import json
from pathlib import Path

from app.products.loader import load_prepared_product


def test_load_prepared_product_overrides_price_and_stock_from_excel(tmp_path: Path) -> None:
    root = tmp_path
    artifacts = root / "automation" / "W3G630-NU33-03"
    source = root / "data" / "draft_saved" / "W3G630-NU33-03"
    artifacts.mkdir(parents=True)
    source.mkdir(parents=True)
    (source / "fan.pdf").write_bytes(b"pdf")
    for index in range(4):
        (source / f"photo-{index}.jpg").write_bytes(b"jpg")
    (artifacts / "1688_payload.json").write_text(
        json.dumps(
            {
                "model": "W3G630-NU33-03",
                "title": "title",
                "category_id": 1034320,
                "industry_category_id": 2293,
                "attributes": {"电压": "400"},
                "specification": {"规格型号": "W3G630-NU33-03"},
                "price": 1,
                "stock": 1,
                "delivery_time": "48小时发货",
                "shipping_template": "运费",
                "package": {"length_cm": 80.5, "width_cm": 79.7, "height_cm": 27, "weight_g": 39300},
            }
        ),
        encoding="utf-8",
    )
    (artifacts / "image_analysis.json").write_text(
        json.dumps(
            {
                "model": "W3G630-NU33-03",
                "images": [
                    {"local_file": f"photo-{index}.jpg", "role": f"role-{index}", "hosted_url": None}
                    for index in range(4)
                ],
            }
        ),
        encoding="utf-8",
    )

    product = load_prepared_product(root, "W3G630-NU33-03", price=10000, stock=10)

    assert product.payload.price == 10000
    assert product.payload.stock == 10
    assert len(product.local_images) == 4
    assert all(path.is_absolute() for path in product.local_images)


def test_source_prefers_processing_then_draft_saved(tmp_path: Path) -> None:
    from app.products.loader import find_source_directory

    draft = tmp_path / "data" / "draft_saved" / "X"
    processing = tmp_path / "data" / "processing" / "X"
    draft.mkdir(parents=True)
    processing.mkdir(parents=True)

    assert find_source_directory(tmp_path, "X") == processing
