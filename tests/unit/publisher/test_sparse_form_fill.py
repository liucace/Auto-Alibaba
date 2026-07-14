import asyncio
from typing import Any

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.domain.errors import ManualReviewRequired
from app.publisher.form_plan import FormField
from app.publisher.playwright_port import (
    _fill_attribute_fields,
    _fill_spec_fields,
    _spec_display_matches,
)


class FakeOption:
    def __init__(self, *, times_out: bool = False, delayed: bool = False) -> None:
        self.times_out = times_out
        self.visible = not delayed
        self.wait_calls: list[tuple[str, float]] = []
        self.clicks = 0

    @property
    def first(self) -> "FakeOption":
        return self

    async def wait_for(self, *, state: str, timeout: float) -> None:
        self.wait_calls.append((state, timeout))
        if self.times_out:
            raise PlaywrightTimeoutError("option stayed hidden")
        if not self.visible:
            await asyncio.sleep(0)
            self.visible = True

    async def click(self, *, timeout: float) -> None:
        assert self.visible
        self.clicks += 1


class FakeField:
    def __init__(
        self,
        value: str = "",
        *,
        retains_typed_value: bool = True,
        retention_delay_reads: int = 0,
    ) -> None:
        self.value = value
        self.retains_typed_value = retains_typed_value
        self.retention_delay_reads = retention_delay_reads
        self.pending_value: str | None = None
        self.input_reads = 0
        self.clicks = 0
        self.fills: list[str] = []
        self.typed: list[str] = []
        self.presses: list[str] = []

    async def input_value(self) -> str:
        self.input_reads += 1
        if self.pending_value is not None:
            if self.retention_delay_reads:
                self.retention_delay_reads -= 1
            else:
                self.value = self.pending_value
                self.pending_value = None
        return self.value

    async def click(self) -> None:
        self.clicks += 1

    async def fill(self, value: str) -> None:
        self.fills.append(value)
        if self.retains_typed_value:
            self.value = value

    async def type(self, value: str) -> None:
        self.typed.append(value)
        if self.retains_typed_value:
            if self.retention_delay_reads:
                self.pending_value = value
            else:
                self.value = value

    async def press(self, key: str) -> None:
        self.presses.append(key)


class FakeCollection:
    def __init__(self, count: int, entries: dict[int, Any]) -> None:
        self.count_value = count
        self.entries = entries
        self.nth_indices: list[int] = []

    async def count(self) -> int:
        return self.count_value

    def nth(self, index: int) -> Any:
        self.nth_indices.append(index)
        return self.entries[index]


class FakeAttributePage:
    def __init__(self, options: dict[str, FakeOption]) -> None:
        self.options = options

    def get_by_role(self, role: str, *, name: str, exact: bool) -> FakeOption:
        assert role == "option"
        assert exact is True
        return self.options[name]


class FakeCellInput:
    def __init__(self, cell: "FakeCell") -> None:
        self.cell = cell

    @property
    def first(self) -> "FakeCellInput":
        return self

    async def count(self) -> int:
        return int(self.cell.has_input)

    async def input_value(self) -> str:
        return self.cell.actual_value


class FakeCell:
    def __init__(
        self,
        page: "FakeSpecPage",
        value: str = "",
        *,
        retains_typed_value: bool = True,
        display_value: str | None = None,
        has_input: bool = True,
    ) -> None:
        self.page = page
        self.actual_value = value
        self.display_value = value if display_value is None else display_value
        self.retains_typed_value = retains_typed_value
        self.has_input = has_input
        self.clicks = 0

    async def inner_text(self) -> str:
        return self.display_value

    async def click(self) -> None:
        self.clicks += 1
        self.page.focused = FakeFocusedInput(self)

    def locator(self, selector: str) -> FakeCellInput:
        assert selector == "input"
        return FakeCellInput(self)


class FakeFocusedInput:
    def __init__(self, cell: FakeCell) -> None:
        self.cell = cell
        self.presses: list[str] = []

    async def fill(self, value: str) -> None:
        if self.cell.retains_typed_value:
            self.cell.actual_value = value
            self.cell.display_value = value

    async def press(self, key: str) -> None:
        self.presses.append(key)


class FakeSpecPage:
    def __init__(self) -> None:
        self.focused: FakeFocusedInput | None = None

    def locator(self, selector: str) -> FakeFocusedInput:
        assert selector == "input:focus"
        assert self.focused is not None
        return self.focused


@pytest.mark.asyncio
async def test_attribute_fill_waits_for_delayed_exact_option() -> None:
    field = FakeField(retention_delay_reads=2)
    option = FakeOption(delayed=True)
    fields = (FormField(index=3, label="品牌", value="SUNON"),)

    await _fill_attribute_fields(
        FakeAttributePage({"SUNON": option}),
        FakeCollection(9, {3: field}),
        fields,
        option_timeout_ms=75,
        retain_timeout_seconds=0.01,
        poll_seconds=0,
    )

    assert option.wait_calls == [("visible", 75)]
    assert option.clicks == 1
    assert field.presses == []
    assert field.input_reads >= 4


@pytest.mark.asyncio
async def test_attribute_fill_tabs_only_after_exact_option_timeout() -> None:
    field = FakeField()
    option = FakeOption(times_out=True)

    await _fill_attribute_fields(
        FakeAttributePage({"SUNON": option}),
        FakeCollection(9, {3: field}),
        (FormField(index=3, label="品牌", value="SUNON"),),
        option_timeout_ms=75,
        retain_timeout_seconds=0.01,
        poll_seconds=0,
    )

    assert option.wait_calls == [("visible", 75)]
    assert option.clicks == 0
    assert field.presses == ["Tab"]


@pytest.mark.asyncio
async def test_sparse_attribute_and_spec_fields_use_planned_indices() -> None:
    attribute_entries = {index: FakeField() for index in (0, 3, 5)}
    attribute_collection = FakeCollection(9, attribute_entries)
    attribute_fields = tuple(
        FormField(index=index, label=label, value=value)
        for index, label, value in (
            (0, "电压", "220V"),
            (3, "品牌", "SUNON"),
            (5, "类型", "轴流风扇"),
        )
    )
    options = {entry.value: FakeOption(times_out=True) for entry in attribute_fields}
    await _fill_attribute_fields(
        FakeAttributePage(options),
        attribute_collection,
        attribute_fields,
        option_timeout_ms=1,
        retain_timeout_seconds=0.01,
        poll_seconds=0,
    )

    spec_page = FakeSpecPage()
    spec_entries = {index: FakeCell(spec_page) for index in (0, 1, 3, 5)}
    spec_collection = FakeCollection(7, spec_entries)
    spec_fields = tuple(
        FormField(index=index, label=label, value=value)
        for index, label, value in (
            (0, "规格型号", "A2175-HBL"),
            (1, "电机功率_w", "45"),
            (3, "转速_rpm", "2800"),
            (5, "电流_a", "0.21"),
        )
    )
    await _fill_spec_fields(
        spec_page,
        spec_collection,
        spec_fields,
        retain_timeout_seconds=0.01,
        poll_seconds=0,
    )

    assert attribute_collection.nth_indices == [0, 3, 5]
    assert spec_collection.nth_indices == [0, 1, 3, 5]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "count"),
    (("attribute", 8), ("attribute", 10), ("spec", 6), ("spec", 8)),
)
async def test_sparse_fill_rejects_non_exact_locator_structure(kind: str, count: int) -> None:
    fields = (FormField(index=0, label="field", value="value"),)
    collection = FakeCollection(count, {})

    with pytest.raises(ManualReviewRequired, match="structure"):
        if kind == "attribute":
            await _fill_attribute_fields(
                FakeAttributePage({}),
                collection,
                fields,
                option_timeout_ms=1,
                retain_timeout_seconds=0.001,
                poll_seconds=0,
            )
        else:
            await _fill_spec_fields(
                FakeSpecPage(),
                collection,
                fields,
                retain_timeout_seconds=0.001,
                poll_seconds=0,
            )

    assert collection.nth_indices == []


@pytest.mark.asyncio
async def test_attribute_fill_raises_when_exact_value_is_not_retained() -> None:
    field = FakeField("stale", retains_typed_value=False)

    with pytest.raises(ManualReviewRequired, match="品牌"):
        await _fill_attribute_fields(
            FakeAttributePage({"SUNON": FakeOption(times_out=True)}),
            FakeCollection(9, {3: field}),
            (FormField(index=3, label="品牌", value="SUNON"),),
            option_timeout_ms=1,
            retain_timeout_seconds=0.001,
            poll_seconds=0,
        )


@pytest.mark.asyncio
async def test_spec_fill_does_not_accept_numeric_substrings_as_retained() -> None:
    page = FakeSpecPage()
    cell = FakeCell(page, "450", retains_typed_value=False, display_value="450 W")

    with pytest.raises(ManualReviewRequired, match="电机功率_w"):
        await _fill_spec_fields(
            page,
            FakeCollection(7, {1: cell}),
            (FormField(index=1, label="电机功率_w", value="45"),),
            retain_timeout_seconds=0.001,
            poll_seconds=0,
        )


@pytest.mark.asyncio
async def test_spec_fill_prefers_exact_actual_value_over_stale_display() -> None:
    page = FakeSpecPage()
    cell = FakeCell(page, "450", retains_typed_value=False, display_value="45 W")

    with pytest.raises(ManualReviewRequired, match="电机功率_w"):
        await _fill_spec_fields(
            page,
            FakeCollection(7, {1: cell}),
            (FormField(index=1, label="电机功率_w", value="45"),),
            retain_timeout_seconds=0.001,
            poll_seconds=0,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("display", ["A2175-HBL-X", "A2175-HBL-GN-REV2"])
async def test_spec_model_display_fallback_rejects_longer_model(display: str) -> None:
    page = FakeSpecPage()
    cell = FakeCell(
        page,
        retains_typed_value=False,
        display_value=display,
        has_input=False,
    )

    with pytest.raises(ManualReviewRequired, match="规格型号"):
        await _fill_spec_fields(
            page,
            FakeCollection(7, {0: cell}),
            (FormField(index=0, label="规格型号", value="A2175-HBL"),),
            retain_timeout_seconds=0.001,
            poll_seconds=0,
        )


@pytest.mark.asyncio
async def test_spec_numeric_display_fallback_accepts_declared_unit() -> None:
    page = FakeSpecPage()
    cell = FakeCell(page, display_value="45 W", has_input=False)

    await _fill_spec_fields(
        page,
        FakeCollection(7, {1: cell}),
        (FormField(index=1, label="电机功率_w", value="45"),),
        retain_timeout_seconds=0.001,
        poll_seconds=0,
    )

    assert cell.clicks == 0


def test_speed_display_accepts_1688_r_per_minute_unit() -> None:
    entry = FormField(index=3, label="转速_rpm", value="2150/2500")

    assert _spec_display_matches("2150/2500\nr/min", entry)
