from app.domain.errors import ManualReviewRequired

MAX_1688_TITLE_LENGTH = 60
UNSUPPORTED_MARKETING_TERMS = ("全网最低", "最好", "最佳", "顶级", "绝对", "100%")


def _compact(value: str) -> str:
    return " ".join(value.split())


def _platform_length(value: str) -> int:
    return sum(1 if character.isascii() else 2 for character in value)


def validate_product_title(
    *, title: str, brand: str, model: str, product_name: str | None
) -> str:
    clean = _compact(title)
    if not clean or _platform_length(clean) > MAX_1688_TITLE_LENGTH:
        raise ManualReviewRequired("商品标题按1688加权计数必须为1到60个字符")
    if clean.casefold().count(model.casefold()) != 1:
        raise ManualReviewRequired("商品标题必须且只能包含一次完整型号")
    if brand.casefold() not in clean.casefold():
        raise ManualReviewRequired("商品标题必须包含证据确认的品牌")
    if product_name and _compact(product_name).casefold() not in clean.casefold():
        raise ManualReviewRequired("商品标题必须包含证据确认的产品名称")
    if any(term.casefold() in clean.casefold() for term in UNSUPPORTED_MARKETING_TERMS):
        raise ManualReviewRequired("商品标题包含无证据营销词")
    return clean
