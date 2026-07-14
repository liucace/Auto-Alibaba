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


def _heading(title: str) -> str:
    return (
        '<h2 style="margin:0 0 14px;color:#0b3a70;font-size:20px;line-height:1.35;'
        f'font-weight:bold">{escape(title)}</h2>'
    )


def _section(slug: str, title: str, body: str, *, alternate: bool = False) -> str:
    background = "#f7f9fb" if alternate else "#ffffff"
    return (
        f'<div data-geo-section="{escape(slug, quote=True)}" '
        f'style="box-sizing:border-box;padding:24px 25px;background:{background};'
        'border-bottom:1px solid #e4e8eb">'
        f"{_heading(title)}{body}</div>"
    )


def _paired_table(rows: list[tuple[str, str]]) -> str:
    rendered_rows: list[str] = []
    for index in range(0, len(rows), 2):
        pairs = rows[index : index + 2]
        cells: list[str] = []
        for pair_index, (label, value) in enumerate(pairs):
            cells.append(
                '<th style="box-sizing:border-box;width:21%;padding:9px 10px;'
                'border:1px solid #d6dde4;background:#eaf1f6;color:#234;text-align:left;'
                f'font-weight:bold">{escape(label)}</th>'
            )
            colspan = ' colspan="3"' if len(pairs) == 1 and pair_index == 0 else ""
            cells.append(
                f'<td{colspan} style="box-sizing:border-box;padding:9px 10px;'
                f'border:1px solid #d6dde4;text-align:left">{escape(value)}</td>'
            )
        rendered_rows.append(f"<tr>{''.join(cells)}</tr>")
    return (
        '<table data-geo-component="paired-spec" '
        'style="width:100%;border-collapse:collapse;background:#fff;text-align:left">'
        f"<tbody>{''.join(rendered_rows)}</tbody></table>"
    )


def _slash_values(value: Any, count: int, unit: str) -> list[str] | None:
    parts = [part.strip() for part in _plain_text(value).split("/")]
    if len(parts) != count or any(not part for part in parts):
        return None
    return [part if _has_unit_alias(part, (unit,)) else f"{part}{unit}" for part in parts]


def _operating_point_table(payload: ProductPayload) -> str:
    points = list(payload.operating_points)
    headers = ["规格项目", *(f"{point.frequency_hz}Hz" for point in points)]
    candidates: list[tuple[str, list[str] | None]] = [
        (
            "额定功率",
            [f"{point.power_w:g}W" for point in points]
            if all(point.power_w is not None for point in points)
            else None,
        ),
        (
            "额定转速",
            [f"{point.speed_rpm:g}r/min" for point in points]
            if all(point.speed_rpm is not None for point in points)
            else None,
        ),
        (
            "风量",
            [f"{point.airflow_cfm:g}CFM" for point in points]
            if all(point.airflow_cfm is not None for point in points)
            else None,
        ),
        (
            "换算风量",
            [f"{point.airflow_m3h:g}m³/h" for point in points]
            if all(point.airflow_m3h is not None for point in points)
            else None,
        ),
        (
            "最大静压",
            [f"{point.static_pressure_in_h2o:g}inH₂O" for point in points]
            if all(point.static_pressure_in_h2o is not None for point in points)
            else None,
        ),
        (
            "额定电流",
            [f"{point.current_a:g}A" for point in points]
            if all(point.current_a is not None for point in points)
            else None,
        ),
        (
            "安全电流",
            _slash_values(payload.specification.get("安全电流_a", ""), len(points), "A"),
        ),
        (
            "噪声",
            [f"{point.noise_db_a:g}dB(A)" for point in points]
            if all(point.noise_db_a is not None for point in points)
            else None,
        ),
    ]
    rows = [(label, values) for label, values in candidates if values]
    rendered_headers = "".join(
        '<th style="box-sizing:border-box;padding:9px 8px;border:1px solid #d6dde4;'
        f'background:#0b3a70;color:#fff;text-align:center">{escape(header)}</th>'
        for header in headers
    )
    rendered_rows = "".join(
        "<tr>"
        '<td style="box-sizing:border-box;padding:9px 8px;border:1px solid #d6dde4;'
        f'background:#eef3f7;text-align:left;font-weight:bold">{escape(label)}</td>'
        + "".join(
            '<td style="box-sizing:border-box;padding:9px 8px;border:1px solid #d6dde4;'
            f'text-align:center">{escape(value)}</td>'
            for value in values
        )
        + "</tr>"
        for label, values in rows
    )
    table = (
        '<table data-geo-component="frequency-comparison" '
        'style="width:100%;border-collapse:collapse;text-align:center">'
        f"<thead><tr>{rendered_headers}</tr></thead><tbody>{rendered_rows}</tbody></table>"
    )
    if all(point.airflow_cfm is not None and point.airflow_m3h is not None for point in points):
        table += (
            '<div data-geo-component="conversion-note" style="box-sizing:border-box;'
            'margin-top:12px;padding:10px 12px;background:#fff7d8;color:#6f5500;font-size:12px">'
            "风量换算仅为满足1688的m³/h字段：1CFM≈1.699m³/h；详情同时保留规格书原始CFM值。"
            "</div>"
        )
    return table


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
            '<td style="box-sizing:border-box;width:50%;padding:5px;vertical-align:top">'
            f'<img src="{escape(url, quote=True)}" alt="{escape(f"{prefix} {role}", quote=True)}" '
            'style="display:block;width:100%;height:auto" />'
            '<p style="box-sizing:border-box;margin:0;padding:7px 8px;background:#f2f4f6;'
            f'text-align:center;color:#555">{escape(role)}</p></td>'
        )
        for url, role in zip(urls, roles, strict=True)
    ]
    return (
        '<table data-geo-component="photo-grid" '
        'style="width:calc(100% + 10px);margin:-5px;border-collapse:collapse"><tbody>'
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


def _spec_text(payload: ProductPayload, key: str) -> str | None:
    value = payload.specification.get(key)
    if value is None or not _is_present(value):
        return None
    _, unit = _spec_label_and_unit(key)
    return _value_with_unit(value, unit, SPEC_UNIT_ALIASES.get(key, ()))


def _product_name(payload: ProductPayload) -> str | None:
    for key in ("产品别名", "类型", "工业风扇种类"):
        value = payload.attributes.get(key)
        if value and value.strip():
            return value.strip()
    return None


def _brand_display(payload: ProductPayload) -> str:
    value = payload.attributes.get("品牌", "").strip()
    return value or payload.brand


def _voltage_text(payload: ProductPayload, key: str = "额定电压_v") -> str | None:
    value = payload.specification.get(key)
    if value is None or not _is_present(value):
        return None
    text = _plain_text(value)
    if _has_unit_alias(text, SPEC_UNIT_ALIASES[key]):
        return text
    product_name = _product_name(payload) or ""
    suffix = "VAC" if "交流" in product_name else "VDC" if "直流" in product_name else "V"
    return f"{text}{suffix}"


def _nominal_mm(value: Any) -> str:
    text = _plain_text(value).replace("毫米", "").replace("mm", "")
    return text.split("±", 1)[0].strip()


def _drawing_dimensions(payload: ProductPayload) -> str | None:
    width = payload.specification.get("外框宽度_mm")
    thickness = payload.specification.get("厚度_mm")
    if (
        width is not None
        and thickness is not None
        and _is_present(width)
        and _is_present(thickness)
    ):
        nominal_width = _nominal_mm(width)
        nominal_thickness = _nominal_mm(thickness)
        return f"{nominal_width}×{nominal_width}×{nominal_thickness}mm"
    return _spec_text(payload, "尺寸_mm")


def _weight_text(payload: ProductPayload) -> str | None:
    value = payload.specification.get("重量_kg")
    if value is None or not _is_present(value):
        return None
    text = _plain_text(value)
    lowered = text.casefold().replace(" ", "")
    try:
        if lowered.endswith("kg"):
            kilograms = float(lowered[:-2])
        elif lowered.endswith("g"):
            return f"{float(lowered[:-1]):g}g"
        else:
            kilograms = float(lowered)
    except ValueError:
        return text
    return f"{kilograms * 1000:g}g"


def _slash_point_summary(payload: ProductPayload, field: str, unit: str = "") -> str | None:
    points = list(payload.operating_points)
    if not points:
        return None
    values = [getattr(point, field) for point in points]
    if any(value is None for value in values):
        return None
    return "/".join(f"{value:g}" for value in values) + unit


def _quick_cards(payload: ProductPayload) -> str:
    cards = [
        ("额定电压", _voltage_text(payload)),
        ("额定风量", _slash_point_summary(payload, "airflow_cfm", "CFM")),
        ("额定转速", _slash_point_summary(payload, "speed_rpm")),
        ("重量", _weight_text(payload)),
    ]
    present = [(label, value) for label, value in cards if value]
    if not present:
        return ""
    width = 100 / len(present)
    cells = "".join(
        '<td style="box-sizing:border-box;padding:13px 9px;background:#fff;text-align:center;'
        f'width:{width:g}%">'
        f'<b style="display:block;color:#0b3a70;font-size:13px">{escape(label)}</b>'
        f'<span style="font-size:15px">{escape(value)}</span></td>'
        for label, value in present
    )
    return (
        '<table data-geo-component="quick-cards" style="width:100%;border-collapse:separate;'
        f'border-spacing:1px;background:#d7e2ec"><tbody><tr>{cells}</tr></tbody></table>'
    )


def _core_rows(payload: ProductPayload) -> list[tuple[str, str]]:
    collector = _RowCollector()
    collector.add("品牌", _brand_display(payload))
    collector.add("完整型号", payload.model)
    targeted = (
        ("额定电压", _voltage_text(payload)),
        ("工作电压", _voltage_text(payload, "电压范围_v")),
        ("频率", _spec_text(payload, "频率_hz")),
        ("外形尺寸", _drawing_dimensions(payload)),
        ("轴承", _spec_text(payload, "轴承系统")),
        ("重量", _weight_text(payload)),
    )
    for label, value in targeted:
        if value:
            collector.add(label, value)

    suppressed_labels = {
        "品牌",
        "完整型号",
        "额定电压",
        "电压范围",
        "启动电压",
        "频率",
        "1688平台风叶直径映射（外框宽度）",
        "重量",
        "标称尺寸",
        "外框宽度",
        "厚度",
        "安装孔距",
        "安装孔",
        "引线长度",
        "电机保护",
        "绝缘等级",
        "框体材质",
        "叶轮材质",
        "引线规格",
        "轴承系统",
        "气流方向",
        "旋转方向",
        "安装方向",
        "工作温度",
        "存储温度",
        "认证",
    }
    if payload.operating_points:
        suppressed_labels.update(
            {"电机功率", "转速", "风量", "最大静压", "电流", "安全电流"}
        )
    suppressed_attributes = {
        "产品别名",
        "类型",
        "工业风扇种类",
        "电压",
        "风叶材质",
        "噪声",
    }
    for label, value in _parameter_rows(payload):
        if label in suppressed_labels or label in suppressed_attributes:
            continue
        collector.add(label, value)
    return collector.rows


def _lead(text: str) -> str:
    return f'<p style="margin:0 0 13px;color:#555">{escape(text)}</p>'


def _drawing_image(url: str, alt: str) -> str:
    return (
        f'<img src="{escape(url.strip(), quote=True)}" alt="{escape(alt, quote=True)}" '
        'style="display:block;width:100%;max-width:100%;height:auto;margin:0 0 12px" />'
    )


def _dimension_rows(payload: ProductPayload) -> list[tuple[str, str]]:
    mapping = (
        ("外框宽度", "外框宽度_mm"),
        ("厚度", "厚度_mm"),
        ("安装孔距", "安装孔距_mm"),
        ("安装孔", "安装孔"),
        ("引线长度", "引线长度_mm"),
        ("安装方向", "安装方向"),
        ("气流方向", "气流方向"),
    )
    return [(label, value) for label, key in mapping if (value := _spec_text(payload, key))]


def _technical_rows(payload: ProductPayload) -> list[tuple[str, str]]:
    mapping = (
        ("框体", "框体材质"),
        ("叶轮", "叶轮材质"),
        ("引线", "引线规格"),
        ("轴承", "轴承系统"),
        ("启动电压", "启动电压_v"),
        ("工作温度", "工作温度_c"),
        ("储存温度", "存储温度_c"),
        ("规格书安全项", "认证"),
    )
    rows: list[tuple[str, str]] = []
    for label, key in mapping:
        value = _voltage_text(payload, key) if key == "启动电压_v" else _spec_text(payload, key)
        if value:
            rows.append((label, value))
    return rows


def _purchase_confirmation(payload: ProductPayload) -> str:
    items = [f"完整型号是否为{payload.model}"]
    voltage = _voltage_text(payload)
    frequency = _spec_text(payload, "频率_hz")
    if voltage and frequency:
        items.append(f"供电是否为{voltage}、{frequency}")
    dimensions = _drawing_dimensions(payload)
    if dimensions:
        items.append(f"安装空间是否匹配{dimensions}")
    hole_pitch = _spec_text(payload, "安装孔距_mm")
    mounting_hole = _spec_text(payload, "安装孔")
    if hole_pitch and mounting_hole:
        items.append(f"孔距{hole_pitch}与{mounting_hole}安装孔是否匹配")
    airflow = _spec_text(payload, "气流方向")
    if airflow:
        items.append(f"气流{airflow}是否符合安装要求")
    if {point.frequency_hz for point in payload.operating_points} == {50, 60}:
        items.append("斜杠参数按50Hz/60Hz顺序读取")
    cells = [
        '<td style="box-sizing:border-box;width:50%;padding:7px 12px;vertical-align:top">'
        '<span style="color:#ff7a1a;font-weight:bold">✓</span> '
        f"{escape(item)}</td>"
        for item in items
    ]
    rows = "".join(
        f"<tr>{''.join(cells[index : index + 2])}</tr>" for index in range(0, len(cells), 2)
    )
    return (
        '<table data-geo-component="purchase-checklist" '
        'style="width:100%;border-collapse:collapse"><tbody>'
        f"{rows}</tbody></table>"
    )


def _faq(payload: ProductPayload) -> str:
    answers: list[tuple[str, str]] = []
    voltage = _voltage_text(payload)
    voltage_range = _voltage_text(payload, "电压范围_v")
    product_name = _product_name(payload) or "风扇"
    if voltage:
        nominal = voltage.split("-", 1)[0]
        answers.append(
            (
                f"这是{nominal}{product_name}吗？",
                f"是。规格书额定电压为{voltage}"
                + (f"，工作电压范围为{voltage_range}。" if voltage_range else "。"),
            )
        )
    else:
        answers.append(
            (
                "如何确认型号？",
                f"请核对品牌 {payload.brand} 和完整型号 {payload.model}，不要按相近后缀替代。",
            )
        )
    if {point.frequency_hz for point in payload.operating_points} == {50, 60}:
        answers.append(
            (
                "为什么功率、转速和风量有两组数值？",
                "斜杠前对应50Hz，斜杠后对应60Hz；这是同一型号的两种频率工况，不是两个SKU。",
            )
        )
    platform_width = _spec_text(payload, "风叶直径_m")
    frame_width = _spec_text(payload, "外框宽度_mm")
    if platform_width and frame_width:
        answers.append(
            (
                f"1688中的{platform_width}是什么意思？",
                f"它对应规格书尺寸图中的{frame_width}外框标称尺寸；详情不把它误写成单独测得的叶轮直径。",
            )
        )
    airflow = _spec_text(payload, "气流方向")
    if airflow:
        answers.append(
            (
                "气流方向怎么判断？",
                f"规格书注明气流{airflow}，安装前需结合设备风道确认方向。",
            )
        )
    bearing = _spec_text(payload, "轴承系统")
    frame = _spec_text(payload, "框体材质")
    impeller = _spec_text(payload, "叶轮材质")
    materials = [value for value in (bearing, frame, impeller) if value]
    if materials:
        answers.append(("轴承和材质是什么？", f"采用{'、'.join(materials)}。"))
    return "".join(
        '<div data-geo-component="faq-card" style="box-sizing:border-box;margin:9px 0;'
        'padding:12px 14px;border-left:4px solid #ff7a1a;background:#fff7ef">'
        f'<b style="display:block;margin-bottom:3px;color:#443327">{escape(question)}</b>'
        f"{escape(answer)}</div>"
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
    product_name = _product_name(payload)
    voltage = _voltage_text(payload)
    frequency = _spec_text(payload, "频率_hz")
    dimensions = _drawing_dimensions(payload)
    bearing = _spec_text(payload, "轴承系统")
    frame = _spec_text(payload, "框体材质")
    impeller = _spec_text(payload, "叶轮材质")
    if voltage and frequency and product_name:
        identity = f"这是一款{voltage}、{frequency}{product_name}"
    else:
        identity = f"这是 {prefix}{(' ' + product_name) if product_name else ''}"
    if dimensions:
        identity += f"，规格书外形尺寸为{dimensions}"
    material_summary = [value for value in (bearing, frame, impeller) if value]
    if material_summary:
        identity += f"，采用{'、'.join(material_summary)}"
    identity += "。"
    brand_line = _brand_display(payload)
    if product_name:
        brand_line += f"｜{product_name}"
    hero = (
        '<div data-geo-section="entity-answer" style="box-sizing:border-box;padding:30px 28px 26px;'
        'background-color:#073a70;background:linear-gradient(135deg,#073a70,#0a5da4);color:#fff">'
        f'<div style="font-size:14px;letter-spacing:.6px;opacity:.9">{escape(brand_line)}</div>'
        f'<h2 style="margin:7px 0 10px;font-size:25px;line-height:1.35;color:#fff">'
        f"{escape(payload.model)} 是什么规格？</h2>"
        f'<p style="margin:0;font-size:15px">{escape(identity)}</p></div>'
    )
    quick_cards = _quick_cards(payload)
    dimension_rows = _dimension_rows(payload)
    technical_rows = _technical_rows(payload)
    product_images = _product_image_grid(prefix, image_urls, image_roles)
    sections = [hero]
    if quick_cards:
        sections.append(
            '<div data-geo-section="quick-facts" style="box-sizing:border-box;'
            f'background:#d7e2ec;border-bottom:1px solid #d7e2ec">{quick_cards}</div>'
        )
    sections.append(
        _section(
            "core-parameters",
            "一眼确认：型号与关键参数",
            _lead("采购时先核对完整型号、额定电压、频率和尺寸。斜杠前后分别对应50Hz与60Hz。")
            + _paired_table(_core_rows(payload)),
        )
    )
    if payload.operating_points:
        sections.append(
            _section(
                "operating-points",
                "50Hz / 60Hz 性能对照",
                _operating_point_table(payload),
                alternate=True,
            )
        )
    sections.append(_section("product-images", "实物与铭牌核对", product_images))
    dimension_body = _drawing_image(drawing_url, f"{prefix} 规格书尺寸图")
    if dimension_rows:
        dimension_body += _paired_table(dimension_rows)
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
                "材质、电气与环境条件",
                _paired_table(technical_rows),
            )
        )
    sections.append(
        _section(
            "purchase-confirmation",
            "采购前请确认",
            _purchase_confirmation(payload),
            alternate=True,
        )
    )
    sections.append(_section("faq", "常见问题 FAQ", _faq(payload)))
    company_images = "".join(
        f'<img src="{escape(url, quote=True)}" '
        f'alt="{escape(f"{active_policy.company_heading} {index}", quote=True)}" '
        'style="display:block;width:100%;max-width:100%;height:auto;margin:0 0 12px" />'
        for index, url in enumerate(active_policy.company_image_urls, start=1)
    )
    sections.append(
        '<div data-geo-section="company" style="box-sizing:border-box;padding:25px 0 0;'
        'background:#fff">'
        '<div style="box-sizing:border-box;padding:0 25px 18px;text-align:center">'
        f"{_heading(active_policy.company_heading)}"
        '<p style="margin:0;color:#666">以下6张公司介绍图片按你提供的原始顺序固定放在详情最末尾。</p>'
        f"</div>{company_images}</div>"
    )
    html = (
        f'<div style="width:100%;max-width:{active_policy.editor_width_px}px;margin:0 auto;'
        'box-sizing:border-box;font-family:Arial,\'Microsoft YaHei\',sans-serif;'
        'color:#222;background:#fff;line-height:1.75;font-size:14px">'
        + "".join(sections)
        + "</div>"
    )
    return RenderedDetail(
        html=html,
        image_sources=tuple([*image_urls, drawing_url, *active_policy.company_image_urls]),
    )
