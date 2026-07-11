import pytest

from app.domain.errors import ManualReviewRequired
from app.publisher.quality import parse_quality_check


def test_quality_parser_requires_zero_errors_and_four_detail_images() -> None:
    html = "".join(f'<img src="https://example.com/{i}.jpg">' for i in range(4))
    result = parse_quality_check(
        ui_text="错误(0)\n待优化(2)",
        response={
            "data": {"data": {"qualityInfos": [{"adviceMessages": [{"title": "买家保障"}]}]}}
        },
        form_values={"description": {"detailList": [{"content": html}]}},
    )

    assert result == {"errors": 0, "advice": ["买家保障"]}


def test_quality_parser_rejects_null_detail_model() -> None:
    with pytest.raises(ManualReviewRequired):
        parse_quality_check(
            ui_text="错误(0)\n待优化(0)",
            response={"data": {"data": {"qualityInfos": []}}},
            form_values={"description": {"detailList": [{"content": "null"}]}},
        )
