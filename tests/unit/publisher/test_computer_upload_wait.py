import pytest

from app.publisher.playwright_port import _activate_computer_upload


class DelayedComputerTab:
    def __init__(self, picker: "DelayedUploadPicker") -> None:
        self.picker = picker

    @property
    def first(self) -> "DelayedComputerTab":
        return self

    async def count(self) -> int:
        self.picker.tab_reads += 1
        return 1 if self.picker.tab_reads >= 3 else 0

    async def is_visible(self) -> bool:
        return True

    async def click(self, *, timeout: int) -> None:
        assert timeout == 5_000
        self.picker.clicked = True


class DelayedFileInput:
    def __init__(self, picker: "DelayedUploadPicker") -> None:
        self.picker = picker

    @property
    def last(self) -> "DelayedFileInput":
        return self

    async def count(self) -> int:
        return 1 if self.picker.clicked else 0

    async def wait_for(self, **_: object) -> None:
        raise AssertionError("file input cannot attach before the delayed tab is clicked")


class DelayedUploadPicker:
    def __init__(self) -> None:
        self.tab_reads = 0
        self.clicked = False
        self.tab = DelayedComputerTab(self)
        self.file_input = DelayedFileInput(self)

    def get_by_text(self, _: str, *, exact: bool) -> DelayedComputerTab:
        assert exact is True
        return self.tab

    def locator(self, selector: str) -> DelayedFileInput:
        assert selector == 'input[type="file"]'
        return self.file_input


@pytest.mark.asyncio
async def test_computer_upload_waits_for_delayed_tab_before_returning_input() -> None:
    picker = DelayedUploadPicker()

    result = await _activate_computer_upload(
        picker,
        timeout_seconds=0.2,
        poll_seconds=0.001,
    )

    assert picker.tab_reads >= 3
    assert picker.clicked is True
    assert result is picker.file_input
