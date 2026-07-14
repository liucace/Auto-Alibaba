from dataclasses import dataclass

from app.domain.models import ProductPayload
from app.products.title_policy import validate_product_title


def _text(value: str | int | float) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


@dataclass(frozen=True)
class FormField:
    index: int
    label: str
    value: str


@dataclass(frozen=True)
class FormPlan:
    category_url: str
    title: str
    attribute_fields: tuple[FormField, ...]
    spec_fields: tuple[FormField, ...]
    sales_values: tuple[str, ...]
    delivery_time: str
    shipping_template: str
    package_values: tuple[str, ...]


def build_form_plan(payload: ProductPayload) -> FormPlan:
    attributes = payload.attributes
    specification = payload.specification
    title = validate_product_title(
        title=payload.title,
        brand=payload.brand,
        model=payload.model,
        product_name=payload.attributes.get("产品别名"),
    )
    attribute_labels = (
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
    spec_labels = (
        "规格型号",
        "电机功率_w",
        "风叶直径_m",
        "转速_rpm",
        "风量_m3h",
        "电流_a",
        "重量_kg",
    )
    return FormPlan(
        category_url=(
            "https://offer-new.1688.com/industry/publish.htm?"
            f"catId={payload.category_id}&industryCategoryId={payload.industry_category_id}"
            "&saleChannel=default&operator=new"
        ),
        title=title,
        attribute_fields=tuple(
            FormField(index=index, label=label, value=value)
            for index, label in enumerate(attribute_labels)
            if label in attributes and (value := _text(attributes[label]))
        ),
        spec_fields=tuple(
            FormField(index=index, label=label, value=value)
            for index, label in enumerate(spec_labels)
            if label in specification and (value := _text(specification[label]))
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
