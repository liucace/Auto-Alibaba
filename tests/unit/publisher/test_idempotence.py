import inspect

from app.publisher.playwright_port import Playwright1688Port, media_is_current, value_matches


def test_exact_values_are_skipped_on_resume() -> None:
    assert value_matches("400", "400")
    assert not value_matches("", "400")


def test_platform_material_label_matches_pp_value() -> None:
    assert value_matches("ABS塑料 PP塑料", "PP塑料", contains=True)


def test_media_reuse_requires_matching_nonempty_fingerprint() -> None:
    assert media_is_current("abc", "abc")
    assert not media_is_current("", "abc")
    assert not media_is_current("old", "new")


def test_connect_replaces_tagged_page_when_media_changed() -> None:
    source = inspect.getsource(Playwright1688Port.connect)

    assert "await candidate.close" in source
    assert "media_is_current" in source
    assert "media_fingerprint" in source


def test_main_upload_persists_media_fingerprint_after_urls_are_ready() -> None:
    source = inspect.getsource(Playwright1688Port.upload_main_images)

    assert "sessionStorage.setItem" in source
    assert "self.media_fingerprint" in source
