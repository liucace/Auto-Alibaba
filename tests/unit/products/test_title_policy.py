import pytest

from app.domain.errors import ManualReviewRequired
from app.products.title_policy import validate_product_title


def test_accepts_approved_dp201at_title() -> None:
    title = "SUNON建准 DP201AT-2122HBL.GN 220-240V 120mm滚珠轴承交流轴流风扇"

    assert (
        validate_product_title(
            title=title,
            brand="SUNON",
            model="DP201AT-2122HBL.GN",
            product_name="交流轴流风扇",
        )
        == title
    )
    assert len(title) == 51


@pytest.mark.parametrize(
    "title, message",
    [
        ("SUNON " + "超" * 60, "60"),
        ("SUNON 220-240V 交流轴流风扇", "完整型号"),
        ("DP201AT-2122HBL.GN 交流轴流风扇", "品牌"),
        ("SUNON DP201AT-2122HBL.GN", "产品名称"),
        ("SUNON DP201AT-2122HBL.GN 全网最低交流轴流风扇", "无证据营销词"),
    ],
)
def test_rejects_unsafe_or_incomplete_title(title: str, message: str) -> None:
    with pytest.raises(ManualReviewRequired, match=message):
        validate_product_title(
            title=title,
            brand="SUNON",
            model="DP201AT-2122HBL.GN",
            product_name="交流轴流风扇",
        )


def test_normalizes_repeated_whitespace() -> None:
    assert validate_product_title(
        title="  SUNON   DP201AT-2122HBL.GN   交流轴流风扇  ",
        brand="SUNON",
        model="DP201AT-2122HBL.GN",
        product_name="交流轴流风扇",
    ) == "SUNON DP201AT-2122HBL.GN 交流轴流风扇"
