import json
from pathlib import Path

import fitz
import pytest
from openpyxl import Workbook
from PIL import Image

from app.domain.errors import ManualReviewRequired
from app.products.preparer import _pdf_contains_exact_model, prepare_product


def _write_pdf(path: Path, model: str) -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), f"Exact model {model} product drawing")
    document.save(path)


def _write_pdf_pages(path: Path, pages: tuple[str, ...]) -> None:
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        page.insert_text((72, 72), text)
    document.save(path)


def _write_inventory(path: Path, model: str) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["型号", "价格", "库存"])
    sheet.append([model, 10000, 10])
    workbook.save(path)


def test_prepare_product_builds_validated_artifacts_and_square_images(tmp_path: Path) -> None:
    model = "W3G800-KS39-03/F01"
    folder_key = "W3G800-KS39-03F01"
    source = tmp_path / "data" / "draft_saved" / folder_key
    artifacts = tmp_path / "automation" / folder_key
    source.mkdir(parents=True)
    artifacts.mkdir(parents=True)
    pdf_name = "fan.pdf"
    _write_pdf(source / pdf_name, model)
    _write_inventory(tmp_path / "price_inventory.xlsx", model)
    images = []
    for index in range(4):
        name = f"photo-{index}.png"
        Image.new("RGB", (1200, 800 + index), (index, 20, 30)).save(source / name)
        images.append({"local_file": name, "role": f"current-model-view-{index}"})
    evidence = {
        "model": model,
        "brand": "ebm-papst",
        "pdf_file": pdf_name,
        "title": f"ebm-papst {model} 400V EC轴流工业风扇",
        "attributes": {
            "电压": "400",
            "产品别名": "EC轴流风机",
            "风叶材质": "PP塑料",
            "品牌": "ebm-papst",
            "噪声": "88",
            "类型": "轴流风扇",
            "叶片数": "5",
            "工业风扇种类": "轴流风扇",
        },
        "specification": {
            "规格型号": model,
            "电压范围_v": "380-480",
            "频率_hz": "50/60",
            "电机功率_w": 1950,
            "风叶直径_m": 0.8,
            "转速_rpm": 940,
            "风量_m3h": 25740,
            "最大静压_pa": 220,
            "电流_a": 3.1,
            "重量_kg": 39.85,
            "防护等级": "IP55",
            "绝缘等级": "F级",
        },
        "package": {"length_cm": 97, "width_cm": 97, "height_cm": 33.4, "weight_g": 39850},
        "images": images,
        "drawing": {"page": 1, "crop": [0.0, 0.0, 1.0, 1.0]},
    }
    (artifacts / "preparation_evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False), encoding="utf-8"
    )

    result = prepare_product(tmp_path, model)

    assert result.model == model
    assert result.price == 10000
    assert result.stock == 10
    payload = json.loads((artifacts / "1688_payload.json").read_text(encoding="utf-8"))
    analysis = json.loads((artifacts / "image_analysis.json").read_text(encoding="utf-8"))
    detail = json.loads((artifacts / "detail_assets.json").read_text(encoding="utf-8"))
    assert payload["model"] == model
    assert payload["brand"] == "ebm-papst"
    assert detail["model"] == model
    assert len(analysis["images"]) == 4
    for item in analysis["images"]:
        prepared = source / item["local_file"]
        with Image.open(prepared) as image:
            assert image.width == image.height
        assert prepared.stat().st_size < 5_000_000


def test_prepare_product_reports_invalid_evidence_as_manual_review(tmp_path: Path) -> None:
    model = "W3G800-KS39-03/F01"
    folder_key = "W3G800-KS39-03F01"
    (tmp_path / "data" / "draft_saved" / folder_key).mkdir(parents=True)
    artifacts = tmp_path / "automation" / folder_key
    artifacts.mkdir(parents=True)
    (artifacts / "preparation_evidence.json").write_text("{invalid", encoding="utf-8")

    with pytest.raises(ManualReviewRequired, match="preparation evidence is invalid"):
        prepare_product(tmp_path, model)


def test_pdf_exact_model_check_rejects_longer_variant(tmp_path: Path) -> None:
    pdf = tmp_path / "fan.pdf"
    _write_pdf(pdf, "W3G800-KS39-03/F010")

    assert not _pdf_contains_exact_model(pdf, "W3G800-KS39-03/F01")


def test_pdf_exact_model_check_accepts_labeled_model_and_part_number_on_same_page(
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "fan.pdf"
    _write_pdf_pages(pdf, ("MODEL: DP201AT   P / N: 2122HBL.GN",))

    assert _pdf_contains_exact_model(pdf, "DP201AT-2122HBL.GN")


def test_pdf_exact_model_check_rejects_unlabeled_model_parts(tmp_path: Path) -> None:
    pdf = tmp_path / "fan.pdf"
    _write_pdf_pages(pdf, ("DP201AT 2122HBL.GN",))

    assert not _pdf_contains_exact_model(pdf, "DP201AT-2122HBL.GN")


def test_pdf_exact_model_check_rejects_labeled_parts_on_different_pages(tmp_path: Path) -> None:
    pdf = tmp_path / "fan.pdf"
    _write_pdf_pages(pdf, ("MODEL: DP201AT", "P / N: 2122HBL.GN"))

    assert not _pdf_contains_exact_model(pdf, "DP201AT-2122HBL.GN")


def test_pdf_exact_model_check_rejects_longer_labeled_part_number(tmp_path: Path) -> None:
    pdf = tmp_path / "fan.pdf"
    _write_pdf_pages(pdf, ("MODEL: DP201AT   P / N: 2122HBL.GN0",))

    assert not _pdf_contains_exact_model(pdf, "DP201AT-2122HBL.GN")
