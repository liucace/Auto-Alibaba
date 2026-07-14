from app.domain.models import PackageInfo, ProductPayload
from app.publisher.form_plan import FormField, build_form_plan


def test_form_plan_contains_only_verified_business_values() -> None:
    payload = ProductPayload(
        model="W3G630-NU33-03",
        brand="ebm-papst",
        title="W3G630-NU33-03 title",
        category_id=1034320,
        industry_category_id=2293,
        attributes={
            "电压": "400",
            "产品别名": "EC轴流风机",
            "风叶材质": "PP塑料",
            "品牌": "ebm-papst",
            "噪声": "90",
            "类型": "轴流风扇",
            "叶片数": "5",
            "工业风扇种类": "轴流风扇",
        },
        specification={
            "规格型号": "W3G630-NU33-03",
            "电机功率_w": 3600,
            "风叶直径_m": 0.63,
            "转速_rpm": 1800,
            "风量_m3h": 22150,
            "电流_a": 5.5,
            "重量_kg": 39.3,
        },
        price=10000,
        stock=10,
        delivery_time="48小时发货",
        shipping_template="运费",
        package=PackageInfo(length_cm=80.5, width_cm=79.7, height_cm=27, weight_g=39300),
    )

    plan = build_form_plan(payload)

    assert plan.category_url.endswith(
        "catId=1034320&industryCategoryId=2293&saleChannel=default&operator=new"
    )
    assert plan.attribute_fields == (
        FormField(index=0, label="电压", value="400"),
        FormField(index=1, label="产品别名", value="EC轴流风机"),
        FormField(index=2, label="风叶材质", value="PP塑料"),
        FormField(index=3, label="品牌", value="ebm-papst"),
        FormField(index=4, label="噪声", value="90"),
        FormField(index=5, label="类型", value="轴流风扇"),
        FormField(index=6, label="叶片数", value="5"),
        FormField(index=8, label="工业风扇种类", value="轴流风扇"),
    )
    assert plan.spec_fields == (
        FormField(index=0, label="规格型号", value="W3G630-NU33-03"),
        FormField(index=1, label="电机功率_w", value="3600"),
        FormField(index=2, label="风叶直径_m", value="0.63"),
        FormField(index=3, label="转速_rpm", value="1800"),
        FormField(index=4, label="风量_m3h", value="22150"),
        FormField(index=5, label="电流_a", value="5.5"),
        FormField(index=6, label="重量_kg", value="39.3"),
    )
    assert plan.sales_values == ("1", "10000", "10", "W3G630-NU33-03")
    assert plan.package_values == ("80.5", "79.7", "27", "39300")
    assert plan.delivery_time == "48小时发货"
    assert plan.shipping_template == "运费"


def test_form_plan_preserves_sparse_sunon_field_indices() -> None:
    payload = ProductPayload(
        model="A2175-HBL",
        brand="SUNON",
        title="SUNON A2175-HBL title",
        category_id=1034320,
        industry_category_id=2293,
        attributes={
            "电压": " 220V ",
            "产品别名": "   ",
            "风叶材质": "\t",
            "品牌": " SUNON",
            "类型": "轴流风扇 ",
        },
        specification={
            "规格型号": " A2175-HBL ",
            "电机功率_w": 45,
            "风叶直径_m": "  ",
            "转速_rpm": 2800,
            "风量_m3h": "\t ",
            "电流_a": 0.21,
        },
        price=188,
        stock=10,
        delivery_time="48小时发货",
        shipping_template="运费",
        package=PackageInfo(length_cm=18, width_cm=18, height_cm=7, weight_g=700),
    )

    plan = build_form_plan(payload)

    assert plan.attribute_fields == (
        FormField(index=0, label="电压", value="220V"),
        FormField(index=3, label="品牌", value="SUNON"),
        FormField(index=5, label="类型", value="轴流风扇"),
    )
    assert plan.spec_fields == (
        FormField(index=0, label="规格型号", value="A2175-HBL"),
        FormField(index=1, label="电机功率_w", value="45"),
        FormField(index=3, label="转速_rpm", value="2800"),
        FormField(index=5, label="电流_a", value="0.21"),
    )
    assert plan.category_url.endswith(
        "catId=1034320&industryCategoryId=2293&saleChannel=default&operator=new"
    )
    assert plan.sales_values == ("1", "188", "10", "A2175-HBL")
    assert plan.package_values == ("18", "18", "7", "700")
    assert plan.delivery_time == "48小时发货"
    assert plan.shipping_template == "运费"
