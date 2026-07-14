import unicodedata
from dataclasses import dataclass
from html import escape
from typing import Any

from app.domain.errors import ManualReviewRequired
from app.domain.models import ProductPayload
from app.ingest.model_number import exact_model_match
from app.products.detail_policy import DetailPolicy, load_detail_policy


@dataclass(frozen=True)
class RenderedDetail:
    html: str
    image_sources: tuple[str, ...]

    @property
    def image_count(self) -> int:
        return len(self.image_sources)


SPEC_META: dict[str, tuple[str, str]] = {
    "规格型号": ("规格型号", ""),
    "额定电压_v": ("额定电压", "V"),
    "电压范围_v": ("电压范围", "V"),
    "启动电压_v": ("启动电压", "V"),
    "频率_hz": ("频率", "Hz"),
    "电机功率_w": ("电机功率", "W"),
    "风叶直径_m": ("1688平台风叶直径映射（外框宽度）", "m"),
    "转速_rpm": ("转速", "rpm"),
    "风量_m3h": ("风量", "m³/h"),
    "风量_cfm": ("风量", "CFM"),
    "最大静压_pa": ("最大静压", "Pa"),
    "最大静压_inH2O": ("最大静压", "inH₂O"),
    "电流_a": ("电流", "A"),
    "安全电流_a": ("安全电流", "A"),
    "重量_kg": ("重量", "kg"),
    "尺寸_mm": ("标称尺寸", "mm"),
    "外框宽度_mm": ("外框宽度", "mm"),
    "厚度_mm": ("厚度", "mm"),
    "安装孔距_mm": ("安装孔距", "mm"),
    "安装孔": ("安装孔", ""),
    "引线长度_mm": ("引线长度", "mm"),
    "防护等级": ("防护等级", ""),
    "绝缘等级": ("绝缘等级", ""),
    "电机保护": ("电机保护", ""),
    "框体材质": ("框体材质", ""),
    "叶轮材质": ("叶轮材质", ""),
    "引线规格": ("引线规格", ""),
    "轴承系统": ("轴承系统", ""),
    "气流方向": ("气流方向", ""),
    "旋转方向": ("旋转方向", ""),
    "安装方向": ("安装方向", ""),
    "工作温度_c": ("工作温度", "°C"),
    "存储温度_c": ("存储温度", "°C"),
    "认证": ("认证", ""),
}

SPEC_UNIT_ALIASES: dict[str, tuple[str, ...]] = {
    "规格型号": (),
    "额定电压_v": ("V", "VAC", "VDC"),
    "电压范围_v": ("V", "VAC", "VDC"),
    "启动电压_v": ("V", "VAC", "VDC"),
    "频率_hz": ("Hz",),
    "电机功率_w": ("W", "kW", "MW"),
    "风叶直径_m": ("m", "mm", "cm"),
    "转速_rpm": ("rpm", "r/min", "rev/min", "min⁻¹"),
    "风量_m3h": ("m³/h", "m3/h", "m³h", "m3h", "CMH"),
    "风量_cfm": ("CFM", "ft³/min", "ft3/min"),
    "最大静压_pa": ("Pa", "kPa", "MPa"),
    "最大静压_inH2O": ("inH2O", "inH₂O", "in H2O", "in H₂O"),
    "电流_a": ("A", "mA"),
    "安全电流_a": ("A", "mA"),
    "重量_kg": ("kg", "g"),
    "尺寸_mm": ("mm", "cm", "m"),
    "外框宽度_mm": ("mm", "cm", "m"),
    "厚度_mm": ("mm", "cm", "m"),
    "安装孔距_mm": ("mm", "cm", "m"),
    "安装孔": (),
    "引线长度_mm": ("mm", "cm", "m"),
    "防护等级": (),
    "绝缘等级": (),
    "电机保护": (),
    "框体材质": (),
    "叶轮材质": (),
    "引线规格": (),
    "轴承系统": (),
    "气流方向": (),
    "旋转方向": (),
    "安装方向": (),
    "工作温度_c": ("°C", "℃", "C"),
    "存储温度_c": ("°C", "℃", "C"),
    "认证": (),
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


def _section(slug: str, title: str, body: str, *, alternate: bool = False) -> str:
    background = "#f6f8fb" if alternate else "#ffffff"
    return (
        f'<div data-geo-section="{escape(slug, quote=True)}" '
        f'style="padding:20px 16px;background:{background};border-bottom:1px solid #d8d8d8">'
        f"{_heading(title)}{body}</div>"
    )


def _operating_point_table(payload: ProductPayload) -> str:
    headers = "".join(
        f'<th style="padding:10px;border:1px solid #d8d8d8;background:#0b3a70;color:#fff">{escape(value)}</th>'
        for value in ("频率", "转速", "风量", "最大静压", "电流", "功率", "噪声")
    )
    body = "".join(
        "<tr>"
        + "".join(
            f'<td style="padding:10px;border:1px solid #d8d8d8">{escape(value)}</td>'
            for value in (
                f"{point.frequency_hz}Hz",
                f"{point.speed_rpm:g}RPM" if point.speed_rpm is not None else "—",
                (
                    f"{point.airflow_cfm:g}CFM / {point.airflow_m3h:g}m³/h"
                    if point.airflow_cfm is not None and point.airflow_m3h is not None
                    else "—"
                ),
                (
                    f"{point.static_pressure_in_h2o:g}inH₂O"
                    if point.static_pressure_in_h2o is not None
                    else "—"
                ),
                f"{point.current_a:g}A" if point.current_a is not None else "—",
                f"{point.power_w:g}W" if point.power_w is not None else "—",
                f"{point.noise_db_a:g}dB(A)" if point.noise_db_a is not None else "—",
            )
        )
        + "</tr>"
        for point in payload.operating_points
    )
    return (
        '<table style="width:100%;border-collapse:collapse"><thead><tr>'
        f"{headers}</tr></thead><tbody>{body}</tbody></table>"
    )


def _selected_rows(payload: ProductPayload, keys: tuple[str, ...]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for key in keys:
        value = payload.specification.get(key)
        if value is None or not _is_present(value):
            continue
        label, unit = _spec_label_and_unit(key)
        rows.append((label, _value_with_unit(value, unit, SPEC_UNIT_ALIASES.get(key, ()))))
    return rows


def _product_image_grid(prefix: str, urls: list[str], roles: list[str]) -> str:
    cells = [
        (
            '<td style="width:50%;padding:6px;vertical-align:top">'
            f'<img src="{escape(url, quote=True)}" alt="{escape(f"{prefix} {role}", quote=True)}" '
            'style="display:block;width:100%;height:auto" />'
            f'<p style="margin:6px 0 0;text-align:center">{escape(role)}</p></td>'
        )
        for url, role in zip(urls, roles, strict=True)
    ]
    return (
        '<table style="width:100%;border-collapse:collapse"><tbody>'
        f"<tr>{cells[0]}{cells[1]}</tr><tr>{cells[2]}{cells[3]}</tr>"
        "</tbody></table>"
    )


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
        if key == "规格型号" or exact_model_match(_plain_text(specification_value), payload.model):
            continue
        normalized_key = key.strip()
        label, unit = _spec_label_and_unit(normalized_key)
        aliases = SPEC_UNIT_ALIASES.get(normalized_key, ())
        collector.add(label, _value_with_unit(specification_value, unit, aliases))
    return collector.rows


def _purchase_confirmation(payload: ProductPayload) -> str:
    rows = [("完整型号", payload.model)]
    rows.extend(_selected_rows(payload, ("额定电压_v", "频率_hz", "尺寸_mm", "安装孔距_mm")))
    return _table(rows)


def _faq(payload: ProductPayload) -> str:
    answers = [
        (
            "如何确认型号？",
            f"请核对品牌 {payload.brand} 和完整型号 {payload.model}，不要按相近后缀替代。",
        )
    ]
    if {point.frequency_hz for point in payload.operating_points} == {50, 60}:
        answers.append(
            (
                "斜杠参数如何理解？",
                "规格中的前值对应50Hz工作点，后值对应60Hz工作点；它们属于同一SKU。",
            )
        )
    dimensions = _selected_rows(payload, ("尺寸_mm", "安装孔距_mm", "厚度_mm"))
    if dimensions:
        summary = "；".join(f"{label}：{value}" for label, value in dimensions)
        answers.append(("安装前需要核对什么？", summary))
    return "".join(
        '<div style="margin:0 0 14px">'
        f'<h3 style="margin:0 0 5px;font-size:16px;color:#0b3a70">{escape(question)}</h3>'
        f'<p style="margin:0">{escape(answer)}</p></div>'
        for question, answer in answers
    )


def _validate(
    payload: ProductPayload,
    drawing_url: str,
    image_urls: list[str],
    image_roles: list[str],
    policy: DetailPolicy,
) -> None:
    current_sources = [drawing_url, *image_urls]
    all_sources = [*image_urls, drawing_url, *policy.company_image_urls]
    if (
        len(image_urls) != policy.current_product_image_count
        or len(image_roles) != policy.current_product_image_count
        or any(not value.strip() for value in current_sources)
        or any(not role.strip() for role in image_roles)
        or len(all_sources) != len(set(all_sources))
        or not policy.sections
        or policy.sections[-1] != "company"
    ):
        raise ManualReviewRequired("GEO detail image and section policy is not satisfied")
    specification_model = payload.specification.get("规格型号")
    if not _is_present(specification_model) or not exact_model_match(
        str(specification_model), payload.model
    ):
        raise ManualReviewRequired("detail specification model does not match payload model")


def render_geo_detail(
    *,
    payload: ProductPayload,
    drawing_url: str,
    image_urls: list[str],
    image_roles: list[str],
    policy: DetailPolicy | None = None,
) -> RenderedDetail:
    active_policy = policy or load_detail_policy()
    _validate(payload, drawing_url, image_urls, image_roles, active_policy)
    prefix = f"{payload.brand} {payload.model}"
    product_name = payload.attributes.get("产品别名") or payload.attributes.get("类型")
    identity = f"这是 {prefix}{(' ' + product_name) if product_name else ''}。"
    quick_rows = _selected_rows(
        payload,
        ("额定电压_v", "频率_hz", "尺寸_mm", "轴承系统", "重量_kg"),
    )
    dimension_rows = _selected_rows(
        payload,
        (
            "外框宽度_mm",
            "厚度_mm",
            "安装孔距_mm",
            "安装孔",
            "引线长度_mm",
            "气流方向",
            "旋转方向",
            "安装方向",
        ),
    )
    technical_rows = _selected_rows(
        payload,
        (
            "框体材质",
            "叶轮材质",
            "引线规格",
            "电压范围_v",
            "启动电压_v",
            "安全电流_a",
            "电机保护",
            "绝缘等级",
            "工作温度_c",
            "存储温度_c",
            "认证",
        ),
    )
    product_images = _product_image_grid(prefix, image_urls, image_roles)
    sections = [_section("entity-answer", "型号确认", f"<p>{escape(identity)}</p>")]
    if quick_rows:
        sections.append(_section("quick-facts", "快速确认", _table(quick_rows), alternate=True))
    sections.append(_section("core-parameters", "核心参数", _table(_parameter_rows(payload))))
    if payload.operating_points:
        sections.append(
            _section(
                "operating-points",
                "50/60Hz 工作点对照",
                _operating_point_table(payload),
                alternate=True,
            )
        )
    sections.append(_section("product-images", "实物与铭牌核对", product_images))
    dimension_body = _image(drawing_url, f"{prefix} 尺寸图")
    if dimension_rows:
        dimension_body += _table(dimension_rows)
    sections.append(
        _section(
            "dimensions-installation",
            "尺寸、安装与气流方向",
            dimension_body,
            alternate=True,
        )
    )
    if technical_rows:
        sections.append(
            _section(
                "materials-electrical-environment",
                "材料、电气与环境信息",
                _table(technical_rows),
            )
        )
    sections.append(
        _section(
            "purchase-confirmation",
            "采购前核对",
            _purchase_confirmation(payload),
            alternate=True,
        )
    )
    sections.append(_section("faq", "常见问题", _faq(payload)))
    company_images = "".join(
        _image(url, f"{active_policy.company_heading} {index}")
        for index, url in enumerate(active_policy.company_image_urls, start=1)
    )
    sections.append(
        _section(
            "company",
            active_policy.company_heading,
            company_images,
            alternate=True,
        )
    )
    html = (
        f'<div style="width:100%;max-width:{active_policy.editor_width_px}px;margin:0 auto;'
        "font-family:arial,microsoft yahei,sans-serif;"
        'color:#222;background:#fff;line-height:1.75;font-size:14px">'
        + "".join(sections)
        + "</div>"
    )
    return RenderedDetail(
        html=html,
        image_sources=tuple([*image_urls, drawing_url, *active_policy.company_image_urls]),
    )
