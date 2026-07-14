from app.publisher import playwright_port


def test_picker_no_longer_waits_for_configured_ebm_album_names() -> None:
    assert not hasattr(playwright_port, "_wait_for_album_name")
