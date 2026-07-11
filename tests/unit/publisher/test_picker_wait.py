import pytest

from app.publisher.playwright_port import _wait_for_picker_frame


class FakeFrame:
    def __init__(self, url: str) -> None:
        self.url = url


class DelayedFramesPage:
    def __init__(self) -> None:
        self.reads = 0

    @property
    def frames(self):
        self.reads += 1
        if self.reads < 4:
            return [FakeFrame("about:blank")]
        return [FakeFrame("https://picman.1688.com/album/picman/picker.htm")]


@pytest.mark.asyncio
async def test_picker_waits_for_delayed_frame() -> None:
    page = DelayedFramesPage()

    frame = await _wait_for_picker_frame(page, timeout_seconds=0.2, poll_seconds=0.001)

    assert "picman.1688.com" in frame.url
    assert page.reads >= 4
