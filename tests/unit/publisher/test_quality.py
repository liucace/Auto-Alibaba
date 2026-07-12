import pytest

from app.domain.errors import ManualReviewRequired
from app.publisher.quality import parse_quality_check


def test_quality_parser_requires_zero_errors_and_five_detail_images() -> None:
    html = "".join(f'<img src="https://example.com/{i}.jpg">' for i in range(5))
    result = parse_quality_check(
        ui_text="错误(0)\n待优化(2)",
        response={
            "data": {"data": {"qualityInfos": [{"adviceMessages": [{"title": "买家保障"}]}]}}
        },
        form_values={"description": {"detailList": [{"content": html}]}},
    )

    assert result == {"errors": 0, "advice": ["买家保障"]}


@pytest.mark.parametrize(
    "sources",
    [
        [f"https://example.com/{index}.jpg" for index in range(4)],
        ["https://example.com/same.jpg"] * 5,
    ],
)
def test_quality_parser_rejects_fewer_than_five_or_duplicate_images(
    sources: list[str],
) -> None:
    html = "".join(f'<img src="{source}">' for source in sources)

    with pytest.raises(ManualReviewRequired, match="five distinct"):
        parse_quality_check(
            ui_text="错误(0)\n待优化(0)",
            response={"data": {"data": {"qualityInfos": []}}},
            form_values={"description": {"detailList": [{"content": html}]}},
        )


def test_quality_parser_rejects_null_detail_model() -> None:
    with pytest.raises(ManualReviewRequired):
        parse_quality_check(
            ui_text="错误(0)\n待优化(0)",
            response={"data": {"data": {"qualityInfos": []}}},
            form_values={"description": {"detailList": [{"content": "null"}]}},
        )
