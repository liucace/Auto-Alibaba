from html import escape
from typing import Any

from app.domain.errors import ManualReviewRequired
from app.domain.models import ProductPayload
from app.ingest.model_number import exact_model_match

REQUIRED_SPECIFICATION_KEYS = {
    "规格型号",
    "电压范围_v",
    "频率_hz",
    "电机功率_w",
    "风叶直径_m",
    "转速_rpm",
    "风量_m3h",
    "最大静压_pa",
    "电流_a",
    "重量_kg",
    "防护等级",
    "绝缘等级",
}


def _text(value: Any) -> str:
    return escape(str(value))


def _number(value: float) -> str:
    return f"{value:g}"


def _image(url: str, alt: str, *, margin: str = "12px 0") -> str:
    return (
        f'<p style="margin:{margin};text-align:center">'
        f'<img src="{escape(url, quote=True)}" alt="{escape(alt, quote=True)}" '
        'style="display:block;width:100%;max-width:100%;height:auto;margin:0 auto" /></p>'
    )


def _heading(title: str, *, level: int = 2) -> str:
    size = "26px" if level == 1 else "21px"
    return (
        f'<h{level} style="margin:0 0 12px;font-size:{size};line-height:1.35;'
        f'color:#0b3a70;font-weight:bold">{escape(title)}</h{level}>'
    )


def _rows(rows: list[tuple[str, str]], *, label_width: str = "25%") -> str:
    return "".join(
        "<tr>"
        f'<td style="width:{label_width};padding:11px;border:1px solid #d8d8d8;'
        f'background:#eef3f8;font-weight:bold">{escape(label)}</td>'
        f'<td style="padding:11px;border:1px solid #d8d8d8">{value}</td>'
        "</tr>"
        for label, value in rows
    )


def _table(rows: list[tuple[str, str]], *, label_width: str = "25%") -> str:
    return (
        '<table style="width:100%;border-collapse:collapse;background:#ffffff;text-align:left">'
        f"<tbody>{_rows(rows, label_width=label_width)}</tbody></table>"
    )


def _validate(
    payload: ProductPayload,
    drawing_url: str,
    image_urls: list[str],
    image_roles: list[str],
) -> None:
    all_urls = [drawing_url, *image_urls]
    if (
        len(image_urls) != 4
        or len(image_roles) != 4
        or any(not url.strip() for url in all_urls)
        or len(set(all_urls)) != 5
    ):
        raise ManualReviewRequired("GEO detail requires five distinct current-model images")
    missing = REQUIRED_SPECIFICATION_KEYS - payload.specification.keys()
    if missing:
        raise ManualReviewRequired(f"required specification values are missing: {sorted(missing)}")
    if not exact_model_match(str(payload.specification["规格型号"]), payload.model):
        raise ManualReviewRequired("detail specification model does not match payload model")


def render_geo_detail(
    *,
    payload: ProductPayload,
    drawing_url: str,
    image_urls: list[str],
    image_roles: list[str],
) -> str:
    _validate(payload, drawing_url, image_urls, image_roles)
    spec = payload.specification
    model = payload.model
    brand = payload.brand
    prefix = f"{brand} {model}"
    power = _text(spec["电机功率_w"])
    speed = _text(spec["转速_rpm"])
    airflow = f"{float(spec['风量_m3h']):,.0f}"
    pressure = _text(spec["最大静压_pa"])
    current = _text(spec["电流_a"])
    diameter_mm = _number(float(spec["风叶直径_m"]) * 1000)
    weight = _number(float(spec["重量_kg"]))
    length_mm = _number(payload.package.length_cm * 10)
    width_mm = _number(payload.package.width_cm * 10)
    height_mm = _number(payload.package.height_cm * 10)
    dimensions = f"{length_mm} × {width_mm} × {height_mm}mm"
    voltage_range = _text(spec["电压范围_v"])
    frequency = _text(spec["频率_hz"])
    protection = _text(spec["防护等级"])
    insulation = _text(spec["绝缘等级"])
    roles = [f"{prefix} {role}" for role in image_roles]

    core_rows = [
        ("品牌", escape(brand)),
        ("完整型号", escape(model)),
        ("产品类型", "三相 EC 轴流工业风扇 / AxiBlade S 系列"),
        ("额定电压", f"400V，适用范围 {voltage_range}VAC"),
        ("频率", f"{frequency}Hz"),
        ("输入功率", f"{power}W"),
        ("额定转速", f"{speed}rpm"),
        ("0Pa 风量", f"{airflow}m³/h（自由送风点）"),
        ("最大静压", f"{pressure}Pa"),
        ("电流", f"{current}A"),
        ("规格尺寸", f"{diameter_mm}mm"),
        ("叶片", "5 片 PP 塑料叶片"),
        ("防护 / 绝缘", f"{protection} / {insulation}"),
        ("外形尺寸", dimensions),
        ("重量", f"{weight}kg"),
    ]

    return f"""<div style="font-family:arial,microsoft yahei,sans-serif;color:#222222;background:#ffffff;line-height:1.75;font-size:14px">
<section data-geo-section="dimension-drawing" style="padding:20px 16px;border-bottom:4px solid #0b3a70">
{_heading("产品尺寸图", level=1)}
{_image(drawing_url, f"{prefix} 产品尺寸图 外形{dimensions}", margin="0")}
</section>
<section data-geo-section="application-scenes" style="padding:18px 16px;background:#f6f8fb">
{_heading("场景使用", level=1)}
{_image(image_urls[0], roles[0])}
{
        _table(
            [
                ("设备散热", "适用于工业设备、控制系统和机组内部的持续送排风与热量交换。"),
                (
                    "冷却系统",
                    "可用于冷凝器、换热器等需要大风量轴流送风的系统，实际工作点应按阻力核对。",
                ),
                ("厂房通风", "适用于厂房与设备区域的空气交换，安装位置和防护方式需结合现场确认。"),
                ("工业换气", "适用于需要连续运行的工业换气场景，不以自由送风量替代实际系统工况。"),
            ]
        )
    }
</section>
<section data-geo-section="product-components" style="padding:18px 16px">
{_heading("产品组成", level=1)}
{_image(image_urls[1], roles[1])}
{_image(image_urls[2], roles[2])}
{_image(image_urls[3], roles[3], margin="12px 0 0")}
</section>
<section data-geo-section="product-definition" style="padding:20px 16px;border-top:4px solid #0b3a70">
{_heading(f"{brand} {model} 400V EC 轴流工业风扇", level=1)}
<p style="margin:0;font-size:15px;color:#333333">{escape(model)} 是 {
        escape(brand)
    } AxiBlade S 系列三相 EC 轴流风机，额定电压 400V，适用范围 {voltage_range}VAC，频率 {
        frequency
    }Hz。额定转速 {speed}rpm，输入功率 {power}W，电流 {
        current
    }A；采购时请按完整型号后缀逐项核对。</p>
</section>
<section data-geo-section="buyer-reasons" style="padding:18px 16px;background:#f6f8fb">
{_heading("买家为什么选择这款风机")}
{
        _table(
            [
                (
                    "需要大风量",
                    f"0Pa 自由送风点风量 {airflow}m³/h，最大静压 {pressure}Pa；有阻力工况应按性能曲线选型。",
                ),
                (
                    "担心选错型号",
                    f"完整型号为 {escape(model)}，可结合铭牌、电压、功率、电流和外形尺寸精确核对。",
                ),
                (
                    "需要 EC 控制",
                    "集成 EC 电机与控制电子模块，支持软启动、状态输出及 MODBUS-RTU 等功能。",
                ),
                (
                    "关注工业防护",
                    f"{protection} 防护等级、{insulation}绝缘，允许的安装方向和环境温度仍应按规格书执行。",
                ),
            ]
        )
    }
</section>
<section data-geo-section="core-parameters" style="padding:18px 16px">
{_heading("核心参数")}
{_table(core_rows)}
</section>
<section data-geo-section="application-guidance" style="padding:18px 16px;background:#f6f8fb">
{_heading("适用场景")}
{
        _table(
            [
                ("设备散热", "用于大型设备、机柜或机组的强制通风，需确认风道阻力和进出风条件。"),
                ("冷却系统", "用于冷凝器、换热器等工业冷却系统，选型时核对所需风量与静压工作点。"),
                ("厂房通风", "用于厂房或设备区换气，安装开孔、支撑结构与人员防护应按现场设计。"),
                ("工业换气", "适用于连续运行的轴流送排风需求，供电和控制接线应由专业人员完成。"),
            ]
        )
    }
</section>
<section data-geo-section="selection-reminders" style="padding:18px 16px">
{_heading("选型提醒")}
<p style="margin:0 0 8px">1. 当前型号为三相 400V，适用电压范围 {voltage_range}VAC、频率 {
        frequency
    }Hz，接线前请核对现场电源。</p>
<p style="margin:0 0 8px">2. {
        airflow
    }m³/h 是 0Pa 自由送风点数据；实际风量会随系统阻力变化，应按所需静压工作点核对性能曲线。</p>
<p style="margin:0 0 8px">3. 外形尺寸为 {dimensions}，重量 {
        weight
    }kg；安装支撑、开孔和维护空间需按图纸确认。</p>
<p style="margin:0">4. 允许轴水平或转子向下安装；转子向上安装、低温连续运行或特殊环境使用前需另行确认。</p>
</section>
<section data-geo-section="purchase-confirmation" style="padding:18px 16px;background:#f6f8fb">
{_heading("采购前请确认")}
{
        _table(
            [
                (
                    "型号是否一致",
                    f"请确认铭牌或需求单为完整型号 {escape(model)}，不同后缀不能直接视为相同配置。",
                ),
                (
                    "电源是否匹配",
                    f"本型号为三相 400V、{frequency}Hz，允许电压范围 {voltage_range}VAC。",
                ),
                ("尺寸重量", f"请确认外形 {dimensions}、重量 {weight}kg、安装开孔及现场承重。"),
                (
                    "数量与物流",
                    "请提供采购数量、交货地址和开票要求，价格、交期及运输方式以客服确认为准。",
                ),
            ],
            label_width="28%",
        )
    }
</section>
<section data-geo-section="faq-selection" style="padding:18px 16px">
{_heading("常见问题 FAQ")}
<div style="padding:12px;border:1px solid #d8d8d8;margin-bottom:12px"><h3 style="margin:0 0 6px;font-size:16px">问：{
        escape(model)
    } 是什么风机？</h3><p style="margin:0">答：它是 {
        escape(brand)
    } AxiBlade S 系列三相 EC 轴流工业风扇，规格尺寸 {diameter_mm}mm。</p></div>
<div style="padding:12px;border:1px solid #d8d8d8;margin-bottom:12px"><h3 style="margin:0 0 6px;font-size:16px">问：电气参数是多少？</h3><p style="margin:0">答：额定电压 400V，范围 {
        voltage_range
    }VAC，{frequency}Hz，{power}W，{current}A，额定转速 {speed}rpm。</p></div>
<div style="padding:12px;border:1px solid #d8d8d8;margin-bottom:12px"><h3 style="margin:0 0 6px;font-size:16px">问：风量和静压是多少？</h3><p style="margin:0">答：0Pa 自由送风点风量 {
        airflow
    }m³/h，最大静压 {pressure}Pa；中间工作点请按性能曲线核对。</p></div>
<div style="padding:12px;border:1px solid #d8d8d8;margin-bottom:12px"><h3 style="margin:0 0 6px;font-size:16px">问：尺寸和重量是多少？</h3><p style="margin:0">答：外形尺寸 {
        dimensions
    }，重量 {weight}kg，安装前请同时核对产品图纸。</p></div>
<div style="padding:12px;border:1px solid #d8d8d8"><h3 style="margin:0 0 6px;font-size:16px">问：下单前需要确认什么？</h3><p style="margin:0">答：请确认完整型号、电源、所需风量静压、安装方向、尺寸重量、数量和交货地址。</p></div>
<div style="padding:16px;margin-top:16px;background:#0b3a70;color:#ffffff"><p style="margin:0;font-size:15px"><strong>一句话选型：</strong>{
        escape(model)
    } 是一款 400V 三相 EC 轴流风机，{diameter_mm}mm 规格，{speed}rpm，最大 {power}W / {
        current
    }A，0Pa 风量 {airflow}m³/h。</p></div>
</section>
</div>"""
