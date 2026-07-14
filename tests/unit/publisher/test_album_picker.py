from collections.abc import Awaitable, Callable

import pytest

from app.domain.errors import ManualReviewRequired
from app.publisher.playwright_port import (
    _upload_with_brand_album,
    upload_capacity_exhausted,
)


@pytest.mark.parametrize("text", ["当前相册已满", "相册容量不足", "图片空间不足"])
def test_album_capacity_messages_are_detected(text: str) -> None:
    assert upload_capacity_exhausted(text)


def test_normal_upload_progress_is_not_capacity_exhaustion() -> None:
    assert not upload_capacity_exhausted("正在上传！ 要插入的图片(4/4)")


def _async_action(log: list[str], prefix: str) -> Callable[[str], Awaitable[None]]:
    async def action(value: str) -> None:
        log.append(f"{prefix}:{value}")

    return action


@pytest.mark.asyncio
async def test_album_workflow_creates_first_brand_album() -> None:
    log: list[str] = []

    async def read_names() -> list[str]:
        return []

    outcomes = iter(["ready"])

    async def upload_once() -> str:
        outcome = next(outcomes)
        log.append(f"upload:{outcome}")
        return outcome

    await _upload_with_brand_album(
        brand="SUNON",
        read_names=read_names,
        select_name=_async_action(log, "select"),
        create_name=_async_action(log, "create"),
        upload_once=upload_once,
    )

    assert log == ["create:SUNON(01)", "select:SUNON(01)", "upload:ready"]


@pytest.mark.asyncio
async def test_album_workflow_rolls_over_full_album_once() -> None:
    log: list[str] = []

    async def read_names() -> list[str]:
        return ["SUNON(01)", "SUNON(02)", "Delta(99)"]

    outcomes = iter(["full", "ready"])

    async def upload_once() -> str:
        outcome = next(outcomes)
        log.append(f"upload:{outcome}")
        return outcome

    await _upload_with_brand_album(
        brand="SUNON",
        read_names=read_names,
        select_name=_async_action(log, "select"),
        create_name=_async_action(log, "create"),
        upload_once=upload_once,
    )

    assert log == [
        "select:SUNON(02)",
        "upload:full",
        "create:SUNON(03)",
        "select:SUNON(03)",
        "upload:ready",
    ]


@pytest.mark.asyncio
async def test_album_workflow_blocks_when_new_album_is_also_full() -> None:
    log: list[str] = []

    async def read_names() -> list[str]:
        return ["SUNON(09)"]

    async def upload_once() -> str:
        log.append("upload:full")
        return "full"

    with pytest.raises(ManualReviewRequired, match=r"SUNON\(10\)"):
        await _upload_with_brand_album(
            brand="SUNON",
            read_names=read_names,
            select_name=_async_action(log, "select"),
            create_name=_async_action(log, "create"),
            upload_once=upload_once,
        )

    assert log.count("upload:full") == 2
    assert log.count("create:SUNON(10)") == 1
