# Multi-Brand Fan Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ebm-papst-specific assumptions with one evidence-driven upload path for all industrial-fan brands, including automatic brand album rollover, then upload SUNON DP201AT-2122HBL.GN to `READY_TO_SAVE` without saving.

**Architecture:** The upload Skill remains responsible for turning the operator's three inputs—PDF, real photos, and price/stock Excel—into internal evidence. The Python project validates that evidence, builds a brand-explicit payload, emits sparse form fields and generic detail HTML, and uses a dedicated album policy to select or create `品牌(NN)` albums. Browser safety, media identity, quality checks, and the save boundary remain unchanged.

**Tech Stack:** Python 3.12+, Pydantic, PyMuPDF, Playwright async API, Typer, pytest, Ruff, mypy.

---

### Task 1: Make brand and composite model evidence explicit

**Files:**
- Modify: `app/domain/models.py`
- Modify: `app/products/preparer.py`
- Modify: `tests/unit/products/test_preparer.py`
- Create: `tests/unit/domain/test_models.py`

- [ ] **Step 1: Write failing payload and preparation tests**

Add tests proving that brand is required, preparation copies the evidence brand into the runtime payload, and a same-page labeled `MODEL` plus `P/N` pair validates the complete business model:

```python
def test_product_payload_requires_explicit_brand() -> None:
    with pytest.raises(ValidationError, match="brand"):
        ProductPayload(
            model="DP201AT-2122HBL.GN",
            title="title",
            category_id=1034320,
            industry_category_id=2293,
            attributes={},
            specification={"规格型号": "DP201AT-2122HBL.GN"},
            price=10000,
            stock=50,
            delivery_time="48小时发货",
            shipping_template="运费",
            package=PackageInfo(length_cm=11.9, width_cm=11.9, height_cm=2.55, weight_g=295),
        )


def test_pdf_model_and_part_number_on_same_page_validate_composite_model(tmp_path: Path) -> None:
    pdf = tmp_path / "sunon.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "MODEL  DP201AT\nP/N  2122HBL.GN")
    document.save(pdf)

    assert _pdf_contains_exact_model(pdf, "DP201AT-2122HBL.GN")


def test_pdf_unlabeled_or_cross_page_parts_do_not_validate(tmp_path: Path) -> None:
    pdf = tmp_path / "unsafe.pdf"
    document = fitz.open()
    document.new_page().insert_text((72, 72), "DP201AT")
    document.new_page().insert_text((72, 72), "P/N 2122HBL.GN")
    document.save(pdf)

    assert not _pdf_contains_exact_model(pdf, "DP201AT-2122HBL.GN")
```

Update the existing preparation fixture with `"brand": "ebm-papst"` and assert `payload["brand"] == "ebm-papst"`.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
python -m pytest tests/unit/domain/test_models.py tests/unit/products/test_preparer.py -q
```

Expected: missing-brand validation does not fail, `PreparationEvidence` rejects the new `brand` field usage or fails to populate it, and the composite PDF model test returns `False`.

- [ ] **Step 3: Implement explicit brand and labeled composite matching**

Change `ProductPayload` and `PreparationEvidence` so brand has no default:

```python
class ProductPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: str
    brand: str = Field(min_length=1)
    title: str
    # existing fields remain unchanged


class PreparationEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: str
    brand: str = Field(min_length=1)
    pdf_file: str
    # existing fields remain unchanged
```

Add a same-page labeled fallback after the existing exact-token check:

```python
def _labeled_composite_match(text: str, model: str) -> bool:
    for match in re.finditer("-", model):
        left, right = model[: match.start()], model[match.end() :]
        model_token = re.compile(
            rf"\bMODEL\b\s*[:：]?\s*{re.escape(left)}(?![A-Z0-9/_-])",
            flags=re.IGNORECASE,
        )
        part_token = re.compile(
            rf"\bP\s*/\s*N\b\s*[:：]?\s*{re.escape(right)}(?![A-Z0-9/_-])",
            flags=re.IGNORECASE,
        )
        if model_token.search(text) and part_token.search(text):
            return True
    return False
```

In `_pdf_contains_exact_model`, evaluate both checks on each individual page. In `prepare_product`, pass `brand=evidence.brand` to `ProductPayload`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```powershell
python -m pytest tests/unit/domain/test_models.py tests/unit/products/test_preparer.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit Task 1**

```powershell
git add app/domain/models.py app/products/preparer.py tests/unit/domain/test_models.py tests/unit/products/test_preparer.py
git commit -m "feat: require evidenced product brands"
```

### Task 2: Replace positional value tuples with sparse form entries

**Files:**
- Modify: `app/publisher/form_plan.py`
- Modify: `app/publisher/playwright_port.py`
- Modify: `tests/unit/publisher/test_form_plan.py`
- Modify: `tests/unit/publisher/test_playwright_port_contract.py`

- [ ] **Step 1: Write failing sparse-plan tests**

Define the desired plan contract in `test_form_plan.py`:

```python
def test_form_plan_omits_unverified_optional_values() -> None:
    payload = ProductPayload(
        model="DP201AT-2122HBL.GN",
        brand="SUNON",
        title="SUNON DP201AT-2122HBL.GN 交流轴流风扇",
        category_id=1034320,
        industry_category_id=2293,
        attributes={"电压": "220-240V", "品牌": "SUNON", "类型": "轴流风扇"},
        specification={
            "规格型号": "DP201AT-2122HBL.GN",
            "电机功率_w": "18/16.5",
            "转速_rpm": "2150/2500",
            "电流_a": "0.09/0.09",
        },
        price=10000,
        stock=50,
        delivery_time="48小时发货",
        shipping_template="运费",
        package=PackageInfo(length_cm=11.9, width_cm=11.9, height_cm=2.55, weight_g=295),
    )

    plan = build_form_plan(payload)

    assert plan.attribute_fields == (
        FormField(index=0, label="电压", value="220-240V"),
        FormField(index=3, label="品牌", value="SUNON"),
        FormField(index=5, label="类型", value="轴流风扇"),
    )
    assert plan.spec_fields == (
        FormField(index=0, label="规格型号", value="DP201AT-2122HBL.GN"),
        FormField(index=1, label="电机功率_w", value="18/16.5"),
        FormField(index=3, label="转速_rpm", value="2150/2500"),
        FormField(index=5, label="电流_a", value="0.09/0.09"),
    )
```

Replace the source-inspection material test with assertions that `fill_product` loops over `plan.attribute_fields` and contains no literal `PP塑料`.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```powershell
python -m pytest tests/unit/publisher/test_form_plan.py tests/unit/publisher/test_playwright_port_contract.py -q
```

Expected: `FormField`, `attribute_fields`, and `spec_fields` do not exist, and the literal PP material assertion fails.

- [ ] **Step 3: Implement sparse entries**

Use named index maps and emit entries only for keys present with non-empty values:

```python
@dataclass(frozen=True)
class FormField:
    index: int
    label: str
    value: str


ATTRIBUTE_INDEXES = {
    "电压": 0,
    "产品别名": 1,
    "风叶材质": 2,
    "品牌": 3,
    "噪声": 4,
    "类型": 5,
    "叶片数": 6,
    "适用范围": 7,
    "工业风扇种类": 8,
}
SPEC_INDEXES = {
    "规格型号": 0,
    "电机功率_w": 1,
    "风叶直径_m": 2,
    "转速_rpm": 3,
    "风量_m3h": 4,
    "电流_a": 5,
    "重量_kg": 6,
}


def _fields(values: dict[str, str | int | float], indexes: dict[str, int]) -> tuple[FormField, ...]:
    return tuple(
        FormField(index=index, label=label, value=_text(values[label]))
        for label, index in indexes.items()
        if label in values and _text(values[label]).strip()
    )
```

Change `FormPlan` to expose `attribute_fields` and `spec_fields`. In `fill_product`, iterate those fields, skip absent values by construction, select an exact visible option when present, otherwise press Tab, and never inject a material literal:

```python
for entry in plan.attribute_fields:
    field = attributes.nth(entry.index)
    if value_matches(await field.input_value(), entry.value):
        continue
    await field.click()
    await field.fill("")
    await self.page.keyboard.type(entry.value)
    option = self.page.get_by_role("option", name=entry.value, exact=True)
    if await option.count() and await option.first.is_visible():
        await option.first.click(timeout=3_000)
    else:
        await self.page.keyboard.press("Tab")

for entry in plan.spec_fields:
    if value_matches(await cells.nth(entry.index).inner_text(), entry.value, contains=True):
        continue
    await cells.nth(entry.index).click()
    focused = self.page.locator("input:focus")
    await focused.fill(entry.value)
    await focused.press("Tab")
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```powershell
python -m pytest tests/unit/publisher/test_form_plan.py tests/unit/publisher/test_playwright_port_contract.py -q
```

Expected: all selected tests pass and no production source contains `PP塑料` outside test evidence.

- [ ] **Step 5: Commit Task 2**

```powershell
git add app/publisher/form_plan.py app/publisher/playwright_port.py tests/unit/publisher/test_form_plan.py tests/unit/publisher/test_playwright_port_contract.py
git commit -m "feat: fill only evidenced product fields"
```

### Task 3: Replace the W3G710 detail page with a generic evidence renderer

**Files:**
- Modify: `app/products/geo_detail.py`
- Rewrite: `tests/unit/products/test_geo_detail.py`
- Modify: `tests/unit/publisher/test_orchestrator.py`
- Modify: `app/cli.py`

- [ ] **Step 1: Write failing SUNON and ebm-papst detail tests**

Build a SUNON payload with sparse specifications and assert the output contains five unique images and only evidenced text:

```python
def test_geo_detail_renders_only_evidenced_sunon_values(sunon_payload: ProductPayload) -> None:
    html = render_geo_detail(
        payload=sunon_payload,
        drawing_url="https://example.com/drawing.jpg",
        image_urls=[f"https://example.com/product-{index}.jpg" for index in range(4)],
        image_roles=["铭牌侧", "背面", "叶轮侧", "侧面"],
    )
    soup = BeautifulSoup(html, "html.parser")

    assert len(soup.select("img")) == 5
    assert len({image["src"] for image in soup.select("img")}) == 5
    assert "SUNON" in html
    assert "DP201AT-2122HBL.GN" in html
    assert "220-240V" in html
    assert "18/16.5W" in html
    for forbidden in ("ebm-papst", "400V", "AxiBlade", "MODBUS", "5 片 PP"):
        assert forbidden not in html
```

Add an ebm-papst payload test proving that its explicit values still render, and change the former missing-required-parameter test so a payload containing only `规格型号` renders without empty rows.

- [ ] **Step 2: Run detail tests and verify RED**

Run:

```powershell
python -m pytest tests/unit/products/test_geo_detail.py tests/unit/publisher/test_orchestrator.py -q
```

Expected: the SUNON detail contains hard-coded ebm-papst facts and sparse specifications raise `ManualReviewRequired`.

- [ ] **Step 3: Implement the generic renderer**

Retain URL/model validation, but require only `规格型号`. Define display metadata without required-key validation:

```python
SPEC_META = {
    "规格型号": ("完整型号", ""),
    "额定电压_v": ("额定电压", "V"),
    "电压范围_v": ("电压范围", "V"),
    "频率_hz": ("频率", "Hz"),
    "电机功率_w": ("功率", "W"),
    "风叶直径_m": ("风叶直径", "m"),
    "转速_rpm": ("转速", "rpm"),
    "风量_m3h": ("风量", "m³/h"),
    "风量_cfm": ("风量", "CFM"),
    "最大静压_pa": ("最大静压", "Pa"),
    "最大静压_inH2O": ("最大静压", "inH₂O"),
    "电流_a": ("电流", "A"),
    "重量_kg": ("重量", "kg"),
    "防护等级": ("防护等级", ""),
    "绝缘等级": ("绝缘等级", ""),
    "电机保护": ("电机保护", ""),
    "框体材质": ("框体材质", ""),
    "轴承系统": ("轴承系统", ""),
    "工作温度_c": ("工作温度", "°C"),
}
```

Render only four neutral sections: `dimension-drawing`, `product-images`, `product-definition`, and `core-parameters`. The parameter rows begin with brand and complete model, then non-duplicate attributes and specifications that are present. Use `payload.brand` for all prefixes and avoid unsupported application claims.

For specification keys not listed in `SPEC_META`, preserve the evidence key as the visible label after replacing the final unit suffix with a parenthesized unit. For example, `尺寸_mm` becomes `尺寸 (mm)`. This keeps new-brand evidence visible without adding a product-specific code branch.

Change `build_task_state` detail version from `reference-faithful-v1` to `evidence-driven-v2`.

- [ ] **Step 4: Run detail tests and verify GREEN**

Run:

```powershell
python -m pytest tests/unit/products/test_geo_detail.py tests/unit/publisher/test_orchestrator.py -q
```

Expected: all selected tests pass, every case still has exactly five distinct images, and sparse SUNON content contains no ebm-papst facts.

- [ ] **Step 5: Commit Task 3**

```powershell
git add app/products/geo_detail.py app/cli.py tests/unit/products/test_geo_detail.py tests/unit/publisher/test_orchestrator.py
git commit -m "feat: render generic evidence-driven details"
```

### Task 4: Add deterministic brand album naming and rollover policy

**Files:**
- Create: `app/publisher/album_policy.py`
- Create: `tests/unit/publisher/test_album_policy.py`

- [ ] **Step 1: Write failing pure policy tests**

```python
def test_brand_album_names_are_exact_and_zero_padded() -> None:
    assert brand_album_name("SUNON", 1) == "SUNON(01)"
    assert matching_brand_albums("SUNON", ["SUNON(01)", "SUNON(09)", "SUNON风扇", "Delta(10)"]) == (
        BrandAlbum(name="SUNON(01)", number=1),
        BrandAlbum(name="SUNON(09)", number=9),
    )


def test_album_choice_uses_latest_or_creates_first() -> None:
    assert choose_brand_album("Delta", []) == AlbumChoice(name="Delta(01)", create=True)
    assert choose_brand_album("Delta", ["Delta(01)", "Delta(03)"]) == AlbumChoice(
        name="Delta(03)", create=False
    )


def test_next_album_increments_highest_brand_number_only() -> None:
    assert next_brand_album("SUNON", ["SUNON(02)", "Delta(99)"]) == "SUNON(03)"
```

- [ ] **Step 2: Run the policy tests and verify RED**

Run:

```powershell
python -m pytest tests/unit/publisher/test_album_policy.py -q
```

Expected: import fails because `album_policy.py` does not exist.

- [ ] **Step 3: Implement the pure policy module**

```python
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class BrandAlbum:
    name: str
    number: int


@dataclass(frozen=True)
class AlbumChoice:
    name: str
    create: bool


def brand_album_name(brand: str, number: int) -> str:
    clean = brand.strip()
    if not clean or number < 1:
        raise ValueError("brand and positive album number are required")
    return f"{clean}({number:02d})"


def matching_brand_albums(brand: str, names: list[str]) -> tuple[BrandAlbum, ...]:
    pattern = re.compile(rf"^{re.escape(brand.strip())}\((\d{{2,}})\)$", re.IGNORECASE)
    matches = [
        BrandAlbum(name=name, number=int(match.group(1)))
        for name in names
        if (match := pattern.fullmatch(name.strip())) is not None
    ]
    return tuple(sorted(matches, key=lambda item: item.number))


def choose_brand_album(brand: str, names: list[str]) -> AlbumChoice:
    matches = matching_brand_albums(brand, names)
    return AlbumChoice(
        name=matches[-1].name if matches else brand_album_name(brand, 1),
        create=not matches,
    )


def next_brand_album(brand: str, names: list[str]) -> str:
    matches = matching_brand_albums(brand, names)
    return brand_album_name(brand, matches[-1].number + 1 if matches else 1)
```

- [ ] **Step 4: Run policy tests and verify GREEN**

Run:

```powershell
python -m pytest tests/unit/publisher/test_album_policy.py -q
```

Expected: all album policy tests pass.

- [ ] **Step 5: Commit Task 4**

```powershell
git add app/publisher/album_policy.py tests/unit/publisher/test_album_policy.py
git commit -m "feat: add brand album rollover policy"
```

### Task 5: Integrate brand albums into the 1688 picker

**Files:**
- Modify: `app/publisher/playwright_port.py`
- Modify: `app/cli.py`
- Create: `tests/unit/publisher/test_album_picker.py`
- Modify: `tests/unit/publisher/test_playwright_port_contract.py`

- [ ] **Step 1: Write failing picker state tests**

Test capacity-state parsing without browser mocks:

```python
@pytest.mark.parametrize("text", ["当前相册已满", "相册容量不足", "图片空间不足"])
def test_album_capacity_messages_are_detected(text: str) -> None:
    assert upload_capacity_exhausted(text)


def test_normal_upload_progress_is_not_capacity_exhaustion() -> None:
    assert not upload_capacity_exhausted("正在上传！ 要插入的图片(4/4)")
```

Add source-contract assertions that `Playwright1688Port` stores `brand`, calls `choose_brand_album`, calls `next_brand_album` only after a capacity result, and contains no `ebm(L)` or `ebm(LCC)` literals. In the same test file, import `run_product` and assert the exact CLI connection contract:

```python
def test_run_product_passes_evidenced_brand_to_port() -> None:
    source = inspect.getsource(run_product)
    assert "brand=product.payload.brand" in source
```

- [ ] **Step 2: Run picker tests and verify RED**

Run:

```powershell
python -m pytest tests/unit/publisher/test_album_picker.py tests/unit/publisher/test_playwright_port_contract.py -q
```

Expected: capacity helper and brand-aware picker behavior do not exist.

- [ ] **Step 3: Add picker helpers and brand-aware connection**

Change `Playwright1688Port.__init__` and `connect` to require `brand: str`; remove default ebm album tuples. Add:

```python
ALBUM_CAPACITY_MESSAGES = ("当前相册已满", "相册容量不足", "图片空间不足")


def upload_capacity_exhausted(body_text: str) -> bool:
    return any(message in body_text for message in ALBUM_CAPACITY_MESSAGES)


async def _create_album(picker: Any, album_select: Any, name: str) -> None:
    await picker.get_by_text("新建相册", exact=True).click(timeout=5_000)
    dialog = picker.locator('[role="dialog"]:visible').last
    field = dialog.locator('input[placeholder*="相册"]:visible').last
    await field.fill(name)
    await dialog.get_by_role("button", name="确定", exact=True).click(timeout=5_000)
    await album_select.locator("option").filter(has_text=name).wait_for(
        state="attached", timeout=10_000
    )


async def _select_brand_album(picker: Any, brand: str) -> tuple[Any, list[str]]:
    album_select = picker.locator("select:visible").last
    names = [text.strip() for text in await album_select.locator("option").all_text_contents()]
    choice = choose_brand_album(brand, names)
    if choice.create:
        await _create_album(picker, album_select, choice.name)
        names.append(choice.name)
    await album_select.select_option(label=choice.name)
    return album_select, names
```

In `app/cli.py`, remove the ebm default and pass `brand=product.payload.brand` to `Playwright1688Port.connect`.

- [ ] **Step 4: Implement one controlled full-album rollover**

Extract one batch uploader used by main and detail uploads. After `set_input_files`, wait until either the existing success predicate is true or `upload_capacity_exhausted(await body.inner_text())` is true. On capacity exhaustion, create exactly `next_brand_album(self.brand, names)`, select it, set the same files once more, and require success. A second capacity result raises:

```python
raise ManualReviewRequired(
    f"new brand album is unavailable or full after one retry: {rollover_name}"
)
```

Keep current watermark disabling, image-count verification, hosted URL checks, and media fingerprint behavior unchanged.

- [ ] **Step 5: Run picker tests and verify GREEN**

Run:

```powershell
python -m pytest tests/unit/publisher/test_album_picker.py tests/unit/publisher/test_playwright_port_contract.py -q
```

Expected: all selected tests pass; no uploader source contains the old ebm album names.

- [ ] **Step 6: Commit Task 5**

```powershell
git add app/publisher/playwright_port.py app/cli.py tests/unit/publisher/test_album_picker.py tests/unit/publisher/test_playwright_port_contract.py
git commit -m "feat: roll over full brand albums"
```

### Task 6: Align the upload Skill and prepare the current SUNON product

**Files:**
- Modify: `C:/Users/小城/.codex/skills/upload-1688-products/SKILL.md`
- Create: `D:/Auto-Alibaba/automation/DP201AT-2122HBL.GN/preparation_evidence.json`

- [ ] **Step 1: Update the Skill input contract**

Insert this exact contract into the Skill preparation section:

```markdown
操作者的外部输入仅限当前型号 PDF、至少四张真实产品照片，以及 Excel 中的价格和库存。品牌、标题、属性、规格、包装值、图片角色、尺寸图裁剪和全部运行 JSON 均由本 Skill 从这些资料中生成；不得要求操作者手工填写 JSON、品牌或技术参数。品牌必须由规格书制造商标识或清晰的铭牌/产品标识确认。普通技术字段没有证据时直接省略。

图片相册按精确品牌名使用 `品牌(NN)` 连续编号。优先选择当前品牌编号最大的相册；相册不存在时创建 `(01)`；上传明确返回容量不足时只允许创建下一编号并重试当前批次一次。禁止使用其他品牌相册。
```

- [ ] **Step 2: Create SUNON evidence from the already reviewed sources**

Write internal evidence with:

```json
{
  "model": "DP201AT-2122HBL.GN",
  "brand": "SUNON",
  "pdf_file": "DP201AT_2122HBL.GN_A12003370G_00_3.pdf",
  "title": "SUNON DP201AT-2122HBL.GN 220-240V 120×120×25mm 交流轴流风扇",
  "attributes": {
    "电压": "220-240V",
    "产品别名": "交流轴流风扇",
    "风叶材质": "PBT热塑性塑料（UL 94V-0）",
    "品牌": "SUNON",
    "噪声": "44/48dB(A)",
    "类型": "轴流风扇",
    "工业风扇种类": "轴流风扇"
  },
  "specification": {
    "规格型号": "DP201AT-2122HBL.GN",
    "额定电压_v": "220-240",
    "电压范围_v": "185-245",
    "频率_hz": "50/60",
    "电机功率_w": "18/16.5",
    "尺寸_mm": "120×120×25",
    "转速_rpm": "2150/2500",
    "风量_cfm": "66/80",
    "最大静压_inH2O": "0.14/0.17",
    "电流_a": "0.09/0.09",
    "重量_kg": 0.295,
    "电机保护": "阻抗保护",
    "绝缘等级": "B级",
    "框体材质": "压铸铝",
    "轴承系统": "精密滚珠轴承",
    "工作温度_c": "-10~+70"
  },
  "package": {"length_cm": 11.9, "width_cm": 11.9, "height_cm": 2.55, "weight_g": 295},
  "images": [
    {"local_file": "IMG_9544.JPG", "role": "铭牌侧整机与型号"},
    {"local_file": "IMG_9545.JPG", "role": "铭牌侧三分之四视图"},
    {"local_file": "IMG_9549.JPG", "role": "叶轮侧三分之四视图"},
    {"local_file": "IMG_9546.JPG", "role": "侧面厚度与引线"}
  ],
  "drawing": {"page": 5, "crop": [0.1, 0.29, 0.92, 0.84]}
}
```

Do not add a blade diameter, IP rating, converted airflow, converted pressure, or other unsupported value.

- [ ] **Step 3: Run preparation and inspect generated artifacts**

Run:

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
python -m app.cli prepare 'DP201AT-2122HBL.GN' --root 'D:\Auto-Alibaba'
```

Expected: JSON status `PREPARED`, four square main images, one drawing, and a payload whose brand is `SUNON`. Inspect `1688_payload.json` and rendered detail locally to confirm no ebm-papst-specific text.

### Task 7: Full verification and guarded upload

**Files:**
- Verify all modified project and Skill files
- Runtime output: `automation/DP201AT-2122HBL.GN/task_state.json`

- [ ] **Step 1: Run all project verification commands**

Run:

```powershell
python -m pytest -q
python -m ruff check .
python -m mypy app
```

Expected: all tests pass, Ruff reports no errors, and mypy reports success.

- [ ] **Step 2: Re-run upload preconditions**

Run in the order required by the upload Skill:

```powershell
python -m app.cli init-product 'DP201AT-2122HBL.GN' --root 'D:\Auto-Alibaba'
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Users\小城\.codex\skills\upload-1688-products\scripts\ensure_chrome.ps1' -Root 'D:\Auto-Alibaba'
python -m app.cli doctor --root 'D:\Auto-Alibaba'
```

Expected: product inputs ready, dedicated Chrome CDP 9223 ready, and all doctor checks pass.

- [ ] **Step 3: Run the only authorized upload entry**

Run:

```powershell
python 'C:\Users\小城\.codex\skills\upload-1688-products\scripts\run_upload.py' --root 'D:\Auto-Alibaba' --model 'DP201AT-2122HBL.GN' --cdp-url 'http://127.0.0.1:9223'
```

Expected final JSON: `status` is `READY_TO_SAVE`, `quality_errors` is `0`, detail image count is `5`, and the message confirms the run stopped before save. If the final JSON is `NEEDS_LOGIN`, `BLOCKED`, or `FAILED`, report its exact message and checks without claiming completion.

- [ ] **Step 4: Verify the saved boundary without clicking it**

Read `automation/DP201AT-2122HBL.GN/task_state.json` and confirm it is fresh for this run, model is exact, quality errors are zero, detail template version is `evidence-driven-v2`, and image count is five. Do not click “保存草稿” or any publish action.

- [ ] **Step 5: Commit project implementation changes**

If Tasks 1–5 were not committed individually, stage only their project files and commit:

```powershell
git add app tests docs/superpowers/plans/2026-07-14-multi-brand-fan-upload.md
git commit -m "feat: support multi-brand fan uploads"
```

Do not add `automation/`, `data/`, `.chrome-profile/`, inventory files, credentials, cookies, or local Skill runtime state to Git.
