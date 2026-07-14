import pytest
from bs4 import BeautifulSoup

from app.domain.errors import ManualReviewRequired
from app.domain.models import PackageInfo, ProductPayload
from app.products.geo_detail import render_geo_detail


@pytest.fixture
def w3g710_payload() -> ProductPayload:
    return ProductPayload(
        model="W3G710-NU31-03",
        brand="ebm-papst",
        title="ebm-papst依必安派特 W3G710-NU31-03 400V EC轴流工业风扇",
        category_id=1034320,
        industry_category_id=2293,
        attributes={
            "电压": "400",
            "风叶材质": "PP塑料",
            "叶片数": "5",
        },
        specification={
            "规格型号": "W3G710-NU31-03",
            "电压范围_v": "380-480",
            "频率_hz": "50/60",
            "电机功率_w": 3800,
            "风叶直径_m": 0.71,
            "转速_rpm": 1680,
            "风量_m3h": 25590,
            "最大静压_pa": 420,
            "电流_a": 5.8,
            "重量_kg": 39.8,
            "防护等级": "IP55",
            "绝缘等级": "F级",
        },
        price=10000,
        stock=10,
        delivery_time="48小时发货",
        shipping_template="运费",
        package=PackageInfo(length_cm=85, width_cm=84.2, height_cm=27.9, weight_g=39800),
    )


def test_geo_detail_matches_reference_faithful_contract(
    w3g710_payload: ProductPayload,
) -> None:
    html = render_geo_detail(
        payload=w3g710_payload,
        drawing_url="https://example.com/drawing.jpg",
        image_urls=[f"https://example.com/product-{index}.jpg" for index in range(4)],
        image_roles=["整机正面", "整机背面", "EC电机", "型号铭牌"],
    )
    soup = BeautifulSoup(html, "html.parser")

    assert [node["data-geo-section"] for node in soup.select("[data-geo-section]")] == [
        "dimension-drawing",
        "application-scenes",
        "product-components",
        "product-definition",
        "buyer-reasons",
        "core-parameters",
        "application-guidance",
        "selection-reminders",
        "purchase-confirmation",
        "faq-selection",
    ]
    images = soup.select("img")
    assert len(images) == 5
    assert len({image["src"] for image in images}) == 5
    assert all("W3G710-NU31-03" in image.get("alt", "") for image in images)
    assert "25,590m³/h" in html
    assert "420Pa" in html
    assert "850 × 842 × 279mm" in html
    assert "39.8kg" in html
    assert "T4E45BAM81100" not in html


@pytest.mark.parametrize(
    ("drawing_url", "image_urls"),
    [
        ("", [f"https://example.com/{index}.jpg" for index in range(4)]),
        ("https://example.com/drawing.jpg", ["https://example.com/same.jpg"] * 4),
        (
            "https://example.com/same.jpg",
            ["https://example.com/same.jpg"]
            + [f"https://example.com/{index}.jpg" for index in range(3)],
        ),
    ],
)
def test_geo_detail_rejects_missing_or_duplicate_images(
    w3g710_payload: ProductPayload,
    drawing_url: str,
    image_urls: list[str],
) -> None:
    with pytest.raises(ManualReviewRequired):
        render_geo_detail(
            payload=w3g710_payload,
            drawing_url=drawing_url,
            image_urls=image_urls,
            image_roles=["a", "b", "c", "d"],
        )


def test_geo_detail_rejects_missing_required_parameter(
    w3g710_payload: ProductPayload,
) -> None:
    incomplete = w3g710_payload.model_copy(update={"specification": {"规格型号": "W3G710-NU31-03"}})

    with pytest.raises(ManualReviewRequired, match="required specification"):
        render_geo_detail(
            payload=incomplete,
            drawing_url="https://example.com/drawing.jpg",
            image_urls=[f"https://example.com/{index}.jpg" for index in range(4)],
            image_roles=["a", "b", "c", "d"],
        )


def test_geo_detail_rejects_payload_model_mismatch(
    w3g710_payload: ProductPayload,
) -> None:
    mismatched = w3g710_payload.model_copy(
        update={"specification": {**w3g710_payload.specification, "规格型号": "OTHER"}}
    )

    with pytest.raises(ManualReviewRequired, match="model"):
        render_geo_detail(
            payload=mismatched,
            drawing_url="https://example.com/drawing.jpg",
            image_urls=[f"https://example.com/{index}.jpg" for index in range(4)],
            image_roles=["a", "b", "c", "d"],
        )
