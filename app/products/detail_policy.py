from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.errors import ManualReviewRequired


class DetailPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    editor_width_px: int = Field(gt=0)
    sections: tuple[str, ...]
    current_product_image_count: int = Field(gt=0)
    company_heading: str
    company_image_urls: tuple[str, ...]

    @field_validator("company_image_urls")
    @classmethod
    def validate_company_urls(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != 6 or len(set(values)) != 6:
            raise ValueError("exactly six distinct company images are required")
        if any(
            not value.startswith("https://cbu01.alicdn.com/img/ibank/") for value in values
        ):
            raise ValueError("company images must use approved 1688 hosting")
        return values


@lru_cache(maxsize=1)
def load_detail_policy() -> DetailPolicy:
    path = Path(__file__).resolve().parents[2] / "config" / "detail_templates.yaml"
    try:
        loaded: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
        geo = loaded["geo_detail"]
        image_policy = geo["image_policy"]
        company = geo["fixed_company_tail"]
        return DetailPolicy(
            editor_width_px=geo["editor_width_px"],
            sections=tuple(geo["sections"]),
            current_product_image_count=image_policy["current_product_required_count"],
            company_heading=company["heading"],
            company_image_urls=tuple(company["urls"]),
        )
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise ManualReviewRequired(f"detail policy is invalid: {path}") from error
