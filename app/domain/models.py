from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


T = TypeVar("T")


class EvidenceValue(BaseModel, Generic[T]):
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
