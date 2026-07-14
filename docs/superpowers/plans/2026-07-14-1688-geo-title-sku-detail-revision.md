# 1688 Multi-Brand GEO Title, SKU, and Detail Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an evidence-driven, multi-brand 1688 listing path that produces the approved title, single-SKU specification, adaptive GEO detail, fixed six-image company tail, and `READY_TO_SAVE` result for `DP201AT-2122HBL.GN` without saving or publishing.

**Architecture:** Keep the operator input boundary at one PDF, real model photos, and Excel price/stock. Add structured 50/60Hz operating points and deterministic platform-spec materialization, validate evidence-authored titles before browser use, render one adaptive detail document with an explicit image manifest, and pass that manifest through editor synchronization, quality checks, task state, and the upload Skill. The existing brand-album rollover policy remains the only media-album path.

**Tech Stack:** Python 3.12+, Pydantic 2, PyYAML, BeautifulSoup, PyMuPDF, Playwright async API, Typer, pytest, Ruff, mypy.

**Approved spec:** `docs/superpowers/specs/2026-07-14-1688-geo-title-sku-detail-revision-design.md`

**Execution constraint:** The user explicitly prohibited subagents. Execute this plan inline with `superpowers:executing-plans` unless the user later explicitly changes that instruction.

**Safety constraint:** Use only the bundled `upload-1688-products` wrapper and dedicated Chrome CDP `http://127.0.0.1:9223`. Never click “保存草稿”, publish, or an equivalent final action.

**Baseline:** `python -m pytest -q` currently reports `161 passed`.

---

## File responsibility map

- Create `app/products/specification_policy.py`: operating-point unit conversion and deterministic slash-value materialization.
- Create `app/products/title_policy.py`: 60-character, brand/model/product-name, and unsupported-claim validation.
- Create `app/products/detail_policy.py`: validated loading of the detail section order and fixed company-tail URLs.
- Modify `app/domain/models.py`: add immutable structured operating points.
- Modify `app/products/preparer.py`: validate titles, enrich operating points, and materialize platform specifications.
- Modify `app/products/geo_detail.py`: render the approved adaptive answer-first detail and return its exact image manifest.
- Modify `app/publisher/form_plan.py`: replace positional sales tuples with an explicit single-SKU plan.
- Modify `app/publisher/playwright_port.py`: verify the 60-character title field, one SKU row, editor sync, and dynamic quality manifest.
- Modify `app/publisher/orchestrator.py`: propagate rendered HTML and exact image sources instead of hardcoded `5`.
- Modify `app/publisher/quality.py`: validate exact image count, uniqueness, order, and fixed tail against the form model.
- Modify `app/cli.py`: record `geo-evidence-v3` and image sources in `task_state.json`.
- Modify `config/detail_templates.yaml`: make module order and the six approved fixed company images explicit.
- Modify `plugins/auto-alibaba/skills/upload-1688-products/`: update evidence/title/detail rules, stale-artifact handling, and dynamic task-state validation.
- Modify focused tests under `tests/unit/` and `tests/artifacts/`; do not add tests that depend on ignored `automation/` files.

---

### Task 1: Add structured operating points and deterministic 1688 specification values

**Files:**
- Modify: `app/domain/models.py:39`
- Create: `app/products/specification_policy.py`
- Modify: `app/products/preparer.py:26,114`
- Create: `tests/unit/products/test_specification_policy.py`
- Modify: `tests/unit/domain/test_models.py`
- Modify: `tests/unit/products/test_preparer.py`

- [ ] **Step 1: Write failing model and conversion tests**

Add tests that define two immutable working points and require conversion/materialization without rounding drift:

```python
from app.domain.models import OperatingPoint
from app.products.specification_policy import materialize_platform_specification


def test_materializes_50_60hz_slash_values_and_cfm_conversion() -> None:
    points = (
        OperatingPoint(
            frequency_hz=50,
            speed_rpm=2150,
            airflow_cfm=66,
            static_pressure_in_h2o=0.14,
            current_a=0.09,
            power_w=18,
            noise_db_a=44,
        ),
        OperatingPoint(
            frequency_hz=60,
            speed_rpm=2500,
            airflow_cfm=80,
            static_pressure_in_h2o=0.17,
            current_a=0.09,
            power_w=16.5,
            noise_db_a=48,
        ),
    )

    specification, enriched = materialize_platform_specification(
        {"规格型号": "DP201AT-2122HBL.GN", "风叶直径_m": 0.119},
        points,
    )

    assert specification["电机功率_w"] == "18/16.5"
    assert specification["转速_rpm"] == "2150/2500"
    assert specification["风量_m3h"] == "112.1/135.9"
    assert specification["电流_a"] == "0.09/0.09"
    assert [point.airflow_m3h for point in enriched] == [112.1, 135.9]


def test_rejects_platform_value_that_conflicts_with_operating_points() -> None:
    points = (OperatingPoint(frequency_hz=50, airflow_cfm=66),)

    with pytest.raises(ManualReviewRequired, match="风量_m3h"):
        materialize_platform_specification({"风量_m3h": "999"}, points)
```

Add a Pydantic test proving `frequency_hz <= 0` is rejected and an empty tuple remains valid for sparse legacy products.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```powershell
python -m pytest tests/unit/domain/test_models.py tests/unit/products/test_specification_policy.py tests/unit/products/test_preparer.py -q
```

Expected: collection fails because `OperatingPoint` and `materialize_platform_specification` do not exist.

- [ ] **Step 3: Add the operating-point model**

Insert this model before `ProductPayload` and add `operating_points` to `ProductPayload`:

```python
class OperatingPoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    frequency_hz: int = Field(gt=0)
    speed_rpm: float | None = Field(default=None, gt=0)
    airflow_cfm: float | None = Field(default=None, ge=0)
    airflow_m3h: float | None = Field(default=None, ge=0)
    static_pressure_in_h2o: float | None = Field(default=None, ge=0)
    current_a: float | None = Field(default=None, ge=0)
    power_w: float | None = Field(default=None, ge=0)
    noise_db_a: float | None = Field(default=None, ge=0)


class ProductPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: str
    brand: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    title: str
    category_id: int
    industry_category_id: int
    attributes: dict[str, str]
    specification: dict[str, str | int | float]
    operating_points: tuple[OperatingPoint, ...] = ()
    price: int
    stock: int
    delivery_time: str
    shipping_template: str
    package: PackageInfo
```

Import `OperatingPoint` in `app/products/preparer.py` and add the same defaulted field to `PreparationEvidence`.

- [ ] **Step 4: Implement deterministic materialization**

Create `app/products/specification_policy.py` with this complete public behavior:

```python
from collections.abc import Callable

from app.domain.errors import ManualReviewRequired
from app.domain.models import OperatingPoint

CFM_TO_M3H = 1.699


def _number(value: float) -> str:
    return f"{value:g}"


def _slash(points: tuple[OperatingPoint, ...], getter: Callable[[OperatingPoint], float | None]) -> str | None:
    values = [getter(point) for point in points]
    if not values or any(value is None for value in values):
        return None
    return "/".join(_number(float(value)) for value in values if value is not None)


def _set_or_verify(
    specification: dict[str, str | int | float], key: str, expected: str | None
) -> None:
    if expected is None:
        return
    existing = str(specification.get(key, "")).strip()
    if existing and existing != expected:
        raise ManualReviewRequired(f"platform specification conflicts with operating points: {key}")
    specification[key] = expected


def materialize_platform_specification(
    raw: dict[str, str | int | float],
    operating_points: tuple[OperatingPoint, ...],
) -> tuple[dict[str, str | int | float], tuple[OperatingPoint, ...]]:
    ordered = tuple(sorted(operating_points, key=lambda point: point.frequency_hz))
    if len({point.frequency_hz for point in ordered}) != len(ordered):
        raise ManualReviewRequired("operating point frequencies must be unique")
    enriched = tuple(
        point.model_copy(
            update={"airflow_m3h": round(point.airflow_cfm * CFM_TO_M3H, 1)}
        )
        if point.airflow_cfm is not None and point.airflow_m3h is None
        else point
        for point in ordered
    )
    specification = dict(raw)
    _set_or_verify(specification, "电机功率_w", _slash(enriched, lambda p: p.power_w))
    _set_or_verify(specification, "转速_rpm", _slash(enriched, lambda p: p.speed_rpm))
    _set_or_verify(specification, "风量_m3h", _slash(enriched, lambda p: p.airflow_m3h))
    _set_or_verify(specification, "电流_a", _slash(enriched, lambda p: p.current_a))
    return specification, enriched
```

- [ ] **Step 5: Materialize once during preparation**

In `prepare_product`, call the policy before constructing `ProductPayload`:

```python
specification, operating_points = materialize_platform_specification(
    evidence.specification,
    evidence.operating_points,
)
payload = ProductPayload(
    model=normalized,
    brand=evidence.brand,
    title=evidence.title,
    category_id=1034320,
    industry_category_id=2293,
    attributes=evidence.attributes,
    specification=specification,
    operating_points=operating_points,
    price=inventory.price,
    stock=inventory.stock,
    delivery_time="48小时发货",
    shipping_template="运费",
    package=evidence.package,
)
```

- [ ] **Step 6: Run tests and commit**

Run:

```powershell
python -m pytest tests/unit/domain/test_models.py tests/unit/products/test_specification_policy.py tests/unit/products/test_preparer.py -q
git add app/domain/models.py app/products/specification_policy.py app/products/preparer.py tests/unit/domain/test_models.py tests/unit/products/test_specification_policy.py tests/unit/products/test_preparer.py
git commit -m "feat: structure fan operating points"
```

Expected: focused tests pass and the commit contains no runtime `automation/` files.

---

### Task 2: Enforce evidence-authored GEO titles before browser use

**Files:**
- Create: `app/products/title_policy.py`
- Modify: `app/products/preparer.py`
- Modify: `app/publisher/form_plan.py`
- Create: `tests/unit/products/test_title_policy.py`

- [ ] **Step 1: Write failing title-policy tests**

```python
import pytest

from app.domain.errors import ManualReviewRequired
from app.products.title_policy import validate_product_title


def test_accepts_approved_dp201at_title() -> None:
    title = "SUNON DP201AT-2122HBL.GN 220-240V 120mm滚珠轴承交流轴流风扇"

    assert validate_product_title(
        title=title,
        brand="SUNON",
        model="DP201AT-2122HBL.GN",
        product_name="交流轴流风扇",
    ) == title
    assert len(title) == 49


@pytest.mark.parametrize(
    "title, message",
    [
        ("SUNON " + "超" * 60, "60"),
        ("SUNON 220-240V 交流轴流风扇", "完整型号"),
        ("DP201AT-2122HBL.GN 交流轴流风扇", "品牌"),
        ("SUNON DP201AT-2122HBL.GN", "产品名称"),
        ("SUNON DP201AT-2122HBL.GN 全网最低交流轴流风扇", "无证据营销词"),
    ],
)
def test_rejects_unsafe_or_incomplete_title(title: str, message: str) -> None:
    with pytest.raises(ManualReviewRequired, match=message):
        validate_product_title(
            title=title,
            brand="SUNON",
            model="DP201AT-2122HBL.GN",
            product_name="交流轴流风扇",
        )
```

- [ ] **Step 2: Run the new test and verify RED**

Run:

```powershell
python -m pytest tests/unit/products/test_title_policy.py -q
```

Expected: import fails because `app.products.title_policy` does not exist.

- [ ] **Step 3: Implement title validation**

Create `app/products/title_policy.py`:

```python
from app.domain.errors import ManualReviewRequired

MAX_1688_TITLE_LENGTH = 60
UNSUPPORTED_MARKETING_TERMS = ("全网最低", "最好", "最佳", "顶级", "绝对", "100%")


def _compact(value: str) -> str:
    return " ".join(value.split())


def _platform_length(value: str) -> int:
    return sum(1 if character.isascii() else 2 for character in value)


def validate_product_title(
    *, title: str, brand: str, model: str, product_name: str | None
) -> str:
    clean = _compact(title)
    if not clean or _platform_length(clean) > MAX_1688_TITLE_LENGTH:
        raise ManualReviewRequired("商品标题按1688加权计数必须为1到60个字符")
    if clean.casefold().count(model.casefold()) != 1:
        raise ManualReviewRequired("商品标题必须且只能包含一次完整型号")
    if brand.casefold() not in clean.casefold():
        raise ManualReviewRequired("商品标题必须包含证据确认的品牌")
    if product_name and _compact(product_name).casefold() not in clean.casefold():
        raise ManualReviewRequired("商品标题必须包含证据确认的产品名称")
    if any(term.casefold() in clean.casefold() for term in UNSUPPORTED_MARKETING_TERMS):
        raise ManualReviewRequired("商品标题包含无证据营销词")
    return clean
```

- [ ] **Step 4: Validate at preparation and form-plan boundaries**

In `prepare_product`, validate `evidence.title` before creating the payload. In `build_form_plan`, validate loaded artifacts again so stale or manually modified JSON cannot reach Chrome:

```python
title = validate_product_title(
    title=evidence.title,
    brand=evidence.brand,
    model=normalized,
    product_name=evidence.attributes.get("产品别名"),
)
```

```python
title = validate_product_title(
    title=payload.title,
    brand=payload.brand,
    model=payload.model,
    product_name=payload.attributes.get("产品别名"),
)
```

Use the returned normalized title in `ProductPayload` and `FormPlan`.

- [ ] **Step 5: Run tests and commit**

```powershell
python -m pytest tests/unit/products/test_title_policy.py tests/unit/products/test_preparer.py tests/unit/publisher/test_form_plan.py -q
git add app/products/title_policy.py app/products/preparer.py app/publisher/form_plan.py tests/unit/products/test_title_policy.py
git commit -m "feat: validate evidence-backed 1688 titles"
```

Expected: all focused tests pass.

---

### Task 3: Make the one-SKU plan explicit and verify the real 1688 module

**Files:**
- Modify: `app/publisher/form_plan.py:15-66`
- Modify: `app/publisher/playwright_port.py:530-670`
- Modify: `tests/unit/publisher/test_form_plan.py`
- Modify: `tests/unit/publisher/test_playwright_port_contract.py`

- [ ] **Step 1: Write failing single-SKU plan tests**

Update the form-plan test to assert named values instead of tuple positions:

```python
plan = build_form_plan(payload)

assert plan.minimum_order_quantity == "1"
assert plan.price == "10000"
assert plan.sku.model == "DP201AT-2122HBL.GN"
assert plan.sku.stock == "10"
assert plan.sku.item_code == "DP201AT-2122HBL.GN"
assert plan.sku.enabled is True
assert [field.value for field in plan.spec_fields] == [
    "DP201AT-2122HBL.GN",
    "18/16.5",
    "0.119",
    "2150/2500",
    "112.1/135.9",
    "0.09/0.09",
    "0.295",
]
```

Add a contract assertion that `fill_product` requires exactly two visible SKU inputs and verifies the model text in `#guid-skuTable`.

- [ ] **Step 2: Run focused tests and verify RED**

```powershell
python -m pytest tests/unit/publisher/test_form_plan.py tests/unit/publisher/test_playwright_port_contract.py -q
```

Expected: `FormPlan` has no named `sku`, `price`, or `minimum_order_quantity` fields.

- [ ] **Step 3: Replace positional sales values with explicit dataclasses**

```python
@dataclass(frozen=True)
class SkuPlan:
    model: str
    stock: str
    item_code: str
    enabled: bool = True


@dataclass(frozen=True)
class FormPlan:
    category_url: str
    title: str
    attribute_fields: tuple[FormField, ...]
    spec_fields: tuple[FormField, ...]
    minimum_order_quantity: str
    price: str
    sku: SkuPlan
    delivery_time: str
    shipping_template: str
    package_values: tuple[str, ...]
```

Build the sales portion as:

```python
minimum_order_quantity="1",
price=str(payload.price),
sku=SkuPlan(
    model=payload.model,
    stock=str(payload.stock),
    item_code=payload.model,
),
```

- [ ] **Step 4: Verify the current page contract while filling**

Replace positional `sales_values` use in `fill_product` with named fields. Before filling, require the current title field to report `maxlength="60"`. After specification fields are synchronized, require one visible SKU row whose module text contains the exact model, then fill only stock and item code:

```python
title_field = self.page.locator('input[placeholder^="建议使用通俗的产品名称"]')
if await title_field.get_attribute("maxlength") != "60":
    raise ManualReviewRequired("1688 title field no longer exposes maxlength=60")
await _fill_and_verify(title_field, plan.title, label="product title")

sku_module = self.page.locator("#guid-skuTable")
sku_inputs = sku_module.locator('input[placeholder="请输入"]:visible')
if await sku_inputs.count() != 2:
    raise ManualReviewRequired("single-SKU table no longer exposes stock and item-code inputs")
if plan.sku.model not in " ".join((await sku_module.inner_text()).split()):
    raise ManualReviewRequired("single-SKU model is not synchronized from product specification")
await _fill_and_verify(sku_inputs.nth(0), plan.sku.stock, label="stock")
await _fill_and_verify(sku_inputs.nth(1), plan.sku.item_code, label="item code")
```

Do not create a second SKU row for slash-separated 50/60Hz values.

- [ ] **Step 5: Run tests and commit**

```powershell
python -m pytest tests/unit/publisher/test_form_plan.py tests/unit/publisher/test_playwright_port_contract.py tests/unit/publisher/test_sparse_form_fill.py -q
git add app/publisher/form_plan.py app/publisher/playwright_port.py tests/unit/publisher/test_form_plan.py tests/unit/publisher/test_playwright_port_contract.py tests/unit/publisher/test_sparse_form_fill.py
git commit -m "feat: enforce one exact-model SKU"
```

Expected: focused tests pass and no slash value appears in `SkuPlan.model` or `SkuPlan.item_code`.

---

### Task 4: Load the approved detail policy and fixed company tail from one source

**Files:**
- Modify: `config/detail_templates.yaml`
- Create: `app/products/detail_policy.py`
- Create: `tests/unit/products/test_detail_policy.py`
- Modify: `tests/artifacts/test_a2e250_geo_detail.py`

- [ ] **Step 1: Write failing policy tests**

```python
from app.products.detail_policy import load_detail_policy


def test_detail_policy_has_approved_sections_and_fixed_company_tail() -> None:
    policy = load_detail_policy()

    assert policy.editor_width_px == 790
    assert policy.current_product_image_count == 4
    assert policy.company_heading == "公司介绍与服务能力"
    assert len(policy.company_image_urls) == 6
    assert len(set(policy.company_image_urls)) == 6
    assert policy.sections[-1] == "company"
    assert policy.company_image_urls[0].endswith("?__r__=1693301896729")
    assert "O1CN01ZNKz0m1fBqloyuUox" in policy.company_image_urls[-1]
```

Replace the artifact test's dependency on ignored `automation/A2E250-AL06-01/detail.html` with policy assertions and renderer fixtures. Fresh clones must not require local business artifacts to run tests.

- [ ] **Step 2: Run tests and verify RED**

```powershell
python -m pytest tests/unit/products/test_detail_policy.py tests/artifacts/test_a2e250_geo_detail.py -q
```

Expected: the new module is missing and the artifact test still reads ignored runtime HTML.

- [ ] **Step 3: Update YAML with the exact policy**

Keep existing style and sync rules, replace section order, and add:

```yaml
geo_detail:
  editor_width_px: 790
  sections:
    - entity_answer
    - quick_facts
    - core_parameters
    - operating_points
    - product_images
    - dimensions_installation
    - materials_electrical_environment
    - purchase_confirmation
    - faq
    - company
  image_policy:
    current_product_required_count: 4
    reject_duplicate_urls: true
    alt_template: "{brand} {model} {image_role}"
  fixed_company_tail:
    heading: "公司介绍与服务能力"
    urls:
      - "https://cbu01.alicdn.com/img/ibank/O1CN010sBWhU1fBqlsKUVbG_!!994523969-0-cib.jpg?__r__=1693301896729"
      - "https://cbu01.alicdn.com/img/ibank/O1CN01UVqBIt1fBqlv65Ixg_!!994523969-0-cib.jpg?__r__=1693301896729"
      - "https://cbu01.alicdn.com/img/ibank/O1CN01imkZdi1fBqltEYrTI_!!994523969-0-cib.jpg?__r__=1693301896730"
      - "https://cbu01.alicdn.com/img/ibank/O1CN01cgSKSM1fBqloqCSiQ_!!994523969-0-cib.jpg?__r__=1693301896730"
      - "https://cbu01.alicdn.com/img/ibank/O1CN01w56XvA1fBqrEhuILX_!!994523969-0-cib.jpg?__r__=1693301896730"
      - "https://cbu01.alicdn.com/img/ibank/O1CN01ZNKz0m1fBqloyuUox_!!994523969-0-cib.jpg?__r__=1693301896730"
```

- [ ] **Step 4: Implement strict policy loading**

Create `app/products/detail_policy.py`:

```python
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.errors import ManualReviewRequired


class DetailPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    editor_width_px: int = Field(gt=0)
    sections: tuple[str, ...]
    current_product_image_count: int = Field(gt=0)
    company_heading: str
    company_image_urls: tuple[str, ...]

    @field_validator("company_image_urls")
    @classmethod
    def validate_company_urls(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != 6 or len(set(values)) != 6:
            raise ValueError("exactly six distinct company images are required")
        if any(not value.startswith("https://cbu01.alicdn.com/img/ibank/") for value in values):
            raise ValueError("company images must use approved 1688 hosting")
        return values


@lru_cache(maxsize=1)
def load_detail_policy() -> DetailPolicy:
    path = Path(__file__).resolve().parents[2] / "config" / "detail_templates.yaml"
    try:
        loaded: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
        geo = loaded["geo_detail"]
        image_policy = geo["image_policy"]
        company = geo["fixed_company_tail"]
        return DetailPolicy(
            editor_width_px=geo["editor_width_px"],
            sections=tuple(geo["sections"]),
            current_product_image_count=image_policy["current_product_required_count"],
            company_heading=company["heading"],
            company_image_urls=tuple(company["urls"]),
        )
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise ManualReviewRequired(f"detail policy is invalid: {path}") from error
```

- [ ] **Step 5: Run tests and commit**

```powershell
python -m pytest tests/unit/products/test_detail_policy.py tests/artifacts/test_a2e250_geo_detail.py -q
git add config/detail_templates.yaml app/products/detail_policy.py tests/unit/products/test_detail_policy.py tests/artifacts/test_a2e250_geo_detail.py
git commit -m "feat: define fixed company detail tail"
```

Expected: tests pass without reading any ignored `automation/` path.

---

### Task 5: Replace the four-section image stack with the approved adaptive GEO document

**Files:**
- Modify: `app/products/geo_detail.py`
- Modify: `tests/unit/products/test_geo_detail.py`

- [ ] **Step 1: Replace old expectations with rich and sparse renderer tests**

The rich fixture must use the approved DP201AT evidence and assert exact section order, 11 unique images, product-photo alts, company-tail alts, and key facts:

```python
document = render_geo_detail(
    payload=dp201at_payload,
    drawing_url="https://example.com/drawing.jpg",
    image_urls=[f"https://example.com/product-{index}.jpg" for index in range(4)],
    image_roles=["铭牌侧整机", "铭牌侧视图", "叶轮侧视图", "侧面与引线"],
)
soup = BeautifulSoup(document.html, "html.parser")

assert [node["data-geo-section"] for node in soup.select("[data-geo-section]")] == [
    "entity-answer",
    "quick-facts",
    "core-parameters",
    "operating-points",
    "product-images",
    "dimensions-installation",
    "materials-electrical-environment",
    "purchase-confirmation",
    "faq",
    "company",
]
assert document.image_count == 11
assert tuple(image["src"] for image in soup.select("img")) == document.image_sources
assert len(set(document.image_sources)) == 11
assert soup.select("[data-geo-section='company']")[-1] == soup.select("[data-geo-section]")[-1]
assert [image["alt"] for image in soup.select("[data-geo-section='company'] img")] == [
    f"公司介绍与服务能力 {index}" for index in range(1, 7)
]
for text in (
    "DP201AT-2122HBL.GN",
    "220-240VAC",
    "66CFM / 112.1m³/h",
    "80CFM / 135.9m³/h",
    "119±0.5mm",
    "25.5±0.5mm",
    "104.8±0.3mm",
    "320±10mm",
):
    assert text in document.html
```

Keep the existing sparse and escaping tests, but update them to read `document.html`. Sparse data must omit unsupported optional sections/rows while still rendering the current product images, dimension drawing, and fixed company tail. Add a Delta payload test proving product sections contain Delta only; the approved company images remain confined to the final company section.

- [ ] **Step 2: Run renderer tests and verify RED**

```powershell
python -m pytest tests/unit/products/test_geo_detail.py -q
```

Expected: current renderer returns `str`, has only four sections, and contains five images.

- [ ] **Step 3: Add a rendered-document contract**

At the top of `geo_detail.py` add:

```python
from dataclasses import dataclass

from app.products.detail_policy import DetailPolicy, load_detail_policy


@dataclass(frozen=True)
class RenderedDetail:
    html: str
    image_sources: tuple[str, ...]

    @property
    def image_count(self) -> int:
        return len(self.image_sources)
```

Expand `SPEC_META` and unit aliases for the evidenced fields used by the approved page: `启动电压_v`, `安全电流_a`, `存储温度_c`, `尺寸_mm`, `外框宽度_mm`, `厚度_mm`, `安装孔距_mm`, `安装孔`, `引线长度_mm`, `叶轮材质`, `引线规格`, `气流方向`, `旋转方向`, `安装方向`, and `认证`.

- [ ] **Step 4: Add reusable section and operating-point renderers**

Use escaped inline HTML only:

```python
def _section(slug: str, title: str, body: str, *, alternate: bool = False) -> str:
    background = "#f6f8fb" if alternate else "#ffffff"
    return (
        f'<section data-geo-section="{escape(slug, quote=True)}" '
        f'style="padding:20px 16px;background:{background};border-bottom:1px solid #d8d8d8">'
        f"{_heading(title)}{body}</section>"
    )


def _operating_point_table(payload: ProductPayload) -> str:
    headers = "".join(
        f'<th style="padding:10px;border:1px solid #d8d8d8;background:#0b3a70;color:#fff">{escape(value)}</th>'
        for value in ("频率", "转速", "风量", "最大静压", "电流", "功率", "噪声")
    )
    body = "".join(
        "<tr>"
        + "".join(
            f'<td style="padding:10px;border:1px solid #d8d8d8">{escape(value)}</td>'
            for value in (
                f"{point.frequency_hz}Hz",
                f"{point.speed_rpm:g}RPM" if point.speed_rpm is not None else "—",
                (
                    f"{point.airflow_cfm:g}CFM / {point.airflow_m3h:g}m³/h"
                    if point.airflow_cfm is not None and point.airflow_m3h is not None
                    else "—"
                ),
                (
                    f"{point.static_pressure_in_h2o:g}inH₂O"
                    if point.static_pressure_in_h2o is not None
                    else "—"
                ),
                f"{point.current_a:g}A" if point.current_a is not None else "—",
                f"{point.power_w:g}W" if point.power_w is not None else "—",
                f"{point.noise_db_a:g}dB(A)" if point.noise_db_a is not None else "—",
            )
        )
        + "</tr>"
        for point in payload.operating_points
    )
    return f'<table style="width:100%;border-collapse:collapse"><thead><tr>{headers}</tr></thead><tbody>{body}</tbody></table>'


def _selected_rows(payload: ProductPayload, keys: tuple[str, ...]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for key in keys:
        value = payload.specification.get(key)
        if value is None or not _is_present(value):
            continue
        label, unit = _spec_label_and_unit(key)
        rows.append(
            (label, _value_with_unit(value, unit, SPEC_UNIT_ALIASES.get(key, ())))
        )
    return rows


def _product_image_grid(prefix: str, urls: list[str], roles: list[str]) -> str:
    cells = [
        (
            '<td style="width:50%;padding:6px;vertical-align:top">'
            f'<img src="{escape(url, quote=True)}" alt="{escape(f"{prefix} {role}", quote=True)}" '
            'style="display:block;width:100%;height:auto" />'
            f'<p style="margin:6px 0 0;text-align:center">{escape(role)}</p></td>'
        )
        for url, role in zip(urls, roles, strict=True)
    ]
    return (
        '<table style="width:100%;border-collapse:collapse"><tbody>'
        f"<tr>{cells[0]}{cells[1]}</tr><tr>{cells[2]}{cells[3]}</tr>"
        "</tbody></table>"
    )


def _purchase_confirmation(payload: ProductPayload) -> str:
    rows = [("完整型号", payload.model)]
    rows.extend(
        _selected_rows(payload, ("额定电压_v", "频率_hz", "尺寸_mm", "安装孔距_mm"))
    )
    return _table(rows)


def _faq(payload: ProductPayload) -> str:
    answers = [
        (
            "如何确认型号？",
            f"请核对品牌 {payload.brand} 和完整型号 {payload.model}，不要按相近后缀替代。",
        )
    ]
    if {point.frequency_hz for point in payload.operating_points} == {50, 60}:
        answers.append(
            (
                "斜杠参数如何理解？",
                "规格中的前值对应50Hz工作点，后值对应60Hz工作点；它们属于同一SKU。",
            )
        )
    dimensions = _selected_rows(payload, ("尺寸_mm", "安装孔距_mm", "厚度_mm"))
    if dimensions:
        summary = "；".join(f"{label}：{value}" for label, value in dimensions)
        answers.append(("安装前需要核对什么？", summary))
    return "".join(
        '<div style="margin:0 0 14px">'
        f'<h3 style="margin:0 0 5px;font-size:16px;color:#0b3a70">{escape(question)}</h3>'
        f'<p style="margin:0">{escape(answer)}</p></div>'
        for question, answer in answers
    )


def _validate(
    payload: ProductPayload,
    drawing_url: str,
    image_urls: list[str],
    image_roles: list[str],
    policy: DetailPolicy,
) -> None:
    current_sources = [drawing_url, *image_urls]
    all_sources = [*image_urls, drawing_url, *policy.company_image_urls]
    if (
        len(image_urls) != policy.current_product_image_count
        or len(image_roles) != policy.current_product_image_count
        or any(not value.strip() for value in current_sources)
        or any(not role.strip() for role in image_roles)
        or len(all_sources) != len(set(all_sources))
        or not policy.sections
        or policy.sections[-1] != "company"
    ):
        raise ManualReviewRequired("GEO detail image and section policy is not satisfied")
    specification_model = payload.specification.get("规格型号")
    if not _is_present(specification_model) or not exact_model_match(
        str(specification_model), payload.model
    ):
        raise ManualReviewRequired("detail specification model does not match payload model")
```

- [ ] **Step 5: Render sections in the approved order and append the fixed tail**

Rewrite `render_geo_detail` to return `RenderedDetail`. The body must be assembled in this order and optional tables must be omitted when their row lists are empty:

```python
def render_geo_detail(
    *,
    payload: ProductPayload,
    drawing_url: str,
    image_urls: list[str],
    image_roles: list[str],
    policy: DetailPolicy | None = None,
) -> RenderedDetail:
    active_policy = policy or load_detail_policy()
    _validate(payload, drawing_url, image_urls, image_roles, active_policy)
    prefix = f"{payload.brand} {payload.model}"
    product_name = payload.attributes.get("产品别名") or payload.attributes.get("类型")
    identity = f"这是 {prefix}{(' ' + product_name) if product_name else ''}。"
    quick_rows = _selected_rows(
        payload,
        ("额定电压_v", "频率_hz", "尺寸_mm", "轴承系统", "重量_kg"),
    )
    dimension_rows = _selected_rows(
        payload,
        (
            "外框宽度_mm",
            "厚度_mm",
            "安装孔距_mm",
            "安装孔",
            "引线长度_mm",
            "气流方向",
            "旋转方向",
            "安装方向",
        ),
    )
    technical_rows = _selected_rows(
        payload,
        (
            "框体材质",
            "叶轮材质",
            "引线规格",
            "电压范围_v",
            "启动电压_v",
            "安全电流_a",
            "电机保护",
            "绝缘等级",
            "工作温度_c",
            "存储温度_c",
            "认证",
        ),
    )
    product_images = _product_image_grid(prefix, image_urls, image_roles)
    sections = [
        _section("entity-answer", "型号确认", f"<p>{escape(identity)}</p>"),
    ]
    if quick_rows:
        sections.append(_section("quick-facts", "快速确认", _table(quick_rows), alternate=True))
    sections.append(_section("core-parameters", "核心参数", _table(_parameter_rows(payload))))
    if payload.operating_points:
        sections.append(
            _section("operating-points", "50/60Hz 工作点对照", _operating_point_table(payload), alternate=True)
        )
    sections.append(_section("product-images", "实物与铭牌核对", product_images))
    dimension_body = _image(drawing_url, f"{prefix} 尺寸图")
    if dimension_rows:
        dimension_body += _table(dimension_rows)
    sections.append(_section("dimensions-installation", "尺寸、安装与气流方向", dimension_body, alternate=True))
    if technical_rows:
        sections.append(_section("materials-electrical-environment", "材料、电气与环境信息", _table(technical_rows)))
    sections.append(_section("purchase-confirmation", "采购前核对", _purchase_confirmation(payload), alternate=True))
    sections.append(_section("faq", "常见问题", _faq(payload)))
    company_images = "".join(
        _image(url, f"{active_policy.company_heading} {index}")
        for index, url in enumerate(active_policy.company_image_urls, start=1)
    )
    sections.append(_section("company", active_policy.company_heading, company_images, alternate=True))
    html = (
        f'<div style="width:100%;max-width:{active_policy.editor_width_px}px;margin:0 auto;'
        'font-family:arial,microsoft yahei,sans-serif;'
        'color:#222;background:#fff;line-height:1.75;font-size:14px">'
        + "".join(sections)
        + "</div>"
    )
    return RenderedDetail(
        html=html,
        image_sources=tuple([*image_urls, drawing_url, *active_policy.company_image_urls]),
    )
```

The helpers above use only `payload.brand`, `payload.model`, present attributes/specifications, and operating points. Keep that boundary: do not add application claims, warranties, stock claims, certifications, or similar-model data.

- [ ] **Step 6: Run renderer tests and commit**

```powershell
python -m pytest tests/unit/products/test_geo_detail.py tests/unit/products/test_detail_policy.py -q
git add app/products/geo_detail.py tests/unit/products/test_geo_detail.py
git commit -m "feat: render adaptive GEO product details"
```

Expected: rich and sparse tests pass; rich DP output has 11 unique images and the company section is last.

---

### Task 6: Carry the dynamic image manifest through synchronization, quality, and task state

**Files:**
- Modify: `app/publisher/orchestrator.py`
- Modify: `app/publisher/playwright_port.py`
- Modify: `app/publisher/quality.py`
- Modify: `app/cli.py`
- Modify: `tests/unit/publisher/test_orchestrator.py`
- Modify: `tests/unit/publisher/test_quality.py`
- Modify: `tests/unit/test_cli_run.py`
- Modify: `plugins/auto-alibaba/skills/upload-1688-products/scripts/inspect_session.py`

- [ ] **Step 1: Write failing manifest tests**

Update the recording port so quality receives exact image sources. Assert the uploader passes 11 to editor sync, passes the same ordered tuple to quality, and returns it in `UploadResult`.

Add quality tests:

```python
def test_quality_parser_requires_exact_ordered_image_manifest() -> None:
    expected = tuple(f"https://example.com/{index}.jpg" for index in range(11))
    html = "".join(f'<img src="{source}">' for source in expected)

    result = parse_quality_check(
        ui_text="错误(0)",
        response={"data": {"data": {"qualityInfos": []}}},
        form_values={"description": {"detailList": [{"content": html}]}},
        expected_image_sources=expected,
    )

    assert result["errors"] == 0


def test_quality_parser_rejects_reordered_company_tail() -> None:
    expected = tuple(f"https://example.com/{index}.jpg" for index in range(11))
    actual = (*expected[:-2], expected[-1], expected[-2])
    html = "".join(f'<img src="{source}">' for source in actual)

    with pytest.raises(ManualReviewRequired, match="manifest"):
        parse_quality_check(
            ui_text="错误(0)",
            response={"data": {"data": {"qualityInfos": []}}},
            form_values={"description": {"detailList": [{"content": html}]}},
            expected_image_sources=expected,
        )
```

Update the task-state test to expect `template_version="geo-evidence-v3"`, `image_count=11`, and `image_sources`.

- [ ] **Step 2: Run focused tests and verify RED**

```powershell
python -m pytest tests/unit/publisher/test_orchestrator.py tests/unit/publisher/test_quality.py tests/unit/test_cli_run.py -q
```

Expected: renderer return type, quality signature, and task-state schema do not match.

- [ ] **Step 3: Propagate `RenderedDetail` through the uploader**

Change the protocol and result:

```python
async def quality_check(
    self, *, expected_image_sources: tuple[str, ...]
) -> dict[str, object]: ...


@dataclass(frozen=True)
class UploadResult:
    model: str
    errors: int
    advice: tuple[str, ...]
    ready_to_save: bool
    detail_drawing_url: str
    detail_html_path: Path
    detail_image_count: int
    detail_image_sources: tuple[str, ...]
    error_details: tuple[dict[str, str], ...] = ()
```

In `ProductUploader.run`:

```python
document = render_geo_detail(
    payload=product.payload,
    drawing_url=drawing_url,
    image_urls=hosted_urls,
    image_roles=[image.role for image in product.images],
)
temporary.write_text(document.html, encoding="utf-8")
temporary.replace(detail_path)
await self._port.inject_detail(document.html, expected_image_count=document.image_count)
quality = await self._port.quality_check(expected_image_sources=document.image_sources)
```

Return `detail_image_count=document.image_count` and `detail_image_sources=document.image_sources`.

- [ ] **Step 4: Make quality validation exact and dynamic**

Add `expected_image_sources` to `parse_quality_check` and replace the old minimum-five rule:

```python
sources = tuple(re.findall(r"<img\b[^>]*\bsrc=[\"']([^\"']+)", content, flags=re.I))
if len(sources) != len(set(sources)):
    raise ManualReviewRequired("description image sources must be unique")
if sources != expected_image_sources:
    raise ManualReviewRequired("description image manifest does not match rendered detail")
```

Update `Playwright1688Port.quality_check` to accept the tuple and pass it to the parser. Keep the existing `description != "null"` and platform error parsing.

- [ ] **Step 5: Record and validate schema v3 without hardcoded image counts**

In `build_task_state`:

```python
"detail": {
    "template_version": "geo-evidence-v3",
    "local_html": str(result.detail_html_path),
    "drawing_url": result.detail_drawing_url,
    "image_count": result.detail_image_count,
    "image_sources": list(result.detail_image_sources),
},
```

In the repository Skill's `inspect_session.py`, replace `image_count == 5` with:

```python
image_count = detail.get("image_count")
image_sources = detail.get("image_sources")
valid_images = (
    isinstance(image_count, int)
    and isinstance(image_sources, list)
    and all(isinstance(item, str) and bool(item.strip()) for item in image_sources)
    and image_count == len(image_sources)
    and image_count == len(set(image_sources))
    and image_count >= 5
)
```

Require `detail.get("template_version") == "geo-evidence-v3"` and `valid_images` in the return expression.

- [ ] **Step 6: Run tests and commit**

```powershell
python -m pytest tests/unit/publisher/test_orchestrator.py tests/unit/publisher/test_quality.py tests/unit/publisher/test_playwright_port_contract.py tests/unit/test_cli_run.py -q
git add app/publisher/orchestrator.py app/publisher/playwright_port.py app/publisher/quality.py app/cli.py tests/unit/publisher/test_orchestrator.py tests/unit/publisher/test_quality.py tests/unit/publisher/test_playwright_port_contract.py tests/unit/test_cli_run.py plugins/auto-alibaba/skills/upload-1688-products/scripts/inspect_session.py
git commit -m "feat: validate dynamic detail image manifests"
```

Expected: focused tests pass and no production code contains `expected_image_count=5` or `detail_image_count=5`.

---

### Task 7: Update the distributable upload Skill, stale-artifact detection, and album regressions

**Files:**
- Modify: `plugins/auto-alibaba/skills/upload-1688-products/SKILL.md`
- Modify: `plugins/auto-alibaba/skills/upload-1688-products/scripts/run_upload.py`
- Modify: `plugins/auto-alibaba/.codex-plugin/plugin.json`
- Modify: `tests/unit/test_run_upload.py`
- Modify: `tests/unit/test_upload_skill_contract.py`
- Modify: `tests/unit/publisher/test_album_picker.py`
- Modify after repository verification: installed Skill under `$env:USERPROFILE\.codex\skills\upload-1688-products`

- [ ] **Step 1: Write failing stale-artifact and Skill contract tests**

```python
def test_prepared_artifacts_are_stale_when_evidence_is_newer(tmp_path: Path) -> None:
    module = _load_run_upload()
    artifacts = tmp_path / "automation" / "DP201AT-2122HBL.GN"
    artifacts.mkdir(parents=True)
    evidence = artifacts / "preparation_evidence.json"
    evidence.write_text("{}", encoding="utf-8")
    for name in ("1688_payload.json", "image_analysis.json", "detail_assets.json"):
        path = artifacts / name
        path.write_text("{}", encoding="utf-8")
        path.touch()
    future = evidence.stat().st_mtime + 10
    os.utime(evidence, (future, future))

    assert module.prepared_artifacts_complete(tmp_path, "DP201AT-2122HBL.GN") is False
```

The Skill contract must assert it documents all of these exact behaviors:

- only PDF, real photos, and Excel price/stock are operator inputs;
- title is evidence-authored, at most 60 characters, and contains brand/full model/product name;
- 50/60Hz slash values stay in product specifications, not SKU names;
- fixed six company images are appended to every brand detail;
- `READY_TO_SAVE` reports the dynamic image count;
- brand album rollover creates only the next same-brand number and retries once;
- never save or publish.

- [ ] **Step 2: Run focused tests and verify RED**

```powershell
python -m pytest tests/unit/test_run_upload.py tests/unit/test_upload_skill_contract.py tests/unit/publisher/test_album_picker.py -q
```

Expected: stale artifacts are treated as complete and the repository Skill still reports five detail images.

- [ ] **Step 3: Reprepare when evidence is newer**

Replace `prepared_artifacts_complete` with:

```python
def prepared_artifacts_complete(root: Path, folder_key: str) -> bool:
    artifacts = root / "automation" / folder_key
    evidence = artifacts / "preparation_evidence.json"
    outputs = tuple(
        artifacts / name
        for name in ("1688_payload.json", "image_analysis.json", "detail_assets.json")
    )
    if not evidence.is_file() or not all(path.is_file() for path in outputs):
        return False
    return all(path.stat().st_mtime_ns >= evidence.stat().st_mtime_ns for path in outputs)
```

- [ ] **Step 4: Merge the approved behavior into the repository Skill**

Use the currently installed Skill's multi-brand/operator-input rules as the baseline, then add the approved title, operating-point, single-SKU, adaptive-detail, fixed-tail, dynamic-count, and evidence-freshness rules. Remove the sentence that requires reporting “详情图为5张”. Do not introduce machine-specific absolute paths.

Keep the upload entry command unchanged:

```powershell
python "<SKILL_DIR>\scripts\run_upload.py" --root "<PROJECT_ROOT>" --model "<MODEL>" --cdp-url "http://127.0.0.1:9223"
```

- [ ] **Step 5: Preserve album rollover behavior with regression tests**

Keep the existing tests for first album creation, highest same-brand selection, one rollover, and blocking when the new album is also full. Add a case proving `Delta(99)` never affects the next SUNON album and a case-insensitive strict match does not accept `SUNON (03)` or `SUNON风扇(03)`.

- [ ] **Step 6: Bump the plugin cachebuster and run distribution tests**

Set `plugins/auto-alibaba/.codex-plugin/plugin.json` version to `0.1.0+codex.<current YYYYMMDDHHMMSS>` and run:

```powershell
python -m pytest tests/unit/test_run_upload.py tests/unit/test_upload_skill_contract.py tests/unit/test_distribution_contract.py tests/unit/publisher/test_album_policy.py tests/unit/publisher/test_album_picker.py -q
git add plugins/auto-alibaba tests/unit/test_run_upload.py tests/unit/test_upload_skill_contract.py tests/unit/publisher/test_album_picker.py
git commit -m "feat: update GEO upload skill contract"
```

Expected: tests pass, plugin paths remain relative, and no original-machine path enters tracked files.

- [ ] **Step 7: Synchronize the verified repository Skill into the active installation**

After the commit passes, copy only the verified skill bundle and compare hashes:

```powershell
$source = Resolve-Path 'plugins\auto-alibaba\skills\upload-1688-products'
$target = Join-Path $env:USERPROFILE '.codex\skills\upload-1688-products'
Copy-Item -Path (Join-Path $source '*') -Destination $target -Recurse -Force
$repoHash = (Get-FileHash -Algorithm SHA256 (Join-Path $source 'scripts\run_upload.py')).Hash
$installedHash = (Get-FileHash -Algorithm SHA256 (Join-Path $target 'scripts\run_upload.py')).Hash
if ($repoHash -ne $installedHash) { throw 'installed upload Skill did not match repository source' }
```

Also compare `SKILL.md` and `scripts/inspect_session.py`. This synchronization is an installation step, not a repository commit.

---

### Task 8: Rebuild DP201AT evidence, verify the whole repository, and fill the real page to `READY_TO_SAVE`

**Files:**
- Local runtime only: `automation/DP201AT-2122HBL.GN/preparation_evidence.json`
- Generated local runtime only: `automation/DP201AT-2122HBL.GN/1688_payload.json`
- Generated local runtime only: `automation/DP201AT-2122HBL.GN/detail.html`
- Generated local runtime only: `automation/DP201AT-2122HBL.GN/task_state.json`
- No tracked production file should change in this task.

- [ ] **Step 1: Update the ignored evidence artifact with approved facts**

Keep the existing PDF, image roles, crop, package, and attributes, and change/add these exact fields:

```json
{
  "title": "SUNON DP201AT-2122HBL.GN 220-240V 120mm滚珠轴承交流轴流风扇",
  "specification": {
    "规格型号": "DP201AT-2122HBL.GN",
    "额定电压_v": "220-240",
    "电压范围_v": "185-245",
    "启动电压_v": 185,
    "频率_hz": "50/60",
    "风叶直径_m": 0.119,
    "尺寸_mm": "120×120×25",
    "外框宽度_mm": "119±0.5",
    "厚度_mm": "25.5±0.5",
    "安装孔距_mm": "104.8±0.3",
    "安装孔": "8-Ø4.3mm",
    "引线长度_mm": "320±10",
    "安全电流_a": "0.10/0.09",
    "电机保护": "阻抗保护",
    "绝缘等级": "B级",
    "框体材质": "压铸铝",
    "叶轮材质": "PBT热塑性塑料（UL94V-0）",
    "轴承系统": "精密滚珠轴承",
    "引线规格": "UL3266 24AWG 灰色",
    "工作温度_c": "-10~+70",
    "存储温度_c": "-40~+70",
    "气流方向": "朝向标签侧",
    "旋转方向": "从叶轮正面观察为逆时针",
    "安装方向": "任意方向",
    "认证": "UL/CUR/TUV/CE/UKCA",
    "重量_kg": 0.295
  },
  "operating_points": [
    {
      "frequency_hz": 50,
      "speed_rpm": 2150,
      "airflow_cfm": 66,
      "static_pressure_in_h2o": 0.14,
      "current_a": 0.09,
      "power_w": 18,
      "noise_db_a": 44
    },
    {
      "frequency_hz": 60,
      "speed_rpm": 2500,
      "airflow_cfm": 80,
      "static_pressure_in_h2o": 0.17,
      "current_a": 0.09,
      "power_w": 16.5,
      "noise_db_a": 48
    }
  ]
}
```

Do not add facts absent from PDF pages 3 and 5 or the current model photos.

- [ ] **Step 2: Reprepare and inspect generated payload**

```powershell
python -m app.cli prepare 'DP201AT-2122HBL.GN' --root 'D:\Auto-Alibaba'
$payload = Get-Content -Raw -Encoding utf8 'automation\DP201AT-2122HBL.GN\1688_payload.json' | ConvertFrom-Json
if ($payload.title.Length -ne 49) { throw 'unexpected title length' }
if ($payload.specification.风量_m3h -ne '112.1/135.9') { throw 'airflow conversion mismatch' }
if ($payload.operating_points.Count -ne 2) { throw 'operating points missing' }
```

Expected: `PREPARED`, stock remains `10`, price remains sourced from Excel, and the seven platform specification values match the approved design.

- [ ] **Step 3: Run complete offline verification**

```powershell
python -m pytest -q
python -m ruff check .
python -m mypy app
```

Expected: all tests pass, Ruff exits 0, and mypy exits 0. Run `git status --short` and confirm only already-known user files or intentionally committed changes remain; do not add `.superpowers/`, local configs, Excel lock files, `automation/`, or `data/`.

- [ ] **Step 4: Run only the bundled upload wrapper**

```powershell
python "$env:USERPROFILE\.codex\skills\upload-1688-products\scripts\run_upload.py" --root 'D:\Auto-Alibaba' --model 'DP201AT-2122HBL.GN' --cdp-url 'http://127.0.0.1:9223'
```

Expected final JSON: `ok=true`, `status="READY_TO_SAVE"`, `quality_errors=0`. The command may reuse the four current-model main images only when the existing media fingerprint matches. It may create a new `SUNON(NN)` album only after an explicit full-capacity response and may retry once.

- [ ] **Step 5: Verify final task state without saving**

```powershell
$state = Get-Content -Raw -Encoding utf8 'automation\DP201AT-2122HBL.GN\task_state.json' | ConvertFrom-Json
if ($state.status -ne 'READY_TO_SAVE') { throw 'upload is not ready' }
if ($state.quality_check.errors -ne 0) { throw 'quality errors remain' }
if ($state.detail.template_version -ne 'geo-evidence-v3') { throw 'wrong detail schema' }
if ($state.detail.image_count -ne 11) { throw 'expected 11 detail images' }
if ($state.detail.image_sources.Count -ne 11) { throw 'image manifest is incomplete' }
$tail = @($state.detail.image_sources | Select-Object -Last 6)
$expectedIds = @(
    'O1CN010sBWhU1fBqlsKUVbG',
    'O1CN01UVqBIt1fBqlv65Ixg',
    'O1CN01imkZdi1fBqltEYrTI',
    'O1CN01cgSKSM1fBqloqCSiQ',
    'O1CN01w56XvA1fBqrEhuILX',
    'O1CN01ZNKz0m1fBqloyuUox'
)
for ($index = 0; $index -lt 6; $index++) {
    if ($tail[$index] -notmatch $expectedIds[$index]) { throw 'fixed company tail is missing or reordered' }
}
```

Inspect the dedicated Chrome page only to confirm the visible title, seven product specifications, one exact-model SKU, full detail, zero blocking errors, and the “保存草稿” boundary. Do not click that button.

- [ ] **Step 6: Report the verified outcome**

Report the exact title, SKU model, seven specification values, detail image count, quality error count, and `READY_TO_SAVE` status. State explicitly that the page stopped before save and publish. Do not claim completion if any offline check, form verification, image manifest, or quality check failed.

---

## Plan self-review checklist

- Evidence-only input and missing-field omission: Tasks 1, 2, 5, and 8.
- Exact 49-character title at 59/60 under 1688's weighted limit: Tasks 2, 3, and 8.
- Single exact-model SKU and slash values kept as 50/60Hz specifications: Tasks 1 and 3.
- Seven approved current product specification values: Tasks 1, 3, and 8.
- Adaptive answer-first GEO modules: Task 5.
- Four real model photos, one drawing, six fixed company images: Tasks 4, 5, 6, and 8.
- Fixed company tail used for every brand but excluded from product evidence: Tasks 4 and 5.
- Dynamic image count and ordered manifest: Task 6.
- Same-brand album rollover and one retry: Task 7.
- Stale evidence forces reprepare: Task 7.
- Dedicated Chrome, wrapper-only execution, and no save/publish: Task 8.
- No placeholders, undefined task references, or unmatched method signatures remain in this plan.
