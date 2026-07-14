import pytest
from pydantic import ValidationError

from app.domain.models import EvidenceValue, OperatingPoint, ProductPayload


def test_present_value_requires_source_evidence() -> None:
    with pytest.raises(ValidationError):
        EvidenceValue[str](value="1800 g", source_page=None, source_text=None, confidence=0.9)


def test_missing_value_may_have_no_source() -> None:
    item = EvidenceValue[str](value=None, source_page=None, source_text=None, confidence=0)
    assert item.value is None


def test_operating_point_rejects_non_positive_frequency() -> None:
    with pytest.raises(ValidationError, match="frequency_hz"):
        OperatingPoint(frequency_hz=0)


def test_product_payload_allows_empty_operating_points_for_sparse_legacy_products() -> None:
    payload = ProductPayload(
        model="A2E250-AL06-01",
        brand="ebm-papst",
        title="ebm-papst A2E250-AL06-01 230V 交流离心风机",
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

    assert payload.operating_points == ()


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


@pytest.mark.parametrize("brand", ["", "   "])
def test_product_payload_rejects_blank_brand(brand: str) -> None:
    with pytest.raises(ValidationError, match="brand"):
        ProductPayload(
            model="DP201AT-2122HBL.GN",
            brand=brand,
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
