import pytest

from app.publisher.playwright_port import _wait_for_new_detail_image_url


@pytest.mark.asyncio
async def test_wait_for_new_detail_image_url_returns_one_added_url() -> None:
    reads = 0

    async def read_urls() -> list[str]:
        nonlocal reads
        reads += 1
        if reads < 3:
            return ["https://cbu01.alicdn.com/img/ibank/existing.jpg"]
        return [
            "https://cbu01.alicdn.com/img/ibank/existing.jpg",
            "https://cbu01.alicdn.com/img/ibank/drawing.jpg",
        ]

    result = await _wait_for_new_detail_image_url(
        read_urls,
        {"https://cbu01.alicdn.com/img/ibank/existing.jpg"},
        timeout_seconds=0.2,
        poll_seconds=0.001,
    )

    assert result == "https://cbu01.alicdn.com/img/ibank/drawing.jpg"
    assert reads >= 3
