import pytest
from bs4 import BeautifulSoup

from app.domain.errors import ManualReviewRequired
from app.domain.models import OperatingPoint, PackageInfo, ProductPayload
from app.products.detail_policy import load_detail_policy
from app.products.geo_detail import render_geo_detail


@pytest.fixture
def dp201at_payload() -> ProductPayload:
    return ProductPayload(
        model="DP201AT-2122HBL.GN",
        brand="SUNON",
        title="SUNON建准 DP201AT-2122HBL.GN 220-240V 120mm滚珠轴承交流轴流风扇",
        category_id=1034320,
        industry_category_id=2293,
        attributes={
            "品牌": "SUNON建准",
            "产品别名": "交流轴流风扇",
            "类型": "轴流风扇",
        },
        specification={
            "规格型号": "DP201AT-2122HBL.GN",
            "额定电压_v": "220-240VAC",
            "频率_hz": "50/60",
            "电机功率_w": "18/16.5",
            "风叶直径_m": "0.119",
            "转速_rpm": "2150/2500",
            "风量_m3h": "112.1/135.9",
            "电流_a": "0.09/0.09",
            "重量_kg": "0.295",
            "尺寸_mm": "120×120×25mm",
            "外框宽度_mm": "119±0.5mm",
            "厚度_mm": "25.5±0.5mm",
            "安装孔距_mm": "104.8±0.3mm",
            "安装孔": "8-Ø4.3mm",
            "引线长度_mm": "320±10mm",
            "框体材质": "压铸铝",
            "叶轮材质": "PBT UL94V-0",
            "引线规格": "UL3266 24AWG 灰色",
            "电压范围_v": "185-245VAC",
            "启动电压_v": "185VAC（25°C）",
            "轴承系统": "精密滚珠轴承",
            "工作温度_c": "-10~+70°C",
            "存储温度_c": "-40~+70°C",
            "气流方向": "朝铭牌侧",
            "旋转方向": "从叶轮正面观察逆时针",
            "安装方向": "任意方向",
            "认证": "UL/CUR/TUV/CE/UKCA",
        },
        operating_points=(
            OperatingPoint(
                frequency_hz=50,
                speed_rpm=2150,
                airflow_cfm=66,
                airflow_m3h=112.1,
                static_pressure_in_h2o=0.14,
                current_a=0.09,
                power_w=18,
                noise_db_a=44,
            ),
            OperatingPoint(
                frequency_hz=60,
                speed_rpm=2500,
                airflow_cfm=80,
                airflow_m3h=135.9,
                static_pressure_in_h2o=0.17,
                current_a=0.09,
                power_w=16.5,
                noise_db_a=48,
            ),
        ),
        price=188,
        stock=10,
        delivery_time="48小时发货",
        shipping_template="运费",
        package=PackageInfo(length_cm=12, width_cm=12, height_cm=2.5, weight_g=295),
    )


@pytest.fixture
def sparse_payload() -> ProductPayload:
    return ProductPayload(
        model="A2175-HBL",
        brand="SUNON",
        title="SUNON A2175-HBL 220V 轴流风扇",
        category_id=1034320,
        industry_category_id=2293,
        attributes={},
        specification={"规格型号": "A2175-HBL"},
        price=100,
        stock=10,
        delivery_time="48小时发货",
        shipping_template="运费",
        package=PackageInfo(length_cm=20, width_cm=20, height_cm=8, weight_g=1000),
    )


def _render(payload: ProductPayload, *, image_roles: list[str] | None = None):
    return render_geo_detail(
        payload=payload,
        drawing_url="https://example.com/drawing.jpg",
        image_urls=[f"https://example.com/product-{index}.jpg" for index in range(4)],
        image_roles=image_roles or ["铭牌侧整机", "铭牌侧视图", "叶轮侧视图", "侧面与引线"],
    )


def test_geo_detail_renders_approved_rich_document(dp201at_payload: ProductPayload) -> None:
    document = _render(dp201at_payload)
    soup = BeautifulSoup(document.html, "html.parser")

    assert [node["data-geo-section"] for node in soup.select("[data-geo-section]")] == [
        "entity-answer",
        "quick-facts",
        "core-parameters",
        "operating-points",
        "product-images",
        "dimensions-installation",
        "materials-electrical-environment",
        "purchase-confirmation",
        "faq",
        "company",
    ]
    assert document.image_count == 11
    assert tuple(image["src"] for image in soup.select("img")) == document.image_sources
    assert len(set(document.image_sources)) == 11
    assert soup.select("[data-geo-section='company']")[-1] == soup.select(
        "[data-geo-section]"
    )[-1]
    assert [image["alt"] for image in soup.select("[data-geo-section='company'] img")] == [
        f"公司介绍与服务能力 {index}" for index in range(1, 7)
    ]
    assert [image["alt"] for image in soup.select("[data-geo-section='product-images'] img")] == [
        f"SUNON DP201AT-2122HBL.GN {role}"
        for role in ("铭牌侧整机", "铭牌侧视图", "叶轮侧视图", "侧面与引线")
    ]
    for text in (
        "DP201AT-2122HBL.GN",
        "220-240VAC",
        "66CFM / 112.1m³/h",
        "80CFM / 135.9m³/h",
        "119±0.5mm",
        "25.5±0.5mm",
        "104.8±0.3mm",
        "320±10mm",
        "1688平台风叶直径映射（外框宽度）",
        "前值对应50Hz工作点，后值对应60Hz工作点；它们属于同一SKU",
    ):
        assert text in document.html


def test_sparse_detail_omits_unsupported_optional_sections(
    sparse_payload: ProductPayload,
) -> None:
    document = _render(sparse_payload)
    soup = BeautifulSoup(document.html, "html.parser")

    assert [node["data-geo-section"] for node in soup.select("[data-geo-section]")] == [
        "entity-answer",
        "core-parameters",
        "product-images",
        "dimensions-installation",
        "purchase-confirmation",
        "faq",
        "company",
    ]
    assert document.image_count == 11
    assert "—" not in soup.select_one("[data-geo-section='core-parameters']").get_text()
    assert "ebm-papst" not in soup.select_one("[data-geo-section='entity-answer']").get_text()


def test_delta_product_evidence_stays_outside_fixed_company_tail(
    sparse_payload: ProductPayload,
) -> None:
    delta = sparse_payload.model_copy(
        update={
            "brand": "Delta",
            "model": "AFB1212H",
            "title": "Delta AFB1212H 12V 120mm直流轴流风扇",
            "attributes": {"产品别名": "直流轴流风扇", "品牌": "Delta"},
            "specification": {"规格型号": "AFB1212H", "额定电压_v": 12},
        }
    )

    soup = BeautifulSoup(_render(delta).html, "html.parser")
    product_html = "".join(str(section) for section in soup.select("[data-geo-section]:not([data-geo-section='company'])"))
    company = soup.select_one("[data-geo-section='company']")

    assert "Delta" in product_html
    assert "SUNON" not in product_html
    assert "ebm-papst" not in product_html
    assert company is not None
    assert [image["src"] for image in company.select("img")] == list(
        load_detail_policy().company_image_urls
    )


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("电压范围_v", "220 VAC", "220 VAC"),
        ("最大静压_inH2O", "1.2inH2O", "1.2inH2O"),
        ("最大静压_inH2O", "1.2inH₂O", "1.2inH₂O"),
    ],
)
def test_geo_detail_preserves_existing_unit_aliases(
    sparse_payload: ProductPayload,
    key: str,
    value: str,
    expected: str,
) -> None:
    payload = sparse_payload.model_copy(
        update={"specification": {"规格型号": "A2175-HBL", key: value}}
    )

    html = _render(payload).html

    assert expected in html
    assert "VACV" not in html
    assert "inH2OinH₂O" not in html
    assert "inH₂OinH₂O" not in html


def test_geo_detail_deduplicates_rows_without_merging_different_meanings(
    sparse_payload: ProductPayload,
) -> None:
    payload = sparse_payload.model_copy(
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
            "specification": {"规格型号": "A2175-HBL", "额定电压_v": "220 VAC"},
        }
    )

    soup = BeautifulSoup(_render(payload).html, "html.parser")
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
    sparse_payload: ProductPayload,
) -> None:
    model = 'A2175-HBL"><img src=x onerror=alert(1)>'
    payload = sparse_payload.model_copy(
        update={
            "model": model,
            "brand": "SUNON<script>alert(1)</script>",
            "attributes": {'参数"><script>alert(2)</script>': "<img src=x onerror=alert(3)>"},
            "specification": {"规格型号": model},
        }
    )

    html = _render(
        payload,
        image_roles=['正面" onerror="alert(4)', "背面", "电机", "铭牌"],
    ).html
    soup = BeautifulSoup(html, "html.parser")

    assert not soup.select("script")
    assert not soup.select("[onerror]")
    assert "&lt;script&gt;" in html
    assert "&lt;img src=x onerror=alert(3)&gt;" in html


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
    sparse_payload: ProductPayload,
    drawing_url: str,
    image_urls: list[str],
    image_roles: list[str],
) -> None:
    with pytest.raises(ManualReviewRequired):
        render_geo_detail(
            payload=sparse_payload,
            drawing_url=drawing_url,
            image_urls=image_urls,
            image_roles=image_roles,
        )


def test_geo_detail_rejects_payload_model_mismatch(
    sparse_payload: ProductPayload,
) -> None:
    mismatched = sparse_payload.model_copy(update={"specification": {"规格型号": "OTHER"}})

    with pytest.raises(ManualReviewRequired, match="model"):
        _render(mismatched)
