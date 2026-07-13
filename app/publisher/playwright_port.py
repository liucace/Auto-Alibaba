import asyncio
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from playwright.async_api import Browser, Page, Playwright, async_playwright

from app.domain.errors import ManualReviewRequired
from app.domain.models import ProductPayload
from app.ingest.model_number import normalize_model
from app.publisher.form_plan import build_form_plan
from app.publisher.quality import parse_quality_check

SAVE_DRAFT_BUTTON = "#saveDraftButton"
MEDIA_FINGERPRINT_KEY = "1688-uploader:media-fingerprint"
DETAIL_SELECTION_PATTERN = re.compile(r"要插入的图片\(1/\d+\)")

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


async def _wait_for_album_name(
    read_options: Callable[[], Awaitable[list[str]]],
    albums: tuple[str, ...],
    *,
    timeout_seconds: float = 15,
    poll_seconds: float = 0.1,
) -> str:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    while loop.time() < deadline:
        available = [text.strip() for text in await read_options()]
        chosen = next((album for album in albums if album in available), None)
        if chosen is not None:
            return chosen
        await asyncio.sleep(poll_seconds)
    raise ManualReviewRequired(f"no configured image album is available: {albums}")


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


async def _wait_for_detail_upload(
    picker: Any, *, timeout_seconds: float = 60, poll_seconds: float = 0.1
) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    body = picker.locator("body")
    while loop.time() < deadline:
        if detail_upload_is_ready(await body.inner_text()):
            return
        await asyncio.sleep(poll_seconds)
    raise ManualReviewRequired("one detail image did not finish uploading")


class Playwright1688Port:
    def __init__(
        self,
        page: Page,
        *,
        albums: tuple[str, ...] = ("ebm(L)", "ebm(LCC)"),
        media_fingerprint: str | None = None,
        runtime: Playwright | None = None,
        browser: Browser | None = None,
    ) -> None:
        self.page = page
        self.albums = albums
        self.media_fingerprint = media_fingerprint
        self._runtime = runtime
        self._browser = browser

    @classmethod
    async def connect(
        cls,
        *,
        cdp_url: str,
        category_url: str,
        albums: tuple[str, ...] = ("ebm(L)", "ebm(LCC)"),
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
            albums=albums,
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
        album_select = picker.locator("select:visible").last
        chosen = await _wait_for_album_name(
            lambda: album_select.locator("option").all_text_contents(), self.albums
        )
        await album_select.select_option(label=chosen)
        watermark = picker.locator('input[type="checkbox"]')
        if await watermark.count() and await watermark.first.is_checked():
            await watermark.first.uncheck()
        await picker.locator('input[type="file"][multiple]').set_input_files(
            [str(path) for path in paths]
        )
        await picker.wait_for_function(
            """() => document.body.innerText.includes('要插入的图片(4/4)')
              && !document.body.innerText.includes('正在上传！')
              && !document.body.innerText.includes('准备上传！')""",
            timeout=60_000,
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
        album_select = picker.locator("select:visible").last
        chosen = await _wait_for_album_name(
            lambda: album_select.locator("option").all_text_contents(), self.albums
        )
        await album_select.select_option(label=chosen)
        watermark = picker.locator('input[type="checkbox"]')
        if await watermark.count() and await watermark.first.is_checked():
            await watermark.first.uncheck()
        await file_input.set_input_files(str(path))
        await _wait_for_detail_upload(picker)
        await picker.locator("em", has_text="插入图片").last.evaluate("element => element.click()")
        return await _wait_for_new_detail_image_url(self._read_detail_image_urls, before)

    async def fill_product(self, payload: ProductPayload) -> None:
        plan = build_form_plan(payload)
        await self.page.locator('input[placeholder^="建议使用通俗的产品名称"]').fill(plan.title)
        attributes = self.page.locator('input[placeholder="如无合适选项可直接输入填写"]')
        if not value_matches(await attributes.nth(0).input_value(), plan.attribute_values[0]):
            await attributes.nth(0).fill(plan.attribute_values[0])
            await self.page.get_by_role("option", name=plan.attribute_values[0], exact=True).click(
                timeout=3_000
            )
        if not value_matches(await attributes.nth(2).input_value(), "PP塑料", contains=True):
            await attributes.nth(2).fill("PP塑料")
            material = self.page.locator('[role="option"]:visible').filter(has_text="PP塑料")
            if await material.count():
                await material.first.click(timeout=3_000)
            else:
                await attributes.nth(2).press("Tab")
        for index in (1, 3, 4, 5, 6, 8):
            value = plan.attribute_values[index]
            if not value:
                continue
            field = attributes.nth(index)
            if value_matches(await field.input_value(), value):
                continue
            await field.click()
            await field.fill("")
            await self.page.keyboard.type(value)
            await self.page.keyboard.press("Tab")

        cells = self.page.locator(".ind-table-antd-input-box")
        if await cells.count() < 7:
            raise ManualReviewRequired("product specification table is not ready")
        for index, value in enumerate(plan.spec_values):
            if value_matches(await cells.nth(index).inner_text(), value, contains=True):
                continue
            await cells.nth(index).click()
            focused = self.page.locator("input:focus")
            await focused.fill(value)
            await focused.press("Tab")

        price = self.page.locator('#guid-priceRange input[placeholder="请输入"]:visible')
        await _fill_and_verify(price.nth(0), plan.sales_values[0], label="minimum order quantity")
        await _fill_and_verify(price.nth(1), plan.sales_values[1], label="price")
        sku = self.page.locator('#guid-skuTable input[placeholder="请输入"]:visible')
        await _fill_and_verify(sku.nth(0), plan.sales_values[2], label="stock")
        await _fill_and_verify(sku.nth(1), plan.sales_values[3], label="sku model")

        delivery_module = self.page.locator("#guid-buyerProtection")
        if plan.delivery_time not in await delivery_module.inner_text():
            delivery = delivery_module.locator(".ant-select-selector").last
            await delivery.click(force=True)
            await (
                self.page.locator(".ant-select-item-option-content:visible")
                .filter(has_text=plan.delivery_time)
                .last.click(timeout=3_000)
            )

        freight_module = self.page.locator("#guid-freight")
        selected = freight_module.locator(".ant-select-selection-item").last
        if (await selected.inner_text()).strip() != plan.shipping_template:
            for _ in range(2):
                await selected.click(force=True)
                option = (
                    self.page.locator(".ant-select-item-option-content:visible")
                    .filter(has_text=plan.shipping_template)
                    .last
                )
                await option.wait_for(state="visible", timeout=5_000)
                await option.click(timeout=3_000)
                await self.page.wait_for_timeout(100)
                if value_matches(await selected.inner_text(), plan.shipping_template):
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

    async def quality_check(self) -> dict[str, object]:
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
