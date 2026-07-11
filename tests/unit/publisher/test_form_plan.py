from app.domain.models import PackageInfo, ProductPayload
from app.publisher.form_plan import build_form_plan


def test_form_plan_contains_only_verified_business_values() -> None:
    payload = ProductPayload(
        model="W3G630-NU33-03",
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
    assert plan.spec_values == ("W3G630-NU33-03", "3600", "0.63", "1800", "22150", "5.5", "39.3")
    assert plan.sales_values == ("1", "10000", "10", "W3G630-NU33-03")
    assert plan.package_values == ("80.5", "79.7", "27", "39300")
    assert plan.delivery_time == "48小时发货"
    assert plan.shipping_template == "运费"
