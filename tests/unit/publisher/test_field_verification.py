import pytest

from app.domain.errors import ManualReviewRequired
from app.publisher.playwright_port import _fill_and_verify


class FakeField:
    def __init__(self, *, clear_after_blurs: int = 0) -> None:
        self.value = ""
        self.clear_after_blurs = clear_after_blurs
        self.fills = 0

    async def click(self) -> None:
        return None

    async def fill(self, value: str) -> None:
        self.value = value
        if value:
            self.fills += 1

    async def press(self, key: str) -> None:
        assert key == "Tab"
        if self.clear_after_blurs > 0:
            self.clear_after_blurs -= 1
            self.value = ""

    async def input_value(self) -> str:
        return self.value


@pytest.mark.asyncio
async def test_fill_and_verify_accepts_persisted_value() -> None:
    field = FakeField()

    await _fill_and_verify(field, "39850", label="package weight")

    assert field.value == "39850"
    assert field.fills == 1


@pytest.mark.asyncio
async def test_fill_and_verify_retries_one_cleared_value() -> None:
    field = FakeField(clear_after_blurs=1)

    await _fill_and_verify(field, "39850", label="package weight")

    assert field.value == "39850"
    assert field.fills == 2


@pytest.mark.asyncio
async def test_fill_and_verify_rejects_repeated_mismatch() -> None:
    field = FakeField(clear_after_blurs=2)

    with pytest.raises(ManualReviewRequired, match="package weight"):
        await _fill_and_verify(field, "39850", label="package weight")
