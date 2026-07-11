import re
from typing import Any

from app.domain.errors import ManualReviewRequired


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
    if len(sources) != 4 or len(set(sources)) != 4:
        raise ManualReviewRequired("description must contain four distinct images")
    advice: list[str] = []
    infos = response.get("data", {}).get("data", {}).get("qualityInfos", [])
    for info in infos:
        for message in info.get("adviceMessages", []) or []:
            title = message.get("title")
            if title:
                advice.append(str(title))
    return {"errors": int(match.group(1)), "advice": advice}
