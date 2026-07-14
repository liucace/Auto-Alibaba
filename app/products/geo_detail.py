from html import escape
from typing import Any

from app.domain.errors import ManualReviewRequired
from app.domain.models import ProductPayload
from app.ingest.model_number import exact_model_match

SPEC_META: dict[str, tuple[str, str]] = {
    "规格型号": ("规格型号", ""),
    "额定电压_v": ("额定电压", "V"),
    "电压范围_v": ("电压范围", "V"),
    "频率_hz": ("频率", "Hz"),
    "电机功率_w": ("电机功率", "W"),
    "风叶直径_m": ("风叶直径", "m"),
    "转速_rpm": ("转速", "rpm"),
    "风量_m3h": ("风量", "m³/h"),
    "风量_cfm": ("风量", "CFM"),
    "最大静压_pa": ("最大静压", "Pa"),
    "最大静压_inH2O": ("最大静压", "inH2O"),
    "电流_a": ("电流", "A"),
    "重量_kg": ("重量", "kg"),
    "防护等级": ("防护等级", ""),
    "绝缘等级": ("绝缘等级", ""),
    "电机保护": ("电机保护", ""),
    "框体材质": ("框体材质", ""),
    "轴承系统": ("轴承系统", ""),
    "工作温度_c": ("工作温度", "°C"),
}


def _plain_text(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    return str(value).strip()


def _is_present(value: Any) -> bool:
    return bool(_plain_text(value))


def _unknown_label(key: str) -> str:
    label, separator, suffix = key.rpartition("_")
    if separator and label and suffix:
        return f"{label} ({suffix})"
    return key


def _spec_label_and_unit(key: str) -> tuple[str, str]:
    return SPEC_META.get(key, (_unknown_label(key), ""))


def _value_with_unit(value: Any, unit: str) -> str:
    text = _plain_text(value)
    if unit and not text.casefold().endswith(unit.casefold()):
        text = f"{text}{unit}"
    return escape(text)


def _image(url: str, alt: str) -> str:
    return (
        '<p style="margin:12px 0;text-align:center">'
        f'<img src="{escape(url.strip(), quote=True)}" alt="{escape(alt, quote=True)}" '
        'style="display:block;width:100%;max-width:100%;height:auto;margin:0 auto" /></p>'
    )


def _heading(title: str) -> str:
    return (
        '<h2 style="margin:0 0 12px;font-size:21px;line-height:1.35;'
        f'color:#0b3a70;font-weight:bold">{escape(title)}</h2>'
    )


def _table(rows: list[tuple[str, str]]) -> str:
    body = "".join(
        "<tr>"
        f'<td style="width:25%;padding:11px;border:1px solid #d8d8d8;'
        f'background:#eef3f8;font-weight:bold">{escape(label)}</td>'
        f'<td style="padding:11px;border:1px solid #d8d8d8">{value}</td>'
        "</tr>"
        for label, value in rows
    )
    return (
        '<table style="width:100%;border-collapse:collapse;background:#ffffff;text-align:left">'
        f"<tbody>{body}</tbody></table>"
    )


def _validate(
    payload: ProductPayload,
    drawing_url: str,
    image_urls: list[str],
    image_roles: list[str],
) -> None:
    all_urls = [drawing_url, *image_urls]
    normalized_urls = [url.strip() for url in all_urls]
    if (
        len(image_urls) != 4
        or len(image_roles) != 4
        or any(not url for url in normalized_urls)
        or len(set(normalized_urls)) != 5
        or any(not role.strip() for role in image_roles)
    ):
        raise ManualReviewRequired(
            "GEO detail requires five distinct current-model images and four image roles"
        )
    specification_model = payload.specification.get("规格型号")
    if not _is_present(specification_model) or not exact_model_match(
        str(specification_model), payload.model
    ):
        raise ManualReviewRequired("detail specification model does not match payload model")


def _parameter_rows(payload: ProductPayload) -> list[tuple[str, str]]:
    rows = [
        ("品牌", escape(payload.brand)),
        ("完整型号", escape(payload.model)),
    ]
    normalized_brand = payload.brand.strip().casefold()
    for key, attribute_value in payload.attributes.items():
        if not key.strip() or not _is_present(attribute_value):
            continue
        text = _plain_text(attribute_value)
        if text.casefold() == normalized_brand:
            continue
        rows.append((_unknown_label(key.strip()), escape(text)))

    for key, specification_value in payload.specification.items():
        if not key.strip() or not _is_present(specification_value):
            continue
        if key == "规格型号" or exact_model_match(
            _plain_text(specification_value), payload.model
        ):
            continue
        label, unit = _spec_label_and_unit(key.strip())
        rows.append((label, _value_with_unit(specification_value, unit)))
    return rows


def render_geo_detail(
    *,
    payload: ProductPayload,
    drawing_url: str,
    image_urls: list[str],
    image_roles: list[str],
) -> str:
    _validate(payload, drawing_url, image_urls, image_roles)
    prefix = f"{payload.brand} {payload.model}"
    product_images = "".join(
        _image(url, f"{prefix} {role.strip()}")
        for url, role in zip(image_urls, image_roles, strict=True)
    )
    definition = (
        f"品牌：{escape(payload.brand)}；完整型号：{escape(payload.model)}"
    )

    return f"""<div style="font-family:arial,microsoft yahei,sans-serif;color:#222222;background:#ffffff;line-height:1.75;font-size:14px">
<section data-geo-section="dimension-drawing" style="padding:20px 16px;border-bottom:4px solid #0b3a70">
{_heading("尺寸图")}
{_image(drawing_url, f"{prefix} 尺寸图")}
</section>
<section data-geo-section="product-images" style="padding:18px 16px;background:#f6f8fb">
{_heading("产品图片")}
{product_images}
</section>
<section data-geo-section="product-definition" style="padding:20px 16px;border-top:4px solid #0b3a70">
{_heading("产品定义")}
<p style="margin:0">{definition}</p>
</section>
<section data-geo-section="core-parameters" style="padding:18px 16px">
{_heading("核心参数")}
{_table(_parameter_rows(payload))}
</section>
</div>"""
