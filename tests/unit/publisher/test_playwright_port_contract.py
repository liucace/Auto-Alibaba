import inspect

from app.cli import run_product
from app.publisher.playwright_port import (
    DETAIL_SYNC_SCRIPT,
    SAVE_DRAFT_BUTTON,
    Playwright1688Port,
    _activate_computer_upload,
    _create_picker_album,
    _fill_attribute_fields,
    build_session_tag,
    normalize_hosted_image_urls,
    normalize_main_image_urls,
)


def test_detail_script_updates_editor_and_react_model() -> None:
    assert "setContent" in DETAIL_SYNC_SCRIPT
    assert "onChange.dispatch" in DETAIL_SYNC_SCRIPT
    assert "save" in DETAIL_SYNC_SCRIPT
    assert "updateModelValue" in DETAIL_SYNC_SCRIPT


def test_port_exposes_no_save_or_publish_action() -> None:
    callable_names = {
        name
        for name, value in inspect.getmembers(Playwright1688Port, callable)
        if not name.startswith("_")
    }
    assert "save" not in callable_names
    assert not any("publish" in name.lower() for name in callable_names)
    assert SAVE_DRAFT_BUTTON == "#saveDraftButton"


def test_port_uses_evidenced_brand_instead_of_ebm_album_defaults() -> None:
    constructor = inspect.signature(Playwright1688Port)
    connect = inspect.signature(Playwright1688Port.connect)
    source = inspect.getsource(Playwright1688Port)

    assert "brand" in constructor.parameters
    assert "brand" in connect.parameters
    assert "ebm(L)" not in source
    assert "ebm(LCC)" not in source


def test_run_product_passes_evidenced_brand_to_port() -> None:
    source = inspect.getsource(run_product)

    assert "brand=product.payload.brand" in source


def test_album_creation_uses_observed_picker_controls() -> None:
    source = inspect.getsource(_create_picker_album)

    assert 'locator("a.album-create")' in source
    assert 'locator(".create:visible")' in source
    assert 'locator("input.create-field:visible")' in source
    assert 'locator("#album-manager-pri")' in source
    assert 'locator("a.button.insert")' in source
    assert "新建相册" not in source


def test_main_image_urls_are_unique_and_strip_thumbnails() -> None:
    raw = [
        "https://cbu01.alicdn.com/a.summ.jpg",
        "https://cbu01.alicdn.com/a.jpg",
        "https://cbu01.alicdn.com/b.jpg",
        "https://cbu01.alicdn.com/c.jpg",
        "https://cbu01.alicdn.com/d.jpg",
    ]
    assert normalize_main_image_urls(raw) == [
        "https://cbu01.alicdn.com/a.jpg",
        "https://cbu01.alicdn.com/b.jpg",
        "https://cbu01.alicdn.com/c.jpg",
        "https://cbu01.alicdn.com/d.jpg",
    ]


def test_hosted_image_urls_are_unique_and_strip_thumbnails() -> None:
    assert normalize_hosted_image_urls(
        [
            "https://cbu01.alicdn.com/a.summ.jpg",
            "https://cbu01.alicdn.com/a.jpg",
            "https://example.com/not-hosted.jpg",
        ]
    ) == ["https://cbu01.alicdn.com/a.jpg"]


def test_freight_dropdown_clicks_visible_selection_item() -> None:
    source = inspect.getsource(Playwright1688Port.fill_product)

    assert "await selected.click(force=True)" in source
    assert 'freight_module.locator(".ant-select-selector").last.click' not in source


def test_ant_dropdown_options_can_be_selected_outside_the_viewport() -> None:
    source = inspect.getsource(Playwright1688Port.fill_product)

    assert 'wait_for(state="attached", timeout=5_000)' in source
    assert 'evaluate("element => element.click()")' in source
    assert '.ant-select-item-option-content:visible' not in source


def test_fill_product_iterates_only_sparse_form_fields() -> None:
    source = inspect.getsource(Playwright1688Port.fill_product)

    assert "_fill_attribute_fields(self.page, attributes, plan.attribute_fields)" in source
    assert "_fill_spec_fields(self.page, cells, plan.spec_fields)" in source
    assert "PP塑料" not in source
    assert "attributes.nth(0)" not in source
    assert "attributes.nth(2)" not in source


def test_fill_product_enforces_real_title_and_single_sku_contract() -> None:
    source = inspect.getsource(Playwright1688Port.fill_product)

    assert 'get_attribute("maxlength") != "60"' in source
    assert 'sku_module = self.page.locator("#guid-skuTable")' in source
    assert "await sku_inputs.count() != 2" in source
    assert "plan.sku.model not in" in source
    assert "plan.sku.stock" in source
    assert "plan.sku.item_code" in source
    assert "sales_values" not in source


def test_sparse_attribute_option_uses_bounded_visibility_wait() -> None:
    source = inspect.getsource(_fill_attribute_fields)

    assert 'get_by_role("option", name=entry.value, exact=True)' in source
    assert 'option.first.wait_for(state="visible", timeout=option_timeout_ms)' in source
    assert "except PlaywrightTimeoutError" in source
    assert "await option.first.click" in source
    assert 'await field.press("Tab")' in source


def test_session_tag_is_stable_per_model() -> None:
    assert build_session_tag(" w3g630-nu33-03 ") == "1688-uploader:W3G630-NU33-03"


def test_image_upload_reuses_existing_four_urls() -> None:
    source = inspect.getsource(Playwright1688Port.upload_main_images)

    assert "existing = await self._read_current_main_image_urls()" in source
    assert source.index("existing =") < source.index('get_by_text("添加图片"')


def test_detail_image_upload_uses_tinymce_picker_not_main_picture() -> None:
    source = inspect.getsource(Playwright1688Port.upload_detail_image)

    assert 'a[role="button"][title="插入图片"]' in source
    assert 'button[title="插入图片"]' not in source
    assert "_upload_picker_files" in source
    assert "ready=detail_upload_is_ready" in source
    assert "要插入的图片(1/1)" not in source
    assert "_read_detail_image_urls" in source
    assert "#guid-primaryPicture" not in source
    assert "element => element.click()" in source


def test_computer_upload_tab_is_only_clicked_when_visible() -> None:
    source = inspect.getsource(_activate_computer_upload)

    assert "await tab.count()" in source
    assert "await tab.first.is_visible()" in source
    assert "await tab.first.click" in source
    assert 'input[type="file"]' in source


def test_detail_injection_requires_explicit_expected_image_count() -> None:
    signature = inspect.signature(Playwright1688Port.inject_detail)
    source = inspect.getsource(Playwright1688Port.inject_detail)

    assert "expected_image_count" in signature.parameters
    assert 'result.get("imageCount") != expected_image_count' in source


def test_quality_check_requires_expected_ordered_image_sources() -> None:
    signature = inspect.signature(Playwright1688Port.quality_check)
    source = inspect.getsource(Playwright1688Port.quality_check)

    assert "expected_image_sources" in signature.parameters
    assert "expected_image_sources=expected_image_sources" in source
