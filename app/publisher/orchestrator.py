from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.domain.models import PreparedProduct, ProductPayload
from app.products.geo_detail import render_geo_detail


class UploaderPort(Protocol):
    async def upload_main_images(self, paths: tuple[Path, ...]) -> list[str]: ...

    async def fill_product(self, payload: ProductPayload) -> None: ...

    async def inject_detail(self, html: str) -> None: ...

    async def quality_check(self) -> dict[str, object]: ...

    async def verify_save_boundary(self) -> None: ...


@dataclass(frozen=True)
class UploadResult:
    model: str
    errors: int
    advice: tuple[str, ...]
    ready_to_save: bool


class ProductUploader:
    def __init__(self, port: UploaderPort) -> None:
        self._port = port

    async def run(self, product: PreparedProduct) -> UploadResult:
        hosted_urls = await self._port.upload_main_images(product.local_images)
        await self._port.fill_product(product.payload)
        parameters = [(name, str(value)) for name, value in product.payload.specification.items()]
        detail = render_geo_detail(
            model=product.payload.model,
            brand=product.payload.brand,
            summary=product.payload.title,
            parameters=parameters,
            image_urls=hosted_urls,
            image_roles=[image.role for image in product.images],
        )
        await self._port.inject_detail(detail)
        quality = await self._port.quality_check()
        raw_errors = quality.get("errors", 0)
        errors = int(raw_errors) if isinstance(raw_errors, (int, str)) else 1
        raw_advice = quality.get("advice", [])
        advice = (
            tuple(str(item) for item in raw_advice) if isinstance(raw_advice, (list, tuple)) else ()
        )
        if errors == 0:
            await self._port.verify_save_boundary()
        return UploadResult(
            model=product.payload.model,
            errors=errors,
            advice=advice,
            ready_to_save=errors == 0,
        )
