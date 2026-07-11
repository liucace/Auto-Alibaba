from pathlib import Path

import pytest

from app.domain.models import (
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
        self.calls.append(("upload", paths))
        return [f"https://example.com/{index}.jpg" for index in range(4)]

    async def fill_product(self, payload: ProductPayload) -> None:
        self.calls.append(("fill", payload.model))

    async def inject_detail(self, html: str) -> None:
        self.calls.append(("detail", html))

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
    return PreparedProduct(
        payload=ProductPayload(
            model="W3G630-NU33-03",
            title="title",
            category_id=1034320,
            industry_category_id=2293,
            attributes={"电压": "400"},
            specification={"规格型号": "W3G630-NU33-03", "电机功率_w": 3600},
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
    )


@pytest.mark.asyncio
async def test_uploader_runs_fixed_order_and_checks_quality_once(product: PreparedProduct) -> None:
    port = RecordingPort()

    result = await ProductUploader(port).run(product)

    assert [name for name, _ in port.calls] == ["upload", "fill", "detail", "quality", "boundary"]
    assert result.errors == 0
    assert result.ready_to_save is True
    detail = next(value for name, value in port.calls if name == "detail")
    assert isinstance(detail, str)
    assert detail.count("<img ") == 4


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
