import json
from pathlib import Path

import pytest

from app.domain.models import (
    DetailDrawingSpec,
    PackageInfo,
    PreparedProduct,
    ProductImage,
    ProductPayload,
)
from app.publisher.orchestrator import ProductUploader


class RecordingPort:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    async def upload_main_images(self, paths: tuple[Path, ...]) -> list[str]:
        self.calls.append(("upload-main", paths))
        return [f"https://example.com/{index}.jpg" for index in range(4)]

    async def upload_detail_image(self, path: Path, *, existing_url: str | None = None) -> str:
        self.calls.append(("upload-detail", (path, existing_url)))
        return "https://cbu01.alicdn.com/img/ibank/drawing.jpg"

    async def fill_product(self, payload: ProductPayload) -> None:
        self.calls.append(("fill", payload.model))

    async def inject_detail(self, html: str, *, expected_image_count: int) -> None:
        self.calls.append(("detail", (html, expected_image_count)))

    async def quality_check(self) -> dict[str, object]:
        self.calls.append(("quality", None))
        return {"errors": 0, "advice": ["视频"]}

    async def verify_save_boundary(self) -> None:
        self.calls.append(("boundary", None))


@pytest.fixture
def product(tmp_path: Path) -> PreparedProduct:
    paths = tuple(tmp_path / f"{index}.jpg" for index in range(4))
    for path in paths:
        path.write_bytes(b"jpg")
    images = tuple(
        ProductImage(local_file=path.name, role=f"role-{index}") for index, path in enumerate(paths)
    )
    drawing = tmp_path / "detail-drawing.jpg"
    drawing.write_bytes(b"drawing")
    (tmp_path / "detail_assets.json").write_text(
        json.dumps(
            {
                "model": "W3G630-NU33-03",
                "pdf_file": "fan.pdf",
                "page": 3,
                "crop": [0.05, 0.1, 0.95, 0.8],
                "local_file": "detail-drawing.jpg",
                "hosted_url": None,
            }
        ),
        encoding="utf-8",
    )
    return PreparedProduct(
        payload=ProductPayload(
            model="W3G630-NU33-03",
            brand="ebm-papst",
            title="title",
            category_id=1034320,
            industry_category_id=2293,
            attributes={"电压": "400"},
            specification={
                "规格型号": "W3G630-NU33-03",
                "电压范围_v": "380-480",
                "频率_hz": "50/60",
                "电机功率_w": 3600,
                "风叶直径_m": 0.63,
                "转速_rpm": 1800,
                "风量_m3h": 22150,
                "最大静压_pa": 440,
                "电流_a": 5.5,
                "重量_kg": 39.3,
                "防护等级": "IP55",
                "绝缘等级": "F级",
            },
            price=10000,
            stock=10,
            delivery_time="48小时发货",
            shipping_template="运费",
            package=PackageInfo(length_cm=80.5, width_cm=79.7, height_cm=27, weight_g=39300),
        ),
        source_directory=tmp_path,
        artifacts_directory=tmp_path,
        images=images,
        local_images=paths,
        detail_drawing=DetailDrawingSpec(
            model="W3G630-NU33-03",
            pdf_file="fan.pdf",
            page=3,
            crop=(0.05, 0.1, 0.95, 0.8),
            local_file="detail-drawing.jpg",
        ),
        local_detail_drawing=drawing,
    )


@pytest.mark.asyncio
async def test_uploader_runs_fixed_order_and_checks_quality_once(product: PreparedProduct) -> None:
    port = RecordingPort()

    result = await ProductUploader(port).run(product)

    assert [name for name, _ in port.calls] == [
        "upload-main",
        "upload-detail",
        "fill",
        "detail",
        "quality",
        "boundary",
    ]
    assert result.errors == 0
    assert result.ready_to_save is True
    detail_call = next(value for name, value in port.calls if name == "detail")
    assert isinstance(detail_call, tuple)
    detail, expected_count = detail_call
    assert isinstance(detail, str)
    assert expected_count == 5
    assert detail.count("<img ") == 5
    assert (product.artifacts_directory / "detail.html").read_text(encoding="utf-8") == detail
    detail_assets = json.loads(
        (product.artifacts_directory / "detail_assets.json").read_text(encoding="utf-8")
    )
    assert detail_assets["hosted_url"] == "https://cbu01.alicdn.com/img/ibank/drawing.jpg"
    assert result.detail_image_count == 5
    assert result.detail_html_path == product.artifacts_directory / "detail.html"


@pytest.mark.asyncio
async def test_uploader_stops_when_quality_has_errors(product: PreparedProduct) -> None:
    port = RecordingPort()

    async def failing_quality() -> dict[str, object]:
        port.calls.append(("quality", None))
        return {"errors": 2, "advice": []}

    port.quality_check = failing_quality  # type: ignore[method-assign]

    result = await ProductUploader(port).run(product)

    assert result.ready_to_save is False
    assert not any(name == "boundary" for name, _ in port.calls)
