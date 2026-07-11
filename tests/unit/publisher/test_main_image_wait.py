import pytest

from app.publisher.playwright_port import _wait_for_main_image_urls


@pytest.mark.asyncio
async def test_main_image_urls_wait_for_react_render() -> None:
    reads = 0

    async def read_urls() -> list[str]:
        nonlocal reads
        reads += 1
        if reads < 4:
            return []
        return [f"https://cbu01.alicdn.com/{index}.jpg" for index in range(4)]

    urls = await _wait_for_main_image_urls(read_urls, timeout_seconds=0.2, poll_seconds=0.001)

    assert len(urls) == 4
    assert reads >= 4
