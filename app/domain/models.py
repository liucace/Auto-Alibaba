from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


class EvidenceValue[T](BaseModel):
    model_config = ConfigDict(frozen=True)

    value: T | None
    source_page: int | None = None
    source_text: str | None = None
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def require_evidence_for_present_value(self) -> "EvidenceValue[T]":
        if self.value is not None and (self.source_page is None or not self.source_text):
            raise ValueError("present values require source page and source text")
        return self


class InventoryRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: str
    price: int
    stock: int


class PackageInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    length_cm: float
    width_cm: float
    height_cm: float
    weight_g: int


class OperatingPoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    frequency_hz: int = Field(gt=0)
    speed_rpm: float | None = Field(default=None, gt=0)
    airflow_cfm: float | None = Field(default=None, ge=0)
    airflow_m3h: float | None = Field(default=None, ge=0)
    static_pressure_in_h2o: float | None = Field(default=None, ge=0)
    current_a: float | None = Field(default=None, ge=0)
    power_w: float | None = Field(default=None, ge=0)
    noise_db_a: float | None = Field(default=None, ge=0)


class ProductPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: str
    brand: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    title: str
    category_id: int
    industry_category_id: int
    attributes: dict[str, str]
    specification: dict[str, str | int | float]
    operating_points: tuple[OperatingPoint, ...] = ()
    price: int
    stock: int
    delivery_time: str
    shipping_template: str
    package: PackageInfo


class ProductImage(BaseModel):
    model_config = ConfigDict(frozen=True)

    local_file: str
    role: str
    hosted_url: str | None = None


class DetailDrawingSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: str
    pdf_file: str
    page: int = Field(ge=1)
    crop: tuple[float, float, float, float]
    local_file: str = "upload_optimized/detail-drawing.jpg"
    hosted_url: str | None = None

    @model_validator(mode="after")
    def validate_crop(self) -> "DetailDrawingSpec":
        x0, y0, x1, y1 = self.crop
        if any(value < 0 or value > 1 for value in self.crop):
            raise ValueError("detail drawing crop values must be between 0 and 1")
        if x0 >= x1 or y0 >= y1:
            raise ValueError("detail drawing crop coordinates must be ordered")
        return self


class PreparedProduct(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    payload: ProductPayload
    source_directory: Path
    artifacts_directory: Path
    images: tuple[ProductImage, ...]
    local_images: tuple[Path, ...]
    detail_drawing: DetailDrawingSpec
    local_detail_drawing: Path
