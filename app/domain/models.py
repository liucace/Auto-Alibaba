from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class ProductPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: str
    brand: str = "ebm-papst"
    title: str
    category_id: int
    industry_category_id: int
    attributes: dict[str, str]
    specification: dict[str, str | int | float]
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


class PreparedProduct(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    payload: ProductPayload
    source_directory: Path
    artifacts_directory: Path
    images: tuple[ProductImage, ...]
    local_images: tuple[Path, ...]
