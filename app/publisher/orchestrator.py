from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.domain.models import PreparedProduct, ProductPayload
from app.products.detail_assets import update_detail_hosted_url
from app.products.geo_detail import render_geo_detail


class UploaderPort(Protocol):
    async def upload_main_images(self, paths: tuple[Path, ...]) -> list[str]: ...

    async def upload_detail_image(self, path: Path, *, existing_url: str | None = None) -> str: ...

    async def fill_product(self, payload: ProductPayload) -> None: ...

    async def inject_detail(self, html: str, *, expected_image_count: int) -> None: ...

    async def quality_check(self) -> dict[str, object]: ...

    async def verify_save_boundary(self) -> None: ...


@dataclass(frozen=True)
class UploadResult:
    model: str
    errors: int
    advice: tuple[str, ...]
    ready_to_save: bool
    detail_drawing_url: str
    detail_html_path: Path
    detail_image_count: int
    error_details: tuple[dict[str, str], ...] = ()


class ProductUploader:
    def __init__(self, port: UploaderPort) -> None:
        self._port = port

    async def run(self, product: PreparedProduct) -> UploadResult:
        hosted_urls = await self._port.upload_main_images(product.local_images)
        drawing_url = await self._port.upload_detail_image(
            product.local_detail_drawing,
            existing_url=product.detail_drawing.hosted_url,
        )
        update_detail_hosted_url(product.artifacts_directory / "detail_assets.json", drawing_url)
        await self._port.fill_product(product.payload)
        detail = render_geo_detail(
            payload=product.payload,
            drawing_url=drawing_url,
            image_urls=hosted_urls,
            image_roles=[image.role for image in product.images],
        )
        detail_path = product.artifacts_directory / "detail.html"
        temporary = detail_path.with_suffix(detail_path.suffix + ".tmp")
        temporary.write_text(detail, encoding="utf-8")
        temporary.replace(detail_path)
        await self._port.inject_detail(detail, expected_image_count=5)
        quality = await self._port.quality_check()
        raw_errors = quality.get("errors", 0)
        errors = int(raw_errors) if isinstance(raw_errors, (int, str)) else 1
        raw_advice = quality.get("advice", [])
        advice = (
            tuple(str(item) for item in raw_advice) if isinstance(raw_advice, (list, tuple)) else ()
        )
        raw_error_details = quality.get("error_details", [])
        error_details = (
            tuple(dict(item) for item in raw_error_details if isinstance(item, dict))
            if isinstance(raw_error_details, (list, tuple))
            else ()
        )
        if errors == 0:
            await self._port.verify_save_boundary()
        return UploadResult(
            model=product.payload.model,
            errors=errors,
            advice=advice,
            ready_to_save=errors == 0,
            detail_drawing_url=drawing_url,
            detail_html_path=detail_path,
            detail_image_count=5,
            error_details=error_details,
        )
