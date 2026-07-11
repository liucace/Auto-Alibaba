import inspect

from app.publisher.playwright_port import (
    DETAIL_SYNC_SCRIPT,
    SAVE_DRAFT_BUTTON,
    Playwright1688Port,
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
