# W3G710 Reference-Faithful Detail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the simplified four-image GEO detail with the approved reference-faithful ten-section detail, upload a cropped PDF drawing as a fifth detail image, persist the generated HTML, and refresh the current W3G710-NU31-03 1688 form without saving or publishing.

**Architecture:** Keep product facts and prepared-asset loading in `app/products`, keep browser interaction in `app/publisher/playwright_port.py`, and let the orchestrator compose the two through explicit paths and hosted URLs. A `detail_assets.json` file describes the drawing source, page, normalized crop and cached hosted URL; the loader renders the local drawing when needed, the port uploads it through TinyMCE's image picker, and the orchestrator writes the final `detail.html` before injecting it.

**Tech Stack:** Python 3.12+, Pydantic, PyMuPDF, BeautifulSoup tests, Playwright CDP, pytest/pytest-asyncio, Ruff, mypy.

**Safety and content boundary:** 全流程不自动保存、不自动发布；详情必须使用当前型号的一张尺寸图和四张实拍图，共五张真实图片。

---

## File map

- Modify `pyproject.toml`: declare PyMuPDF runtime dependency.
- Modify `app/domain/models.py`: add immutable detail drawing configuration and prepared path fields.
- Create `app/products/detail_assets.py`: validate, render, and persist the drawing asset and hosted URL.
- Modify `app/products/loader.py`: load `detail_assets.json` and prepare the drawing before browser work.
- Replace `app/products/geo_detail.py`: render the approved ten-section, five-image HTML.
- Modify `app/publisher/orchestrator.py`: upload the drawing, persist its URL and final HTML, then inject it.
- Modify `app/publisher/playwright_port.py`: upload one detail image through TinyMCE and validate five injected images.
- Modify `app/cli.py`: include detail metadata in `task_state.json`.
- Create `tests/unit/products/test_detail_assets.py`: drawing render and cache behavior.
- Modify `tests/unit/products/test_loader.py`: detail asset loading and missing-asset failure.
- Modify `tests/unit/products/test_geo_detail.py`: ten-section and five-image contract.
- Modify `tests/unit/publisher/test_orchestrator.py`: upload order, persistence and five-image HTML.
- Modify `tests/unit/publisher/test_playwright_port_contract.py`: TinyMCE detail picker and safety contract.
- Modify `README.md`: document `detail_assets.json` and the reference-faithful detail behavior.
- Create ignored runtime file `automation/W3G710-NU31-03/detail_assets.json` and generated drawing under `data/draft_saved/W3G710-NU31-03/upload_optimized/`.

### Task 1: Rich ten-section renderer

**Files:**
- Modify: `tests/unit/products/test_geo_detail.py`
- Modify: `app/products/geo_detail.py`

- [ ] **Step 1: Write failing renderer contract tests**

Add a `ProductPayload` fixture for `W3G710-NU31-03`, call the wished-for API, and assert the accepted structure:

```python
html = render_geo_detail(
    payload=w3g710_payload,
    drawing_url="https://example.com/drawing.jpg",
    image_urls=[f"https://example.com/product-{i}.jpg" for i in range(4)],
    image_roles=["整机正面", "整机背面", "EC电机", "型号铭牌"],
)
soup = BeautifulSoup(html, "html.parser")
assert [node["data-geo-section"] for node in soup.select("[data-geo-section]")] == [
    "dimension-drawing", "application-scenes", "product-components",
    "product-definition", "buyer-reasons", "core-parameters",
    "application-guidance", "selection-reminders", "purchase-confirmation",
    "faq-selection",
]
assert len(soup.select("img")) == 5
assert len({node["src"] for node in soup.select("img")}) == 5
assert all("W3G710-NU31-03" in node.get("alt", "") for node in soup.select("img"))
assert "25,590m³/h" in html
assert "420Pa" in html
assert "850 × 842 × 279mm" in html
assert "T4E45BAM81100" not in html
```

Add rejection tests for duplicate URLs, absent drawing URL, missing required specification keys, and a payload whose `规格型号` differs from `payload.model`.

- [ ] **Step 2: Run the renderer tests and verify RED**

Run: `python -m pytest tests/unit/products/test_geo_detail.py -q`

Expected: failures because `render_geo_detail` does not accept `payload` or `drawing_url`, and still renders eight sections/four images.

- [ ] **Step 3: Implement the renderer**

Change the public signature to:

```python
def render_geo_detail(
    *,
    payload: ProductPayload,
    drawing_url: str,
    image_urls: list[str],
    image_roles: list[str],
) -> str:
```

Validate five distinct non-empty URLs, exact model equality, and these required specification keys: `规格型号`, `电机功率_w`, `风叶直径_m`, `转速_rpm`, `风量_m3h`, `电流_a`, `重量_kg`. Render the ten confirmed sections in order with inline `#0b3a70`, `#f6f8fb`, white table cells and escaped values. Derive dimensions from `payload.package`, convert `weight_g` to kilograms, label the free-air value as `0Pa 风量`, and include five direct-answer FAQ entries. Use one drawing image and each of the four product images once.

The visible Chinese module titles must be exactly represented as: 产品尺寸图、场景使用、产品组成、型号标题与产品定义、买家为什么选择这款风机、核心参数、适用场景、选型提醒、采购前请确认、常见问题 FAQ 与一句话选型。

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest tests/unit/products/test_geo_detail.py -q`

Expected: all renderer tests pass.

Commit: `git add app/products/geo_detail.py tests/unit/products/test_geo_detail.py && git commit -m "feat: render reference-faithful fan detail"`

### Task 2: PDF drawing preparation and cache

**Files:**
- Modify: `pyproject.toml`
- Modify: `app/domain/models.py`
- Create: `app/products/detail_assets.py`
- Create: `tests/unit/products/test_detail_assets.py`
- Modify: `tests/unit/products/test_loader.py`
- Modify: `app/products/loader.py`

- [ ] **Step 1: Write failing drawing preparation tests**

Create a two-page PDF with PyMuPDF in `tmp_path`, place `W3G710-NU31-03` text and a rectangle on page 2, and define:

```python
spec = DetailDrawingSpec(
    model="W3G710-NU31-03",
    pdf_file="sheet.pdf",
    page=2,
    crop=(0.05, 0.10, 0.95, 0.75),
    local_file="upload_optimized/detail-drawing.jpg",
)
path = prepare_detail_drawing(tmp_path, spec)
assert path.is_file()
assert path.stat().st_size > 0
assert path.name == "detail-drawing.jpg"
```

Add tests rejecting page 0, an out-of-range page, crop coordinates outside 0..1, inverted crop coordinates, a mismatched model, missing PDF, and an existing non-empty cached JPEG being reused without rewriting its modification time.

Update loader tests to require a matching `detail_assets.json` and return an existing prepared drawing path; missing configuration must raise `ManualReviewRequired` before browser work.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/unit/products/test_detail_assets.py tests/unit/products/test_loader.py -q`

Expected: import failures for `DetailDrawingSpec` and `prepare_detail_drawing`.

- [ ] **Step 3: Implement models and rendering**

Declare `pymupdf>=1.25` in project dependencies. Add:

```python
class DetailDrawingSpec(BaseModel):
    model_config = ConfigDict(frozen=True)
    model: str
    pdf_file: str
    page: int = Field(ge=1)
    crop: tuple[float, float, float, float]
    local_file: str = "upload_optimized/detail-drawing.jpg"
    hosted_url: str | None = None

class PreparedProduct(BaseModel):
    # existing fields unchanged
    detail_drawing: DetailDrawingSpec
    local_detail_drawing: Path
```

In `detail_assets.py`, validate normalized crop ordering, open `source / pdf_file` with `fitz.open`, convert the one-based page to zero-based, create a page-relative `fitz.Rect`, render at 2x resolution with `alpha=False`, and save JPEG to `source / local_file`. Write `update_detail_hosted_url(path, url)` atomically by preserving all JSON fields and replacing only `hosted_url`.

In the loader, read and exact-match `detail_assets.json`, call `prepare_detail_drawing`, and populate the two new `PreparedProduct` fields.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest tests/unit/products/test_detail_assets.py tests/unit/products/test_loader.py -q`

Expected: all asset and loader tests pass.

Commit: `git add pyproject.toml app/domain/models.py app/products/detail_assets.py app/products/loader.py tests/unit/products/test_detail_assets.py tests/unit/products/test_loader.py && git commit -m "feat: prepare PDF detail drawing"`

### Task 3: Upload a detail drawing without occupying a main image slot

**Files:**
- Modify: `tests/unit/publisher/test_playwright_port_contract.py`
- Modify: `app/publisher/playwright_port.py`

- [ ] **Step 1: Write failing port contract tests**

Test URL normalization and inspect the upload method contract:

```python
assert normalize_hosted_image_urls([
    "https://cbu01.alicdn.com/a.summ.jpg",
    "https://cbu01.alicdn.com/a.jpg",
]) == ["https://cbu01.alicdn.com/a.jpg"]
source = inspect.getsource(Playwright1688Port.upload_detail_image)
assert 'button[title="插入图片"]' in source
assert "要插入的图片(1/1)" in source
assert "_read_detail_image_urls" in source
assert "#guid-primaryPicture" not in source
```

Update the detail synchronization contract so it requires the caller's expected image count and rejects a mismatch.

- [ ] **Step 2: Run the port tests and verify RED**

Run: `python -m pytest tests/unit/publisher/test_playwright_port_contract.py -q`

Expected: import/attribute failures because detail-image upload does not exist.

- [ ] **Step 3: Implement detail upload**

Add `_read_detail_image_urls()` that parses TinyMCE content in the page and normalizes `cbu01.alicdn.com/img/ibank/` URLs. Implement:

```python
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

async def upload_detail_image(self, path: Path, *, existing_url: str | None = None) -> str:
    if existing_url and existing_url.startswith("https://cbu01.alicdn.com/img/ibank/"):
        return existing_url
    before = set(await self._read_detail_image_urls())
    await self.page.locator('#guid-description button[title="插入图片"]').click()
    picker = await _wait_for_picker_frame(self.page)
    await picker.get_by_text("我的电脑", exact=True).click()
    album_select = picker.locator("select:visible").last
    chosen = await _wait_for_album_name(
        lambda: album_select.locator("option").all_text_contents(), self.albums
    )
    await album_select.select_option(label=chosen)
    watermark = picker.locator('input[type="checkbox"]')
    if await watermark.count() and await watermark.first.is_checked():
        await watermark.first.uncheck()
    await picker.locator('input[type="file"]').set_input_files(str(path))
    await picker.wait_for_function(
        "() => document.body.innerText.includes('要插入的图片(1/1)')"
        " && !document.body.innerText.includes('正在上传！')"
        " && !document.body.innerText.includes('准备上传！')",
        timeout=60_000,
    )
    await picker.locator("em", has_text="插入图片").last.click()
    return await _wait_for_new_detail_image_url(self._read_detail_image_urls, before)
```

Change `inject_detail(html, expected_image_count=5)` to compare the returned TinyMCE `imageCount` with the explicit expected count.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest tests/unit/publisher/test_playwright_port_contract.py tests/unit/publisher/test_picker_wait.py -q`

Expected: all port contract and wait tests pass.

Commit: `git add app/publisher/playwright_port.py tests/unit/publisher/test_playwright_port_contract.py && git commit -m "feat: upload dedicated detail drawing"`

### Task 4: Orchestrate and persist the rich detail

**Files:**
- Modify: `tests/unit/publisher/test_orchestrator.py`
- Modify: `app/publisher/orchestrator.py`
- Modify: `tests/unit/test_cli_run.py`
- Modify: `app/cli.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing integration tests**

Extend `RecordingPort` with `upload_detail_image`, set a local drawing and `DetailDrawingSpec` on the product fixture, and require this call order:

```python
assert [name for name, _ in port.calls] == [
    "upload-main", "upload-detail", "fill", "detail", "quality", "boundary"
]
assert generated_html.count("<img ") == 5
assert (product.artifacts_directory / "detail.html").read_text(encoding="utf-8") == generated_html
assert json.loads((product.artifacts_directory / "detail_assets.json").read_text())["hosted_url"] == "https://example.com/drawing.jpg"
```

Extend the CLI state assertion with `detail.template_version`, `detail.local_html`, `detail.drawing_url`, and `detail.image_count == 5`.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/unit/publisher/test_orchestrator.py tests/unit/test_cli_run.py -q`

Expected: fixtures and call-order assertions fail because the orchestrator never uploads or persists a detail drawing.

- [ ] **Step 3: Implement orchestration and state**

Extend `UploaderPort` with `upload_detail_image`. In `ProductUploader.run`, upload/reuse the detail drawing immediately after the main images, persist the URL using `update_detail_hosted_url`, fill the product, render the five-image detail, atomically write `detail.html`, inject with expected image count 5, run quality once, and preserve the existing save boundary. Extend `UploadResult` with `detail_drawing_url`, `detail_html_path`, and `detail_image_count`.

In `app/cli.py`, save:

```python
"detail": {
    "template_version": "reference-faithful-v1",
    "local_html": str(result.detail_html_path),
    "drawing_url": result.detail_drawing_url,
    "image_count": result.detail_image_count,
}
```

Update README's artifact tree and safety section; retain the no-save/no-publish guarantee.

- [ ] **Step 4: Verify GREEN and full regression suite**

Run: `python -m pytest -q`

Expected: all tests pass.

Run: `python -m ruff check . && python -m ruff format --check . && python -m mypy app`

Expected: zero lint, format or type errors.

Commit: `git add app/publisher/orchestrator.py app/cli.py README.md tests/unit/publisher/test_orchestrator.py tests/unit/test_cli_run.py && git commit -m "feat: persist rich detail workflow"`

### Task 5: Prepare W3G710 and refresh the real 1688 page

**Files:**
- Create runtime: `automation/W3G710-NU31-03/detail_assets.json`
- Generate runtime: `data/draft_saved/W3G710-NU31-03/upload_optimized/detail-drawing.jpg`
- Generate runtime: `automation/W3G710-NU31-03/detail.html`
- Update runtime: `automation/W3G710-NU31-03/task_state.json`

- [ ] **Step 1: Add the current model drawing configuration**

Use this exact runtime configuration:

```json
{
  "model": "W3G710-NU31-03",
  "pdf_file": "Data_sheet_US_-_W3G710NU3103_VWA0710BTTPS_KM289792_.pdf",
  "page": 4,
  "crop": [0.04, 0.12, 0.96, 0.69],
  "local_file": "upload_optimized/detail-drawing.jpg",
  "hosted_url": null
}
```

- [ ] **Step 2: Prepare and visually inspect the drawing**

Load the product through `load_prepared_product`, inspect the generated JPEG, and adjust only the configured crop if dimension lines, `850`, `842`, `279`, or the full model are clipped. Keep the original PDF unchanged and ensure the JPEG is below 5MB.

- [ ] **Step 3: Render a local preview with known hosted product URLs**

Run a read-only CDP script to collect the four existing hosted main image URLs, call `render_geo_detail` with a temporary drawing URL, write the preview to `automation/W3G710-NU31-03/detail.html`, and open it in Chrome. Verify the ten modules, five image positions, tables, no text corruption and no unrelated model.

- [ ] **Step 4: Run the real uploader**

Run: `python -m app.cli doctor --root D:\Auto-Alibab`

Expected: Python, workbook and Chrome CDP 9223 are all OK.

Run: `python -m app.cli run W3G710-NU31-03 --root D:\Auto-Alibab`

Expected: the tagged current-model page is reused, the detail drawing uploads once, the final HTML is injected, quality errors are 0, and the command reports `READY_TO_SAVE` without clicking save.

- [ ] **Step 5: Perform independent browser verification**

Use a read-only CDP script to assert:

- `window.name == "1688-uploader:W3G710-NU31-03"`;
- four hosted main images;
- TinyMCE contains the complete model, at least five images, the confirmed parameter values and no `T4E45BAM81100`;
- `detail.html` matches the injected semantic content;
- `#saveDraftButton` exists and has not been clicked;
- `task_state.json` is `READY_TO_SAVE` with quality errors 0 and detail image count 5.

- [ ] **Step 6: Final verification**

Run: `python -m pytest -q && python -m ruff check . && python -m ruff format --check . && python -m mypy app`

Expected: all commands exit 0.

Do not commit ignored product runtime artifacts. Commit any final test-only adjustments with `git commit -m "test: verify W3G710 rich detail"` only when tracked files changed.
