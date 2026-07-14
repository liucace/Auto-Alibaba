from app.products.detail_policy import load_detail_policy


def test_detail_policy_has_approved_sections_and_fixed_company_tail() -> None:
    policy = load_detail_policy()

    assert policy.editor_width_px == 790
    assert policy.current_product_image_count == 4
    assert policy.company_heading == "公司介绍与服务能力"
    assert len(policy.company_image_urls) == 6
    assert len(set(policy.company_image_urls)) == 6
    assert policy.sections[-1] == "company"
    assert policy.company_image_urls[0].endswith("?__r__=1693301896729")
    assert "O1CN01ZNKz0m1fBqloyuUox" in policy.company_image_urls[-1]
