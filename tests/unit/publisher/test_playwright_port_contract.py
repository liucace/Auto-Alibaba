import inspect

from app.publisher.playwright_port import (
    DETAIL_SYNC_SCRIPT,
    SAVE_DRAFT_BUTTON,
    Playwright1688Port,
    _activate_computer_upload,
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


def test_material_attribute_only_clicks_visible_option() -> None:
    source = inspect.getsource(Playwright1688Port.fill_product)

    assert '[role="option"]:visible' in source
    assert 'attributes.nth(2).press("Tab")' in source


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
    assert "_wait_for_detail_upload" in source
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
