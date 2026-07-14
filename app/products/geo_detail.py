import unicodedata
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
    "最大静压_inH2O": ("最大静压", "inH₂O"),
    "电流_a": ("电流", "A"),
    "重量_kg": ("重量", "kg"),
    "防护等级": ("防护等级", ""),
    "绝缘等级": ("绝缘等级", ""),
    "电机保护": ("电机保护", ""),
    "框体材质": ("框体材质", ""),
    "轴承系统": ("轴承系统", ""),
    "工作温度_c": ("工作温度", "°C"),
}

SPEC_UNIT_ALIASES: dict[str, tuple[str, ...]] = {
    "规格型号": (),
    "额定电压_v": ("V", "VAC", "VDC"),
    "电压范围_v": ("V", "VAC", "VDC"),
    "频率_hz": ("Hz",),
    "电机功率_w": ("W", "kW", "MW"),
    "风叶直径_m": ("m", "mm", "cm"),
    "转速_rpm": ("rpm", "r/min", "rev/min", "min⁻¹"),
    "风量_m3h": ("m³/h", "m3/h", "m³h", "m3h", "CMH"),
    "风量_cfm": ("CFM", "ft³/min", "ft3/min"),
    "最大静压_pa": ("Pa", "kPa", "MPa"),
    "最大静压_inH2O": ("inH2O", "inH₂O", "in H2O", "in H₂O"),
    "电流_a": ("A", "mA"),
    "重量_kg": ("kg", "g"),
    "防护等级": (),
    "绝缘等级": (),
    "电机保护": (),
    "框体材质": (),
    "轴承系统": (),
    "工作温度_c": ("°C", "℃", "C"),
}

_MODEL_LABELS = {"model", "型号", "规格型号", "完整型号"}
_BRAND_LABELS = {"brand", "品牌"}


def _plain_text(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    return str(value).strip()


def _is_present(value: Any) -> bool:
    return bool(_plain_text(value))


def _normalize_row_part(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.split()).casefold()


def _normalize_identity(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return "".join(normalized.split()).casefold()


class _RowCollector:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str]] = []
        self._seen: set[tuple[str, str]] = set()

    def add(self, label: str, value: str) -> None:
        normalized = (_normalize_row_part(label), _normalize_row_part(value))
        if normalized in self._seen:
            return
        self._seen.add(normalized)
        self.rows.append((label.strip(), value.strip()))


def _unknown_label(key: str) -> str:
    label, separator, suffix = key.rpartition("_")
    if separator and label and suffix:
        return f"{label} ({suffix})"
    return key


def _spec_label_and_unit(key: str) -> tuple[str, str]:
    return SPEC_META.get(key, (_unknown_label(key), ""))


def _unit_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(normalized.split())


def _has_unit_alias(value: str, aliases: tuple[str, ...]) -> bool:
    normalized_value = _unit_text(value)
    for alias in aliases:
        normalized_alias = _unit_text(alias)
        if not normalized_alias or not normalized_value.endswith(normalized_alias):
            continue
        prefix = normalized_value[: -len(normalized_alias)]
        if prefix and prefix[-1].isdigit():
            return True
    return False


def _value_with_unit(value: Any, unit: str, aliases: tuple[str, ...]) -> str:
    text = _plain_text(value)
    if unit and not _has_unit_alias(text, aliases):
        text = f"{text}{unit}"
    return text


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
        f'<td style="padding:11px;border:1px solid #d8d8d8">{escape(value)}</td>'
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
    collector = _RowCollector()
    collector.add("品牌", payload.brand)
    collector.add("完整型号", payload.model)
    normalized_brand = _normalize_identity(payload.brand)
    for key, attribute_value in payload.attributes.items():
        if not key.strip() or not _is_present(attribute_value):
            continue
        text = _plain_text(attribute_value)
        normalized_label = _normalize_identity(key)
        if normalized_label in _MODEL_LABELS or exact_model_match(text, payload.model):
            continue
        if normalized_label in _BRAND_LABELS or _normalize_identity(text) == normalized_brand:
            continue
        collector.add(_unknown_label(key.strip()), text)

    for key, specification_value in payload.specification.items():
        if not key.strip() or not _is_present(specification_value):
            continue
        if key == "规格型号" or exact_model_match(
            _plain_text(specification_value), payload.model
        ):
            continue
        normalized_key = key.strip()
        label, unit = _spec_label_and_unit(normalized_key)
        aliases = SPEC_UNIT_ALIASES.get(normalized_key, ())
        collector.add(label, _value_with_unit(specification_value, unit, aliases))
    return collector.rows


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
