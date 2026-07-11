import pytest

from app.publisher.playwright_port import _wait_for_album_name


@pytest.mark.asyncio
async def test_album_waits_until_async_options_are_loaded() -> None:
    reads = 0

    async def read_options() -> list[str]:
        nonlocal reads
        reads += 1
        return ["默认相册"] if reads < 4 else ["默认相册", "ebm(L)"]

    chosen = await _wait_for_album_name(
        read_options,
        ("ebm(L)", "ebm(LCC)"),
        timeout_seconds=0.2,
        poll_seconds=0.001,
    )

    assert chosen == "ebm(L)"
    assert reads >= 4
