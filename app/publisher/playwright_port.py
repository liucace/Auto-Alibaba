import asyncio
from pathlib import Path
from typing import Any

from playwright.async_api import Browser, Page, Playwright, async_playwright

from app.domain.errors import ManualReviewRequired
from app.domain.models import ProductPayload
from app.publisher.form_plan import build_form_plan
from app.publisher.quality import parse_quality_check

SAVE_DRAFT_BUTTON = "#saveDraftButton"

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


def normalize_main_image_urls(raw_urls: list[str]) -> list[str]:
    unique: list[str] = []
    for raw in raw_urls:
        url = raw.replace(".summ.jpg", ".jpg")
        if url not in unique:
            unique.append(url)
    return unique[-4:]


class Playwright1688Port:
    def __init__(
        self,
        page: Page,
        *,
        albums: tuple[str, ...] = ("ebm(L)", "ebm(LCC)"),
        runtime: Playwright | None = None,
        browser: Browser | None = None,
    ) -> None:
        self.page = page
        self.albums = albums
        self._runtime = runtime
        self._browser = browser

    @classmethod
    async def connect(
        cls,
        *,
        cdp_url: str,
        category_url: str,
        albums: tuple[str, ...] = ("ebm(L)", "ebm(LCC)"),
    ) -> "Playwright1688Port":
        runtime = await async_playwright().start()
        browser = await runtime.chromium.connect_over_cdp(cdp_url)
        if not browser.contexts:
            await runtime.stop()
            raise ManualReviewRequired("Chrome 9223 has no browser context")
        page = await browser.contexts[0].new_page()
        await page.goto(category_url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(1_000)
        if "offer-new.1688.com/industry/publish.htm" not in page.url:
            raise ManualReviewRequired(f"unexpected page after navigation: {page.url}")
        return cls(page, albums=albums, runtime=runtime, browser=browser)

    async def upload_main_images(self, paths: tuple[Path, ...]) -> list[str]:
        if len(paths) != 4:
            raise ManualReviewRequired("exactly four main images are required")
        await self.page.get_by_text("添加图片", exact=True).first.click(timeout=5_000)
        picker = None
        for _ in range(50):
            picker = next(
                (frame for frame in self.page.frames if "picman.1688.com" in frame.url),
                None,
            )
            if picker is not None:
                break
            await asyncio.sleep(0.1)
        if picker is None:
            raise ManualReviewRequired("1688 image picker frame did not open")
        await picker.get_by_text("我的电脑", exact=True).click(timeout=5_000)
        album_select = picker.locator("select:visible").last
        available = await album_select.locator("option").all_text_contents()
        chosen = next(
            (album for album in self.albums if any(text.strip() == album for text in available)),
            None,
        )
        if chosen is None:
            raise ManualReviewRequired(f"no configured image album is available: {self.albums}")
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
        await self.page.wait_for_timeout(800)
        module = self.page.locator("#guid-primaryPicture")
        raw_urls = await module.locator("img").evaluate_all(
            "els => els.map(el => el.src).filter(src => src.includes('cbu01.alicdn.com/img/ibank/'))"
        )
        urls = normalize_main_image_urls(list(raw_urls))
        if len(urls) != 4:
            raise ManualReviewRequired(f"expected four hosted main images, got {len(urls)}")
        return urls

    async def fill_product(self, payload: ProductPayload) -> None:
        plan = build_form_plan(payload)
        await self.page.locator('input[placeholder^="建议使用通俗的产品名称"]').fill(plan.title)
        attributes = self.page.locator('input[placeholder="如无合适选项可直接输入填写"]')
        await attributes.nth(0).fill(plan.attribute_values[0])
        await self.page.get_by_role("option", name=plan.attribute_values[0], exact=True).click(
            timeout=3_000
        )
        await attributes.nth(2).fill("PP塑料")
        material = self.page.get_by_role("option").filter(has_text="PP塑料")
        if await material.count():
            await material.first.click(timeout=3_000)
        for index in (1, 3, 4, 5, 6, 8):
            value = plan.attribute_values[index]
            if not value:
                continue
            field = attributes.nth(index)
            await field.click()
            await field.fill("")
            await self.page.keyboard.type(value)
            await self.page.keyboard.press("Tab")

        cells = self.page.locator(".ind-table-antd-input-box")
        if await cells.count() < 7:
            raise ManualReviewRequired("product specification table is not ready")
        for index, value in enumerate(plan.spec_values):
            await cells.nth(index).click()
            focused = self.page.locator("input:focus")
            await focused.fill(value)
            await focused.press("Tab")

        price = self.page.locator('#guid-priceRange input[placeholder="请输入"]:visible')
        await price.nth(0).fill(plan.sales_values[0])
        await price.nth(0).press("Tab")
        await price.nth(1).fill(plan.sales_values[1])
        await price.nth(1).press("Tab")
        sku = self.page.locator('#guid-skuTable input[placeholder="请输入"]:visible')
        await sku.nth(0).fill(plan.sales_values[2])
        await sku.nth(0).press("Tab")
        await sku.nth(1).fill(plan.sales_values[3])
        await sku.nth(1).press("Tab")

        delivery = self.page.locator("#guid-buyerProtection .ant-select-selector").last
        await delivery.click(force=True)
        await (
            self.page.locator(".ant-select-item-option-content:visible")
            .filter(has_text=plan.delivery_time)
            .last.click(timeout=3_000)
        )

        freight_module = self.page.locator("#guid-freight")
        selected = freight_module.locator(".ant-select-selection-item").last
        if (await selected.inner_text()).strip() != plan.shipping_template:
            await freight_module.locator(".ant-select-selector").last.click(force=True)
            await (
                self.page.locator(".ant-select-item-option-content:visible")
                .filter(has_text=plan.shipping_template)
                .last.click(timeout=3_000)
            )

        package = self.page.locator('#guid-officialLogistics input[placeholder="请输入"]:visible')
        if await package.count() != 4:
            raise ManualReviewRequired("package dimension inputs are not ready")
        for index, value in enumerate(plan.package_values):
            field = package.nth(index)
            await field.click()
            await field.fill("")
            await self.page.keyboard.type(value)
            await self.page.keyboard.press("Tab")

    async def inject_detail(self, html: str) -> None:
        result: dict[str, Any] = await self.page.evaluate(DETAIL_SYNC_SCRIPT, html)
        if not result.get("ok") or result.get("imageCount") != 4:
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
