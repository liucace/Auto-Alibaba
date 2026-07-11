from dataclasses import dataclass

from app.domain.models import ProductPayload


def _text(value: str | int | float) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


@dataclass(frozen=True)
class FormPlan:
    category_url: str
    title: str
    attribute_values: tuple[str, ...]
    spec_values: tuple[str, ...]
    sales_values: tuple[str, ...]
    delivery_time: str
    shipping_template: str
    package_values: tuple[str, ...]


def build_form_plan(payload: ProductPayload) -> FormPlan:
    attributes = payload.attributes
    specification = payload.specification
    return FormPlan(
        category_url=(
            "https://offer-new.1688.com/industry/publish.htm?"
            f"catId={payload.category_id}&industryCategoryId={payload.industry_category_id}"
            "&saleChannel=default&operator=new"
        ),
        title=payload.title,
        attribute_values=tuple(
            attributes.get(name, "")
            for name in (
                "电压",
                "产品别名",
                "风叶材质",
                "品牌",
                "噪声",
                "类型",
                "叶片数",
                "适用范围",
                "工业风扇种类",
            )
        ),
        spec_values=tuple(
            _text(specification[name])
            for name in (
                "规格型号",
                "电机功率_w",
                "风叶直径_m",
                "转速_rpm",
                "风量_m3h",
                "电流_a",
                "重量_kg",
            )
        ),
        sales_values=("1", str(payload.price), str(payload.stock), payload.model),
        delivery_time=payload.delivery_time,
        shipping_template=payload.shipping_template,
        package_values=(
            _text(payload.package.length_cm),
            _text(payload.package.width_cm),
            _text(payload.package.height_cm),
            str(payload.package.weight_g),
        ),
    )
