import re
from typing import Any

from app.domain.errors import ManualReviewRequired

QUALITY_SECTIONS = {
    "主图视频",
    "商品主图",
    "基础信息",
    "销售信息",
    "服务与承诺",
    "物流信息",
    "商品资质和其他服务",
    "详情信息",
}


def _extract_error_details(ui_text: str) -> list[dict[str, str]]:
    lines = [line.strip() for line in ui_text.splitlines() if line.strip()]
    details: list[dict[str, str]] = []
    for index, line in enumerate(lines):
        if re.fullmatch(r"\d+个报错", line) is None:
            continue
        section = next(
            (candidate for candidate in reversed(lines[:index]) if candidate in QUALITY_SECTIONS),
            "未知板块",
        )
        item = lines[index + 1] if index + 1 < len(lines) else "未知项目"
        message = lines[index + 2] if index + 2 < len(lines) else "平台未提供错误说明"
        details.append({"section": section, "item": item, "message": message})
    return details


def parse_quality_check(
    *,
    ui_text: str,
    response: dict[str, Any],
    form_values: dict[str, Any],
) -> dict[str, object]:
    match = re.search(r"错误\((\d+)\)", ui_text)
    if match is None:
        raise ManualReviewRequired("quality assistant did not expose an error count")
    content = form_values.get("description", {}).get("detailList", [{}])[0].get("content")
    if not isinstance(content, str) or content == "null":
        raise ManualReviewRequired("description is not synchronized to the form model")
    sources = re.findall(r"<img\b[^>]*\bsrc=[\"']([^\"']+)", content, flags=re.I)
    if len(sources) < 5 or len(set(sources)) != len(sources):
        raise ManualReviewRequired("description must contain at least five distinct images")
    advice: list[str] = []
    infos = response.get("data", {}).get("data", {}).get("qualityInfos", [])
    for info in infos:
        for message in info.get("adviceMessages", []) or []:
            title = message.get("title")
            if title:
                advice.append(str(title))
    return {
        "errors": int(match.group(1)),
        "advice": advice,
        "error_details": _extract_error_details(ui_text),
    }
