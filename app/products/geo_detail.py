from html import escape

from app.domain.errors import ManualReviewRequired


def _image(url: str, alt: str) -> str:
    return (
        '<p style="margin:12px 0;text-align:center">'
        f'<img src="{escape(url, quote=True)}" alt="{escape(alt, quote=True)}" '
        'style="max-width:100%;height:auto" /></p>'
    )


def render_geo_detail(
    *,
    model: str,
    brand: str,
    summary: str,
    parameters: list[tuple[str, str]],
    image_urls: list[str],
    image_roles: list[str],
) -> str:
    if len(image_urls) != 4 or len(set(image_urls)) != 4 or len(image_roles) != 4:
        raise ManualReviewRequired("GEO detail requires four distinct current-model images")
    alts = [f"{brand} {model} {role}" for role in image_roles]
    rows = "".join(
        f'<tr><td style="padding:9px;border:1px solid #d8d8d8">{escape(name)}</td>'
        f'<td style="padding:9px;border:1px solid #d8d8d8">{escape(value)}</td></tr>'
        for name, value in parameters
    )
    return f"""<div style="font-family:arial,microsoft yahei,sans-serif;color:#222;line-height:1.75">
<section data-geo-section="entity-answer"><h1>{escape(brand)} {escape(model)}</h1><p>{escape(summary)}</p>{_image(image_urls[0], alts[0])}</section>
<section data-geo-section="product-definition"><h2>{escape(model)} 是什么产品</h2><p>{escape(summary)}，采购时请核对完整型号后缀。</p></section>
<section data-geo-section="core-parameters"><h2>核心参数</h2><table style="width:100%;border-collapse:collapse">{rows}</table>{_image(image_urls[1], alts[1])}</section>
<section data-geo-section="operating-points"><h2>性能与工况</h2><p>风量、静压、功率和电流应按当前型号规格书的同一工作点核对。</p></section>
<section data-geo-section="structure-installation"><h2>结构与安装</h2><p>安装尺寸、方向和防护要求以当前型号图纸与规格书为准。</p>{_image(image_urls[2], alts[2])}{_image(image_urls[3], alts[3])}</section>
<section data-geo-section="purchase-confirmation"><h2>采购前确认</h2><p>请确认完整型号、电压、频率、尺寸、重量和所需工作点。</p></section>
<section data-geo-section="faq"><h2>常见问题</h2><p><strong>如何避免选错？</strong> 使用完整型号 {escape(model)} 与铭牌逐项核对。</p></section>
<section data-geo-section="one-sentence-selection"><strong>一句话选型：</strong>{escape(summary)}</section>
</div>"""
