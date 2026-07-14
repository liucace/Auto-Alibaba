import asyncio
import re
from collections.abc import Awaitable, Callable
from functools import partial
from pathlib import Path
from typing import Any, Literal, cast

from playwright.async_api import (
    Browser,
    Page,
    Playwright,
    async_playwright,
)
from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
)

from app.domain.errors import ManualReviewRequired
from app.domain.models import ProductPayload
from app.ingest.model_number import normalize_model
from app.publisher.album_policy import choose_brand_album, next_brand_album
from app.publisher.form_plan import FormField, build_form_plan
from app.publisher.quality import parse_quality_check

SAVE_DRAFT_BUTTON = "#saveDraftButton"
MEDIA_FINGERPRINT_KEY = "1688-uploader:media-fingerprint"
DETAIL_SELECTION_PATTERN = re.compile(r"要插入的图片\(1/\d+\)")
ATTRIBUTE_OPTION_TIMEOUT_MS = 500
FIELD_RETAIN_TIMEOUT_SECONDS = 0.5
FIELD_RETAIN_POLL_SECONDS = 0.05
ATTRIBUTE_FIELD_COUNT = 9
SPEC_FIELD_COUNT = 7
ALBUM_CAPACITY_MESSAGES = ("当前相册已满", "相册容量不足", "图片空间不足", "相册已满")
SPEC_DISPLAY_UNITS: dict[str, tuple[str, ...]] = {
    "电机功率_w": ("W",),
    "风叶直径_m": ("m",),
    "转速_rpm": ("rpm", "r/min"),
    "风量_m3h": ("m³/h", "m3/h", "m³h", "m3h"),
    "电流_a": ("A",),
    "重量_kg": ("kg",),
}

DETAIL_SYNC_SCRIPT = r"""
(html) => {
  const tiny = window.tinymce || window.tinyMCE;
  const editor = tiny?.activeEditor || tiny?.editors?.[0];
  if (!editor) return {ok: false, reason: "tinymce missing"};
  editor.setContent(html);
  if (editor.onChange?.dispatch) editor.onChange.dispatch(editor);
  if (typeof editor.save === "function") editor.save();

  const root = document.querySelector("#guid-description");
  const nodes = root ? [root, ...root.querySelectorAll("*")] : [];
  const seen = new Set();
  for (const element of nodes) {
    for (const key of Object.keys(element)) {
      if (!key.startsWith("__reactFiber$") && !key.startsWith("__reactInternalInstance$")) continue;
      for (let fiber = element[key], depth = 0; fiber && depth < 20; fiber = fiber.return, depth += 1) {
        const instance = fiber.stateNode;
        if (!instance || seen.has(instance)) continue;
        seen.add(instance);
        if (typeof instance.updateModelValue === "function") {
          instance.updateModelValue(html);
          return {
            ok: true,
            editorLength: editor.getContent().length,
            textareaLength: document.getElementById(editor.id)?.value?.length || 0,
            imageCount: (editor.getContent().match(/<img\b/gi) || []).length,
          };
        }
      }
    }
  }
  return {ok: false, reason: "updateModelValue missing"};
}
"""


def normalize_hosted_image_urls(raw_urls: list[str]) -> list[str]:
    unique: list[str] = []
    for raw in raw_urls:
        url = raw.replace(".summ.jpg", ".jpg")
        if "cbu01.alicdn.com/" in url and url not in unique:
            unique.append(url)
    return unique


def normalize_main_image_urls(raw_urls: list[str]) -> list[str]:
    unique = normalize_hosted_image_urls(raw_urls)
    return unique[-4:]


def build_session_tag(model: str) -> str:
    return f"1688-uploader:{normalize_model(model)}"


def value_matches(current: str, desired: str, *, contains: bool = False) -> bool:
    current_value = " ".join(current.split())
    desired_value = " ".join(desired.split())
    return desired_value in current_value if contains else current_value == desired_value


def media_is_current(current: str | None, expected: str) -> bool:
    return bool(expected) and current == expected


def upload_capacity_exhausted(body_text: str) -> bool:
    return any(message in body_text for message in ALBUM_CAPACITY_MESSAGES)


UploadState = Literal["ready", "full"]


async def _upload_with_brand_album(
    *,
    brand: str,
    read_names: Callable[[], Awaitable[list[str]]],
    select_name: Callable[[str], Awaitable[None]],
    create_name: Callable[[str], Awaitable[None]],
    upload_once: Callable[[], Awaitable[UploadState]],
) -> None:
    names = [name.strip() for name in await read_names()]
    choice = choose_brand_album(brand, names)
    if choice.create:
        await create_name(choice.name)
        names.append(choice.name)
    await select_name(choice.name)
    if await upload_once() == "ready":
        return

    rollover_name = next_brand_album(brand, names)
    await create_name(rollover_name)
    await select_name(rollover_name)
    if await upload_once() != "ready":
        raise ManualReviewRequired(
            f"new brand album is unavailable or full after one retry: {rollover_name}"
        )


async def _fill_and_verify(field: Any, value: str, *, label: str, retries: int = 1) -> None:
    for _ in range(retries + 1):
        await field.click()
        await field.fill("")
        await field.fill(value)
        await field.press("Tab")
        await asyncio.sleep(0)
        if value_matches(await field.input_value(), value):
            return
    raise ManualReviewRequired(f"field did not retain expected value: {label}")


async def _wait_for_condition(
    condition: Callable[[], Awaitable[bool]],
    *,
    timeout_seconds: float,
    poll_seconds: float,
) -> bool:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    while True:
        if await condition():
            return True
        if loop.time() >= deadline:
            return False
        await asyncio.sleep(poll_seconds)


async def _wait_for_locator_text(
    locator: Any,
    desired: str,
    *,
    timeout_seconds: float = FIELD_RETAIN_TIMEOUT_SECONDS,
    poll_seconds: float = FIELD_RETAIN_POLL_SECONDS,
) -> bool:
    async def retained() -> bool:
        return value_matches(await locator.inner_text(), desired)

    return await _wait_for_condition(
        retained,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
    )


async def _require_field_count(locator: Any, *, expected: int, label: str) -> None:
    available = await locator.count()
    if available != expected:
        raise ManualReviewRequired(
            f"{label} structure expected {expected} fields: found {available}"
        )


async def _fill_attribute_fields(
    page: Any,
    attributes: Any,
    fields: tuple[FormField, ...],
    *,
    option_timeout_ms: float = ATTRIBUTE_OPTION_TIMEOUT_MS,
    retain_timeout_seconds: float = FIELD_RETAIN_TIMEOUT_SECONDS,
    poll_seconds: float = FIELD_RETAIN_POLL_SECONDS,
) -> None:
    await _require_field_count(
        attributes, expected=ATTRIBUTE_FIELD_COUNT, label="product attribute"
    )
    for entry in fields:
        field = attributes.nth(entry.index)
        if await field.input_value() == entry.value:
            continue
        await field.click()
        await field.fill("")
        await field.type(entry.value)
        option = page.get_by_role("option", name=entry.value, exact=True)
        try:
            await option.first.wait_for(state="visible", timeout=option_timeout_ms)
        except PlaywrightTimeoutError:
            await field.press("Tab")
        else:
            await option.first.click(timeout=option_timeout_ms)

        if not await _wait_for_condition(
            partial(_attribute_field_retains, field, entry.value),
            timeout_seconds=retain_timeout_seconds,
            poll_seconds=poll_seconds,
        ):
            raise ManualReviewRequired(f"field did not retain expected value: {entry.label}")


def _spec_display_matches(current: str, entry: FormField) -> bool:
    current_value = " ".join(current.split())
    desired_value = " ".join(entry.value.split())
    if current_value == desired_value:
        return True
    units = SPEC_DISPLAY_UNITS.get(entry.label)
    if units is None:
        return False
    unit_pattern = "|".join(re.escape(unit) for unit in units)
    return re.fullmatch(
        rf"{re.escape(desired_value)}\s*(?:{unit_pattern})",
        current_value,
        flags=re.IGNORECASE,
    ) is not None


async def _attribute_field_retains(field: Any, value: str) -> bool:
    current: str = await field.input_value()
    return current == value


async def _spec_cell_retains(cell: Any, entry: FormField) -> bool:
    inputs = cell.locator("input")
    if await inputs.count():
        current: str = await inputs.first.input_value()
        return current == entry.value
    return _spec_display_matches(await cell.inner_text(), entry)


async def _fill_spec_fields(
    page: Any,
    cells: Any,
    fields: tuple[FormField, ...],
    *,
    retain_timeout_seconds: float = FIELD_RETAIN_TIMEOUT_SECONDS,
    poll_seconds: float = FIELD_RETAIN_POLL_SECONDS,
) -> None:
    await _require_field_count(cells, expected=SPEC_FIELD_COUNT, label="product specification")
    for entry in fields:
        cell = cells.nth(entry.index)
        if await _spec_cell_retains(cell, entry):
            continue
        await cell.click()
        focused = page.locator("input:focus")
        await focused.fill(entry.value)
        await focused.press("Tab")

        if not await _wait_for_condition(
            partial(_spec_cell_retains, cell, entry),
            timeout_seconds=retain_timeout_seconds,
            poll_seconds=poll_seconds,
        ):
            raise ManualReviewRequired(f"field did not retain expected value: {entry.label}")


def detail_upload_is_ready(body_text: str) -> bool:
    return bool(DETAIL_SELECTION_PATTERN.search(body_text)) and not any(
        status in body_text for status in ("正在上传！", "准备上传！")
    )


async def _wait_for_picker_frame(
    page: Any, *, timeout_seconds: float = 20, poll_seconds: float = 0.1
) -> Any:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    while loop.time() < deadline:
        picker = next(
            (frame for frame in page.frames if "picman.1688.com" in frame.url),
            None,
        )
        if picker is not None:
            return picker
        await asyncio.sleep(poll_seconds)
    raise ManualReviewRequired("1688 image picker frame did not open")


async def _activate_computer_upload(
    picker: Any, *, timeout_seconds: float = 15, poll_seconds: float = 0.1
) -> Any:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    tab = picker.get_by_text("我的电脑", exact=True)
    file_input = picker.locator('input[type="file"]').last
    clicked = False
    while loop.time() < deadline:
        if await file_input.count():
            return file_input
        if not clicked and await tab.count() and await tab.first.is_visible():
            await tab.first.click(timeout=5_000)
            clicked = True
        await asyncio.sleep(poll_seconds)
    raise ManualReviewRequired("computer upload input did not become available")


async def _wait_for_main_image_urls(
    read_urls: Callable[[], Awaitable[list[str]]],
    *,
    timeout_seconds: float = 15,
    poll_seconds: float = 0.1,
) -> list[str]:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    while loop.time() < deadline:
        urls = normalize_main_image_urls(await read_urls())
        if len(urls) == 4:
            return urls
        await asyncio.sleep(poll_seconds)
    raise ManualReviewRequired("four hosted main image URLs did not reach the form model")


async def _wait_for_new_detail_image_url(
    read_urls: Callable[[], Awaitable[list[str]]],
    before: set[str],
    *,
    timeout_seconds: float = 20,
    poll_seconds: float = 0.1,
) -> str:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    while loop.time() < deadline:
        added = [url for url in await read_urls() if url not in before]
        if len(added) == 1:
            return added[0]
        await asyncio.sleep(poll_seconds)
    raise ManualReviewRequired("one hosted detail image URL did not reach TinyMCE")


async def _wait_for_upload_state(
    picker: Any,
    *,
    ready: Callable[[str], bool],
    timeout_seconds: float = 60,
    poll_seconds: float = 0.1,
) -> UploadState:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    body = picker.locator("body")
    while loop.time() < deadline:
        body_text = await body.inner_text()
        if upload_capacity_exhausted(body_text):
            return "full"
        if ready(body_text):
            return "ready"
        await asyncio.sleep(poll_seconds)
    raise ManualReviewRequired("image upload did not finish")


async def _wait_for_detail_upload(
    picker: Any, *, timeout_seconds: float = 60, poll_seconds: float = 0.1
) -> UploadState:
    return await _wait_for_upload_state(
        picker,
        ready=detail_upload_is_ready,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
    )


def _main_upload_is_ready(body_text: str) -> bool:
    return (
        "要插入的图片(4/4)" in body_text
        and "正在上传！" not in body_text
        and "准备上传！" not in body_text
    )


async def _create_picker_album(picker: Any, album_select: Any, name: str) -> None:
    trigger = picker.locator("a.album-create")
    dialog = picker.locator(".create:visible").last
    if not await dialog.count():
        try:
            await trigger.last.click(timeout=5_000)
        except PlaywrightTimeoutError as error:
            raise ManualReviewRequired("image picker does not expose new album creation") from error
    field = dialog.locator("input.create-field:visible").last
    private = dialog.locator("#album-manager-pri")
    confirm = dialog.locator("a.button.insert").last
    try:
        await field.fill(name, timeout=5_000)
        if await private.count() and not await private.is_checked():
            await private.check(timeout=5_000)
        await confirm.click(timeout=5_000)
    except PlaywrightTimeoutError as error:
        raise ManualReviewRequired(f"could not create brand album: {name}") from error

    async def created() -> bool:
        options = [
            text.strip() for text in await album_select.locator("option").all_text_contents()
        ]
        return name in options

    if not await _wait_for_condition(created, timeout_seconds=10, poll_seconds=0.1):
        raise ManualReviewRequired(f"new brand album did not appear in picker: {name}")


async def _upload_picker_files(
    *,
    picker: Any,
    file_input: Any,
    files: str | list[str],
    brand: str,
    ready: Callable[[str], bool],
) -> None:
    album_select = picker.locator("select:visible").last

    async def read_names() -> list[str]:
        return cast(list[str], await album_select.locator("option").all_text_contents())

    async def select_name(name: str) -> None:
        try:
            await album_select.select_option(label=name, timeout=5_000)
        except PlaywrightTimeoutError as error:
            raise ManualReviewRequired(f"brand album could not be selected: {name}") from error

    async def create_name(name: str) -> None:
        await _create_picker_album(picker, album_select, name)

    async def upload_once() -> UploadState:
        await file_input.set_input_files(files)
        return await _wait_for_upload_state(picker, ready=ready)

    await _upload_with_brand_album(
        brand=brand,
        read_names=read_names,
        select_name=select_name,
        create_name=create_name,
        upload_once=upload_once,
    )


class Playwright1688Port:
    def __init__(
        self,
        page: Page,
        *,
        brand: str,
        media_fingerprint: str | None = None,
        runtime: Playwright | None = None,
        browser: Browser | None = None,
    ) -> None:
        self.page = page
        self.brand = brand.strip()
        if not self.brand:
            raise ManualReviewRequired("product brand is required for image album selection")
        self.media_fingerprint = media_fingerprint
        self._runtime = runtime
        self._browser = browser

    @classmethod
    async def connect(
        cls,
        *,
        cdp_url: str,
        category_url: str,
        brand: str,
        session_tag: str | None = None,
        media_fingerprint: str | None = None,
    ) -> "Playwright1688Port":
        runtime = await async_playwright().start()
        browser = await runtime.chromium.connect_over_cdp(cdp_url)
        if not browser.contexts:
            await runtime.stop()
            raise ManualReviewRequired("Chrome 9223 has no browser context")
        context = browser.contexts[0]
        page = None
        if session_tag:
            for candidate in reversed(context.pages):
                if await candidate.evaluate("() => window.name") == session_tag:
                    if media_fingerprint is not None:
                        current = await candidate.evaluate(
                            "key => window.sessionStorage.getItem(key)", MEDIA_FINGERPRINT_KEY
                        )
                        if not media_is_current(current, media_fingerprint):
                            await candidate.close(run_before_unload=False)
                            continue
                    page = candidate
                    break
        if page is None:
            page = await context.new_page()
            if session_tag:
                await page.evaluate("tag => { window.name = tag; }", session_tag)
            await page.goto(category_url, wait_until="domcontentloaded", timeout=30_000)
        await page.locator('input[placeholder^="建议使用通俗的产品名称"]').wait_for(
            state="visible", timeout=20_000
        )
        if "offer-new.1688.com/industry/publish.htm" not in page.url:
            raise ManualReviewRequired(f"unexpected page after navigation: {page.url}")
        return cls(
            page,
            brand=brand,
            media_fingerprint=media_fingerprint,
            runtime=runtime,
            browser=browser,
        )

    async def _read_current_main_image_urls(self) -> list[str]:
        raw = await self.page.locator("#guid-primaryPicture img").evaluate_all(
            "els => els.map(el => el.src).filter(src => src.includes('cbu01.alicdn.com/img/ibank/'))"
        )
        return normalize_main_image_urls(list(raw))

    async def _read_detail_image_urls(self) -> list[str]:
        raw = await self.page.evaluate(
            """() => {
              const tiny = window.tinymce || window.tinyMCE;
              const editor = tiny?.activeEditor || tiny?.editors?.[0];
              if (!editor) return [];
              const container = document.createElement('div');
              container.innerHTML = editor.getContent();
              return [...container.querySelectorAll('img')].map(image => image.src);
            }"""
        )
        return normalize_hosted_image_urls(list(raw))

    async def upload_main_images(self, paths: tuple[Path, ...]) -> list[str]:
        if len(paths) != 4:
            raise ManualReviewRequired("exactly four main images are required")
        existing = await self._read_current_main_image_urls()
        if len(existing) == 4:
            if self.media_fingerprint is None:
                return existing
            current = await self.page.evaluate(
                "key => window.sessionStorage.getItem(key)", MEDIA_FINGERPRINT_KEY
            )
            if media_is_current(current, self.media_fingerprint):
                return existing
            raise ManualReviewRequired("existing main images do not match prepared media fingerprint")
        await self.page.get_by_text("添加图片", exact=True).first.click(timeout=5_000)
        picker = await _wait_for_picker_frame(self.page)
        await _activate_computer_upload(picker)
        watermark = picker.locator('input[type="checkbox"]')
        if await watermark.count() and await watermark.first.is_checked():
            await watermark.first.uncheck()
        file_input = picker.locator('input[type="file"][multiple]').last
        if not await file_input.count():
            raise ManualReviewRequired("main image multiple-file input is unavailable")
        await _upload_picker_files(
            picker=picker,
            file_input=file_input,
            files=[str(path) for path in paths],
            brand=self.brand,
            ready=_main_upload_is_ready,
        )
        insert = picker.locator("em", has_text="插入图片")
        await insert.last.click(timeout=5_000)

        async def read_urls() -> list[str]:
            return await self._read_current_main_image_urls()

        urls = await _wait_for_main_image_urls(read_urls)
        if self.media_fingerprint is not None:
            await self.page.evaluate(
                "([key, value]) => window.sessionStorage.setItem(key, value)",
                [MEDIA_FINGERPRINT_KEY, self.media_fingerprint],
            )
        return urls

    async def upload_detail_image(self, path: Path, *, existing_url: str | None = None) -> str:
        if existing_url and existing_url.startswith("https://cbu01.alicdn.com/img/ibank/"):
            return existing_url.replace(".summ.jpg", ".jpg")
        if not path.is_file() or path.stat().st_size == 0:
            raise ManualReviewRequired(f"detail image does not exist or is empty: {path}")
        before = set(await self._read_detail_image_urls())
        await self.page.locator('#guid-description a[role="button"][title="插入图片"]').click(
            timeout=5_000
        )
        picker = await _wait_for_picker_frame(self.page)
        file_input = await _activate_computer_upload(picker)
        watermark = picker.locator('input[type="checkbox"]')
        if await watermark.count() and await watermark.first.is_checked():
            await watermark.first.uncheck()
        await _upload_picker_files(
            picker=picker,
            file_input=file_input,
            files=str(path),
            brand=self.brand,
            ready=detail_upload_is_ready,
        )
        await picker.locator("em", has_text="插入图片").last.evaluate("element => element.click()")
        return await _wait_for_new_detail_image_url(self._read_detail_image_urls, before)

    async def fill_product(self, payload: ProductPayload) -> None:
        plan = build_form_plan(payload)
        attributes = self.page.locator('input[placeholder="如无合适选项可直接输入填写"]')
        cells = self.page.locator(".ind-table-antd-input-box")
        await _require_field_count(
            attributes, expected=ATTRIBUTE_FIELD_COUNT, label="product attribute"
        )
        await _require_field_count(cells, expected=SPEC_FIELD_COUNT, label="product specification")
        title_field = self.page.locator('input[placeholder^="建议使用通俗的产品名称"]')
        if await title_field.get_attribute("maxlength") != "60":
            raise ManualReviewRequired("1688 title field no longer exposes maxlength=60")
        await _fill_and_verify(title_field, plan.title, label="product title")
        await _fill_attribute_fields(self.page, attributes, plan.attribute_fields)
        await _fill_spec_fields(self.page, cells, plan.spec_fields)

        price = self.page.locator('#guid-priceRange input[placeholder="请输入"]:visible')
        await _fill_and_verify(
            price.nth(0), plan.minimum_order_quantity, label="minimum order quantity"
        )
        await _fill_and_verify(price.nth(1), plan.price, label="price")
        sku_module = self.page.locator("#guid-skuTable")
        sku_inputs = sku_module.locator('input[placeholder="请输入"]:visible')
        if await sku_inputs.count() != 2:
            raise ManualReviewRequired(
                "single-SKU table no longer exposes stock and item-code inputs"
            )
        if plan.sku.model not in " ".join((await sku_module.inner_text()).split()):
            raise ManualReviewRequired(
                "single-SKU model is not synchronized from product specification"
            )
        await _fill_and_verify(sku_inputs.nth(0), plan.sku.stock, label="stock")
        await _fill_and_verify(sku_inputs.nth(1), plan.sku.item_code, label="item code")

        delivery_module = self.page.locator("#guid-buyerProtection")
        if plan.delivery_time not in await delivery_module.inner_text():
            delivery = delivery_module.locator(".ant-select-selector").last
            await delivery.click(force=True)
            option = (
                self.page.locator(".ant-select-item-option")
                .filter(has_text=plan.delivery_time)
                .last
            )
            await option.wait_for(state="attached", timeout=5_000)
            await option.evaluate("element => element.click()")
            selected_delivery = delivery_module.locator(".ant-select-selection-item").last
            if not await _wait_for_locator_text(selected_delivery, plan.delivery_time):
                raise ManualReviewRequired("delivery time did not retain expected value")

        freight_module = self.page.locator("#guid-freight")
        selected = freight_module.locator(".ant-select-selection-item").last
        if (await selected.inner_text()).strip() != plan.shipping_template:
            for _ in range(2):
                await selected.click(force=True)
                option = (
                    self.page.locator(".ant-select-item-option")
                    .filter(has_text=plan.shipping_template)
                    .last
                )
                await option.wait_for(state="attached", timeout=5_000)
                await option.evaluate("element => element.click()")
                if await _wait_for_locator_text(selected, plan.shipping_template):
                    break
            else:
                raise ManualReviewRequired("freight template did not retain expected value")

        package = self.page.locator('#guid-officialLogistics input[placeholder="请输入"]:visible')
        if await package.count() != 4:
            raise ManualReviewRequired("package dimension inputs are not ready")
        for index, value in enumerate(plan.package_values):
            await _fill_and_verify(package.nth(index), value, label=f"package value {index + 1}")
        await self.page.wait_for_timeout(250)
        for index, value in enumerate(plan.package_values):
            field = package.nth(index)
            if not value_matches(await field.input_value(), value):
                await _fill_and_verify(field, value, label=f"package value {index + 1}")

    async def inject_detail(self, html: str, *, expected_image_count: int) -> None:
        result: dict[str, Any] = await self.page.evaluate(DETAIL_SYNC_SCRIPT, html)
        if not result.get("ok") or result.get("imageCount") != expected_image_count:
            raise ManualReviewRequired(f"detail form synchronization failed: {result}")

    async def quality_check(
        self, *, expected_image_sources: tuple[str, ...]
    ) -> dict[str, object]:
        async with self.page.expect_response(
            lambda response: "qualityCal" in response.url and response.request.method == "POST",
            timeout=20_000,
        ) as response_info:
            await self.page.evaluate("() => document.querySelector('.star-reload-btn')?.click()")
        response = await response_info.value
        response_json = await response.json()
        post_data = response.request.post_data_json
        if not isinstance(post_data, dict):
            raise ManualReviewRequired("quality request has no JSON form payload")
        ui_text = await self.page.locator("body").inner_text()
        return parse_quality_check(
            ui_text=ui_text,
            response=response_json,
            form_values=post_data.get("formValues", {}),
            expected_image_sources=expected_image_sources,
        )

    async def verify_save_boundary(self) -> None:
        button = self.page.locator(SAVE_DRAFT_BUTTON)
        if await button.count() != 1:
            raise ManualReviewRequired("save draft button is not unique")
        if (await button.evaluate("element => element.tagName")) != "A":
            raise ManualReviewRequired("save draft control is not an anchor")
        text = (await button.inner_text()).strip()
        if text != "保存草稿" or "发布" in text:
            raise ManualReviewRequired(f"unsafe save boundary text: {text}")

    async def disconnect(self) -> None:
        if self._runtime is not None:
            await self._runtime.stop()
            self._runtime = None
