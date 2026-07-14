import pytest
from bs4 import BeautifulSoup

from app.domain.errors import ManualReviewRequired
from app.domain.models import PackageInfo, ProductPayload
from app.products.geo_detail import render_geo_detail


@pytest.fixture
def sunon_sparse_payload() -> ProductPayload:
    return ProductPayload(
        model="A2175-HBL",
        brand="SUNON",
        title="SUNON A2175-HBL",
        category_id=1034320,
        industry_category_id=2293,
        attributes={
            "品牌": "SUNON",
            "叶片数": "18",
            "空值": "  ",
        },
        specification={
            "规格型号": "A2175-HBL",
            "电压范围_v": "220-240",
            "电机功率_w": 16.5,
        },
        price=100,
        stock=10,
        delivery_time="48小时发货",
        shipping_template="运费",
        package=PackageInfo(length_cm=20, width_cm=20, height_cm=8, weight_g=1000),
    )


def _render(payload: ProductPayload, *, image_roles: list[str] | None = None) -> str:
    return render_geo_detail(
        payload=payload,
        drawing_url="https://example.com/drawing.jpg",
        image_urls=[f"https://example.com/product-{index}.jpg" for index in range(4)],
        image_roles=image_roles or ["正面", "背面", "电机", "铭牌"],
    )


def test_geo_detail_renders_sparse_evidence_without_product_specific_claims(
    sunon_sparse_payload: ProductPayload,
) -> None:
    html = _render(sunon_sparse_payload)
    soup = BeautifulSoup(html, "html.parser")

    assert [node["data-geo-section"] for node in soup.select("[data-geo-section]")] == [
        "dimension-drawing",
        "product-images",
        "product-definition",
        "core-parameters",
    ]
    images = soup.select("img")
    assert len(images) == 5
    assert len({image["src"] for image in images}) == 5
    assert [image.get("alt") for image in images] == [
        "SUNON A2175-HBL 尺寸图",
        "SUNON A2175-HBL 正面",
        "SUNON A2175-HBL 背面",
        "SUNON A2175-HBL 电机",
        "SUNON A2175-HBL 铭牌",
    ]
    assert "SUNON" in html
    assert "A2175-HBL" in html
    assert "220-240V" in html
    assert ">18<" in html
    assert "16.5W" in html
    for unsupported_claim in ("ebm-papst", "400V", "AxiBlade", "MODBUS", "5片PP"):
        assert unsupported_claim not in html

    rows = soup.select('[data-geo-section="core-parameters"] tr')
    assert [row.select_one("td").get_text(strip=True) for row in rows] == [
        "品牌",
        "完整型号",
        "叶片数",
        "电压范围",
        "电机功率",
    ]


def test_geo_detail_renders_explicit_ebm_evidence_through_the_same_generic_path(
    sunon_sparse_payload: ProductPayload,
) -> None:
    payload = sunon_sparse_payload.model_copy(
        update={
            "brand": "ebm-papst",
            "model": "W3G710-NU31-03",
            "attributes": {
                "产品系列": "AxiBlade",
                "通信方式": "MODBUS",
                "叶片说明": "5片PP",
            },
            "specification": {
                "规格型号": "W3G710-NU31-03",
                "额定电压_v": 400,
                "最大静压_inH2O": 1.25,
                "尺寸_mm": 710,
            },
        }
    )

    html = _render(payload)
    soup = BeautifulSoup(html, "html.parser")

    assert [node["data-geo-section"] for node in soup.select("[data-geo-section]")] == [
        "dimension-drawing",
        "product-images",
        "product-definition",
        "core-parameters",
    ]
    for evidenced_text in ("ebm-papst", "W3G710-NU31-03", "400V", "AxiBlade", "MODBUS", "5片PP"):
        assert evidenced_text in html
    assert "1.25inH₂O" in html
    assert "1.25inH2O" not in html
    assert "尺寸 (mm)" in html


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("电压范围_v", "220 VAC", "220 VAC"),
        ("最大静压_inH2O", "1.2inH2O", "1.2inH2O"),
        ("最大静压_inH2O", "1.2inH₂O", "1.2inH₂O"),
    ],
)
def test_geo_detail_preserves_existing_unit_aliases(
    sunon_sparse_payload: ProductPayload,
    key: str,
    value: str,
    expected: str,
) -> None:
    payload = sunon_sparse_payload.model_copy(
        update={"specification": {"规格型号": "A2175-HBL", key: value}}
    )

    html = _render(payload)

    assert expected in html
    assert "VACV" not in html
    assert "inH2OinH₂O" not in html
    assert "inH₂OinH₂O" not in html


def test_geo_detail_deduplicates_rows_without_merging_different_meanings(
    sunon_sparse_payload: ProductPayload,
) -> None:
    payload = sunon_sparse_payload.model_copy(
        update={
            "attributes": {
                " MODEL ": "OTHER-MODEL",
                " 型号 ": "OTHER-MODEL-2",
                "产品编号": "A2175-HBL",
                " BRAND ": "OTHER-BRAND",
                " 品牌 ": "OTHER-BRAND-2",
                "制造商": " SUNON ",
                "额定电压": "220 VAC",
                " 额定电压 ": "220 VAC",
                "颜色": "黑色",
                " 颜色 ": "白色",
                "材料": "PP",
                "叶片材料": "PP",
            },
            "specification": {
                "规格型号": "A2175-HBL",
                "额定电压_v": "220 VAC",
            },
        }
    )

    soup = BeautifulSoup(_render(payload), "html.parser")
    rows = [
        tuple(cell.get_text(strip=True) for cell in row.select("td"))
        for row in soup.select('[data-geo-section="core-parameters"] tr')
    ]

    assert rows == [
        ("品牌", "SUNON"),
        ("完整型号", "A2175-HBL"),
        ("额定电压", "220 VAC"),
        ("颜色", "黑色"),
        ("颜色", "白色"),
        ("材料", "PP"),
        ("叶片材料", "PP"),
    ]


def test_geo_detail_escapes_html_and_event_attributes(
    sunon_sparse_payload: ProductPayload,
) -> None:
    model = 'A2175-HBL"><img src=x onerror=alert(1)>'
    payload = sunon_sparse_payload.model_copy(
        update={
            "model": model,
            "brand": "SUNON<script>alert(1)</script>",
            "attributes": {'参数"><script>alert(2)</script>': "<img src=x onerror=alert(3)>"},
            "specification": {"规格型号": model},
        }
    )

    html = _render(payload, image_roles=['正面" onerror="alert(4)', "背面", "电机", "铭牌"])
    soup = BeautifulSoup(html, "html.parser")

    assert not soup.select("script")
    assert not soup.select("[onerror]")
    assert "&lt;script&gt;" in html
    assert "&lt;img src=x onerror=alert(3)&gt;" in html


def test_geo_detail_renders_only_brand_and_model_when_only_model_is_specified(
    sunon_sparse_payload: ProductPayload,
) -> None:
    payload = sunon_sparse_payload.model_copy(
        update={"attributes": {}, "specification": {"规格型号": "A2175-HBL"}}
    )

    soup = BeautifulSoup(_render(payload), "html.parser")
    rows = soup.select('[data-geo-section="core-parameters"] tr')

    assert len(rows) == 2
    assert all(
        len(row.select("td")) == 2 and all(cell.get_text(strip=True) for cell in row.select("td"))
        for row in rows
    )


@pytest.mark.parametrize(
    ("drawing_url", "image_urls", "image_roles"),
    [
        ("", [f"https://example.com/{index}.jpg" for index in range(4)], ["a", "b", "c", "d"]),
        (
            "https://example.com/drawing.jpg",
            ["https://example.com/same.jpg"] * 4,
            ["a", "b", "c", "d"],
        ),
        (
            "https://example.com/same.jpg",
            ["https://example.com/same.jpg"]
            + [f"https://example.com/{index}.jpg" for index in range(3)],
            ["a", "b", "c", "d"],
        ),
        (
            "https://example.com/drawing.jpg",
            [f"https://example.com/{index}.jpg" for index in range(4)],
            ["a", "b", "c"],
        ),
        (
            "https://example.com/drawing.jpg",
            [f"https://example.com/{index}.jpg" for index in range(4)],
            ["a", " ", "c", "d"],
        ),
    ],
)
def test_geo_detail_rejects_missing_or_duplicate_images_and_roles(
    sunon_sparse_payload: ProductPayload,
    drawing_url: str,
    image_urls: list[str],
    image_roles: list[str],
) -> None:
    with pytest.raises(ManualReviewRequired):
        render_geo_detail(
            payload=sunon_sparse_payload,
            drawing_url=drawing_url,
            image_urls=image_urls,
            image_roles=image_roles,
        )


def test_geo_detail_rejects_payload_model_mismatch(
    sunon_sparse_payload: ProductPayload,
) -> None:
    mismatched = sunon_sparse_payload.model_copy(
        update={"specification": {"规格型号": "OTHER"}}
    )

    with pytest.raises(ManualReviewRequired, match="model"):
        _render(mismatched)
