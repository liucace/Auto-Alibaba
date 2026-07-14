import pytest
from pydantic import ValidationError

from app.domain.models import EvidenceValue, ProductPayload


def test_present_value_requires_source_evidence() -> None:
    with pytest.raises(ValidationError):
        EvidenceValue[str](value="1800 g", source_page=None, source_text=None, confidence=0.9)


def test_missing_value_may_have_no_source() -> None:
    item = EvidenceValue[str](value=None, source_page=None, source_text=None, confidence=0)
    assert item.value is None


def test_product_payload_requires_brand() -> None:
    with pytest.raises(ValidationError):
        ProductPayload(
            model="DP201AT-2122HBL.GN",
            title="Industrial fan",
            category_id=1034320,
            industry_category_id=2293,
            attributes={},
            specification={},
            price=10000,
            stock=10,
            delivery_time="48 hours",
            shipping_template="Freight",
            package={"length_cm": 1, "width_cm": 1, "height_cm": 1, "weight_g": 1},
        )
