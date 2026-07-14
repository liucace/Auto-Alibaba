import pytest

from app.domain.errors import ManualReviewRequired
from app.publisher.quality import parse_quality_check


def _html(sources: tuple[str, ...]) -> str:
    return "".join(f'<img src="{source}">' for source in sources)


def test_quality_parser_requires_exact_ordered_image_manifest() -> None:
    expected = tuple(f"https://example.com/{index}.jpg" for index in range(11))

    result = parse_quality_check(
        ui_text="错误(0)\n待优化(2)",
        response={
            "data": {"data": {"qualityInfos": [{"adviceMessages": [{"title": "买家保障"}]}]}}
        },
        form_values={"description": {"detailList": [{"content": _html(expected)}]}},
        expected_image_sources=expected,
    )

    assert result == {"errors": 0, "advice": ["买家保障"], "error_details": []}


def test_quality_parser_rejects_reordered_company_tail() -> None:
    expected = tuple(f"https://example.com/{index}.jpg" for index in range(11))
    actual = (*expected[:-2], expected[-1], expected[-2])

    with pytest.raises(ManualReviewRequired, match="manifest"):
        parse_quality_check(
            ui_text="错误(0)",
            response={"data": {"data": {"qualityInfos": []}}},
            form_values={"description": {"detailList": [{"content": _html(actual)}]}},
            expected_image_sources=expected,
        )


def test_quality_parser_extracts_blocking_error_details_separately_from_advice() -> None:
    expected = tuple(f"https://example.com/{index}.jpg" for index in range(11))
    result = parse_quality_check(
        ui_text="\n".join(
            [
                "错误(1)",
                "待优化(2)",
                "基础信息",
                "已完成",
                "物流信息",
                "1个报错",
                "件重尺",
                "重量均不能为空",
                "详情信息",
                "已完成",
            ]
        ),
        response={
            "data": {"data": {"qualityInfos": [{"adviceMessages": [{"title": "买家保障"}]}]}}
        },
        form_values={"description": {"detailList": [{"content": _html(expected)}]}},
        expected_image_sources=expected,
    )

    assert result["errors"] == 1
    assert result["advice"] == ["买家保障"]
    assert result["error_details"] == [
        {"section": "物流信息", "item": "件重尺", "message": "重量均不能为空"}
    ]


def test_quality_parser_rejects_duplicate_images_even_when_count_matches() -> None:
    expected = tuple(f"https://example.com/{index}.jpg" for index in range(11))
    actual = (*expected[:-1], expected[0])

    with pytest.raises(ManualReviewRequired, match="unique"):
        parse_quality_check(
            ui_text="错误(0)\n待优化(0)",
            response={"data": {"data": {"qualityInfos": []}}},
            form_values={"description": {"detailList": [{"content": _html(actual)}]}},
            expected_image_sources=expected,
        )


def test_quality_parser_rejects_null_detail_model() -> None:
    expected = tuple(f"https://example.com/{index}.jpg" for index in range(11))

    with pytest.raises(ManualReviewRequired, match="not synchronized"):
        parse_quality_check(
            ui_text="错误(0)\n待优化(0)",
            response={"data": {"data": {"qualityInfos": []}}},
            form_values={"description": {"detailList": [{"content": "null"}]}},
            expected_image_sources=expected,
        )
