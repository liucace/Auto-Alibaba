import pytest

from app.publisher.playwright_port import Playwright1688Port


class FakeRuntime:
    def __init__(self) -> None:
        self.stopped = False

    async def stop(self) -> None:
        self.stopped = True


@pytest.mark.asyncio
async def test_disconnect_stops_playwright_without_closing_chrome() -> None:
    runtime = FakeRuntime()
    port = Playwright1688Port(object(), runtime=runtime)  # type: ignore[arg-type]

    await port.disconnect()

    assert runtime.stopped is True
