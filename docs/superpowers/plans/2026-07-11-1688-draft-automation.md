# 1688 Fan Draft Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows-local Python CLI that converts one model folder plus the matching Excel row into an evidence-bound 1688 product payload, fills the verified seven-section merchant form in a logged-in Chrome session, and can only save a draft.

**Architecture:** A four-stage pipeline separates ingestion, local Codex extraction, deterministic payload/GEO generation, and Playwright publishing. Pydantic contracts are the only boundary objects; raw PDFs and images never cross into the browser layer. A persistent state machine, incident bundles, domain guard, and exact draft-button check make each product resumable and prevent any publish action.

**Tech Stack:** Python 3.12, Typer, Pydantic 2, openpyxl, PyMuPDF, PyYAML, Jinja2, Beautiful Soup 4, async Playwright, structlog, pytest, pytest-asyncio, pytest-playwright, Ruff, mypy.

---

## Delivery constraints

- Use TDD for every behavior: add one focused failing test, run it, add the smallest implementation, then rerun it.
- Never add a publish/submit-product function. The only terminal browser action is the verified `#saveDraftButton` anchor whose text is exactly `保存草稿`.
- Never reopen or revalidate a successfully archived draft. The archived state and the three save signals are the record of success.
- Keep `config/categories.yaml`, `config/logistics_rules.yaml`, and `config/detail_templates.yaml` as the source of business rules. Fix their encoding to UTF-8 without changing the approved values.
- Commit after each task. Do not stage unrelated user files.

## Target file map

```text
pyproject.toml
.env.example
README.md
app/
  __init__.py
  cli.py
  config.py
  domain/{models.py,states.py,errors.py}
  ingest/{model_number.py,file_stability.py,scanner.py,inventory.py,documents.py}
  ai/{codex_client.py,prompts.py,schemas.py}
  products/{builder.py,geo_detail.py}
  publisher/
    {browser.py,safety.py,locators.py,selector_store.py,image_bank.py,draft_saver.py,orchestrator.py}
    sections/{base.py,main_media.py,basic_information.py,sales_information.py,
              service_commitment.py,logistics_information.py,
              qualifications_services.py,detail_information.py}
  workflow/{state_store.py,lifecycle.py,incidents.py,knowledge.py,runner.py}
config/
  {categories.yaml,detail_templates.yaml,field_rules.yaml,image_rules.yaml,
   sales_rules.yaml,service_rules.yaml,logistics_rules.yaml,
   qualification_rules.yaml,safety_rules.yaml,selectors.yaml}
tests/
  unit/...
  integration/...
  fixtures/{publish_page.html,picman.html,tinymce.html,sample_inventory.xlsx}
```

### Task 1: Bootstrap the typed CLI project

**Files:**
- Create: `pyproject.toml`
- Create: `app/__init__.py`
- Create: `app/cli.py`
- Create: `tests/unit/test_cli.py`

- [ ] **Write the failing smoke test**

```python
# tests/unit/test_cli.py
from typer.testing import CliRunner
from app.cli import app


def test_version_command() -> None:
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "1688-draft-automation 0.1.0"
```

- [ ] **Run it and confirm the import failure**

Run: `python -m pytest tests/unit/test_cli.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app'`.

- [ ] **Add dependencies, strict tool settings, and the minimal command**

```python
# app/cli.py
import typer

app = typer.Typer(no_args_is_help=True)


@app.command()
def version() -> None:
    typer.echo("1688-draft-automation 0.1.0")
```

Declare Python `>=3.12`, runtime dependencies from the Tech Stack, and dev dependencies for pytest, pytest-asyncio, Ruff, and mypy in `pyproject.toml`. Configure Ruff for `py312` and mypy with `strict = true`.

- [ ] **Verify the bootstrap**

Run: `python -m pytest tests/unit/test_cli.py -q`
Expected: `1 passed`.

- [ ] **Commit**

```powershell
git add pyproject.toml app/__init__.py app/cli.py tests/unit/test_cli.py
git commit -m "build: bootstrap typed automation CLI"
```

### Task 2: Define immutable contracts and legal state transitions

**Files:**
- Create: `app/domain/models.py`
- Create: `app/domain/states.py`
- Create: `app/domain/errors.py`
- Create: `tests/unit/domain/test_states.py`
- Create: `tests/unit/domain/test_models.py`

- [ ] **Write failing transition and evidence tests**

```python
from app.domain.states import ProductStatus, transition
from app.domain.errors import InvalidTransition


def test_saved_draft_is_terminal() -> None:
    assert transition(ProductStatus.DRAFT_SAVING, ProductStatus.DRAFT_SAVED) is ProductStatus.DRAFT_SAVED
    with pytest.raises(InvalidTransition):
        transition(ProductStatus.DRAFT_SAVED, ProductStatus.PROCESSING)
```

```python
from app.domain.models import EvidenceValue


def test_present_value_requires_source_evidence() -> None:
    with pytest.raises(ValueError):
        EvidenceValue[str](value="1800 g", source_page=None, source_text=None, confidence=0.9)
```

- [ ] **Run and confirm missing modules**

Run: `python -m pytest tests/unit/domain -q`
Expected: FAIL during collection.

- [ ] **Implement the contracts**

Define frozen Pydantic models for `EvidenceValue[T]`, `OperatingPoint`, `Specification`, `ImageAnalysis`, `InventoryRecord`, `ProductPayload`, `SectionResult`, `DraftEvidence`, and `TaskState`. Use exactly these statuses:

```python
class ProductStatus(StrEnum):
    DISCOVERED = "DISCOVERED"
    FILES_STABLE = "FILES_STABLE"
    PROCESSING = "PROCESSING"
    ANALYZING = "ANALYZING"
    PAYLOAD_READY = "PAYLOAD_READY"
    FILLING = "FILLING"
    DRAFT_SAVING = "DRAFT_SAVING"
    DRAFT_SAVED = "DRAFT_SAVED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    FAILED = "FAILED"
```

Do not define `PUBLISHING` or `PUBLISHED`. Validate that any non-null extracted value has a source page/file, verbatim source text, and confidence.

- [ ] **Verify contracts and transitions**

Run: `python -m pytest tests/unit/domain -q`
Expected: all pass.

- [ ] **Commit**

```powershell
git add app/domain tests/unit/domain
git commit -m "feat: define evidence contracts and task states"
```

### Task 3: Normalize and compare model numbers strictly

**Files:**
- Create: `app/ingest/model_number.py`
- Create: `tests/unit/ingest/test_model_number.py`

- [ ] **Write the normalization matrix first**

```python
@pytest.mark.parametrize(("raw", "expected"), [
    (" A2E250-AL06-01\u200b", "A2E250-AL06-01"),
    ("a2e250_al06_01", "A2E250-AL06-01"),
    ("A2E250　AL06－01", "A2E250-AL06-01"),
])
def test_normalize_model(raw: str, expected: str) -> None:
    assert normalize_model(raw) == expected


def test_similar_models_are_never_equal() -> None:
    assert not exact_model_match("A2E250-AL06-01", "A2E250-AL06-10")
    assert not exact_model_match("A2E250-AL06-O1", "A2E250-AL06-01")
```

- [ ] **Run the red test**

Run: `python -m pytest tests/unit/ingest/test_model_number.py -q`
Expected: FAIL during import.

- [ ] **Implement only approved transformations**

Strip outer whitespace, remove Unicode format/control characters, uppercase, convert underscores/consecutive spaces/full-width hyphens to ASCII `-`, and collapse repeated hyphens. Do not repair `O/0`, `I/1`, suffixes, or near matches.

- [ ] **Run the focused test**

Run: `python -m pytest tests/unit/ingest/test_model_number.py -q`
Expected: all pass.

- [ ] **Commit**

```powershell
git add app/ingest/model_number.py tests/unit/ingest/test_model_number.py
git commit -m "feat: add strict model normalization"
```

### Task 4: Match Excel rows exactly and apply only the approved defaults

**Files:**
- Create: `app/ingest/inventory.py`
- Create: `tests/unit/ingest/test_inventory.py`
- Create: `tests/fixtures/sample_inventory.xlsx`

- [ ] **Write failing workbook tests**

```python
def test_missing_model_row_stops_product(workbook_path: Path) -> None:
    with pytest.raises(ModelRowNotFound):
        load_inventory(workbook_path, "A2E250-AL06-99")


def test_blank_price_and_stock_use_defaults(workbook_path: Path) -> None:
    row = load_inventory(workbook_path, "A2E250-AL06-01")
    assert row.price == Decimal("10000")
    assert row.stock == 50


def test_present_values_are_not_overwritten(workbook_path: Path) -> None:
    row = load_inventory(workbook_path, "A2E250-AL06-02")
    assert row.price == Decimal("8888")
    assert row.stock == 10
```

- [ ] **Run and observe failure**

Run: `python -m pytest tests/unit/ingest/test_inventory.py -q`
Expected: FAIL during import.

- [ ] **Implement header-driven exact lookup**

Use `openpyxl.load_workbook(..., read_only=True, data_only=True)`. Normalize only the model column. Raise `ModelRowNotFound` if no exact row exists; apply `10000` and `50` independently only when the matching row cell is `None` or blank.

- [ ] **Verify defaults and preservation**

Run: `python -m pytest tests/unit/ingest/test_inventory.py -q`
Expected: all pass.

- [ ] **Commit**

```powershell
git add app/ingest/inventory.py tests/unit/ingest/test_inventory.py tests/fixtures/sample_inventory.xlsx
git commit -m "feat: load exact inventory rows with approved defaults"
```

### Task 5: Detect stable input folders and own their lifecycle

**Files:**
- Create: `app/ingest/file_stability.py`
- Create: `app/ingest/scanner.py`
- Create: `app/workflow/lifecycle.py`
- Create: `tests/unit/ingest/test_scanner.py`
- Create: `tests/unit/workflow/test_lifecycle.py`

- [ ] **Write tests for stability and atomic movement**

```python
def test_folder_is_unstable_when_size_changes(tmp_path: Path, fake_clock: FakeClock) -> None:
    probe = StabilityProbe(window_seconds=2, clock=fake_clock)
    folder = make_model_folder(tmp_path, "A2E250-AL06-01")
    assert not probe.ready(folder)
    (folder / "drawing.pdf").write_bytes(b"changed")
    fake_clock.advance(2)
    assert not probe.ready(folder)


def test_archive_never_reopens_saved_folder(layout: DataLayout) -> None:
    saved = layout.draft_saved / "A2E250-AL06-01"
    saved.mkdir(parents=True)
    assert list(Scanner(layout).discover()) == []
```

- [ ] **Run the red tests**

Run: `python -m pytest tests/unit/ingest/test_scanner.py tests/unit/workflow/test_lifecycle.py -q`
Expected: FAIL during collection.

- [ ] **Implement snapshot stability and same-volume moves**

Accept only first-level model directories, compare `(relative_path, size, mtime_ns)` snapshots after the configured window, and use `Path.replace` for moves between `inbox`, `processing`, `draft_saved`, `failed`, and `manual_review`. Reject duplicate destinations instead of merging content.

- [ ] **Verify lifecycle behavior**

Run: `python -m pytest tests/unit/ingest/test_scanner.py tests/unit/workflow/test_lifecycle.py -q`
Expected: all pass.

- [ ] **Commit**

```powershell
git add app/ingest/file_stability.py app/ingest/scanner.py app/workflow/lifecycle.py tests/unit/ingest tests/unit/workflow/test_lifecycle.py
git commit -m "feat: add stable-folder ingestion lifecycle"
```

### Task 6: Inventory documents and reconcile model evidence

**Files:**
- Create: `app/ingest/documents.py`
- Create: `tests/unit/ingest/test_documents.py`

- [ ] **Write evidence reconciliation tests**

```python
def test_pdf_directory_and_excel_must_match() -> None:
    result = reconcile_models(directory="A2E250-AL06-01", pdf="A2E250-AL06-01", plate=None, excel="A2E250-AL06-01")
    assert result.model == "A2E250-AL06-01"


def test_readable_conflicting_plate_requires_review() -> None:
    with pytest.raises(ModelConflict):
        reconcile_models(directory="A2E250-AL06-01", pdf="A2E250-AL06-01", plate="A2E250-AL06-02", excel="A2E250-AL06-01")
```

- [ ] **Run and confirm failure**

Run: `python -m pytest tests/unit/ingest/test_documents.py -q`
Expected: FAIL during import.

- [ ] **Implement deterministic file inventory**

Classify PDFs, supported images, and spreadsheets by extension; reject empty PDF/image sets; return sorted absolute paths. Reconcile exact normalized strings and treat an unreadable plate as absent, never as agreement.

- [ ] **Verify document rules**

Run: `python -m pytest tests/unit/ingest/test_documents.py -q`
Expected: all pass.

- [ ] **Commit**

```powershell
git add app/ingest/documents.py tests/unit/ingest/test_documents.py
git commit -m "feat: inventory source documents and reconcile models"
```

### Task 7: Wrap local `codex exec` with JSON Schema output

**Files:**
- Create: `app/ai/schemas.py`
- Create: `app/ai/prompts.py`
- Create: `app/ai/codex_client.py`
- Create: `tests/unit/ai/test_codex_client.py`
- Create: `tests/unit/ai/test_schemas.py`

- [ ] **Write tests against a fake process runner**

```python
@pytest.mark.asyncio
async def test_codex_uses_read_only_workspace_and_schema(tmp_path: Path) -> None:
    runner = FakeRunner(stdout=valid_specification_json())
    result = await CodexClient(runner).extract_specification(tmp_path)
    command = runner.last_command
    assert command[:2] == ["codex", "exec"]
    assert "--sandbox" in command and "read-only" in command
    assert "--output-schema" in command
    assert result.model == "A2E250-AL06-01"
```

```python
def test_payload_rejects_60hz_as_china_primary() -> None:
    with pytest.raises(ValueError):
        Specification.model_validate(spec_with_primary_frequency(60))
```

- [ ] **Run the red tests**

Run: `python -m pytest tests/unit/ai -q`
Expected: FAIL during collection.

- [ ] **Implement subprocess isolation and schema validation**

Use `asyncio.create_subprocess_exec` through an injected `ProcessRunner`; pass the source folder as the only readable workspace, a generated Pydantic JSON Schema file, and a prompt that requires null for absent fields, preserves all frequency operating points, selects 50 Hz for China, and forbids similar-model evidence. Validate stdout before writing `specification.json` or `image_analysis.json` atomically.

- [ ] **Verify malformed output and timeout paths too**

Run: `python -m pytest tests/unit/ai -q`
Expected: all pass, including invalid JSON, schema mismatch, non-zero exit, and timeout cases.

- [ ] **Commit**

```powershell
git add app/ai tests/unit/ai
git commit -m "feat: extract evidence with local Codex CLI"
```

### Task 8: Build the deterministic product payload

**Files:**
- Create: `app/products/builder.py`
- Create: `tests/unit/products/test_builder.py`

- [ ] **Write tests for 50 Hz, image order, and logistics**

```python
def test_builder_maps_only_50hz_to_sales_payload(inputs: BuildInputs) -> None:
    payload = build_payload(inputs)
    assert payload.primary_operating_point.frequency_hz == 50
    assert {point.frequency_hz for point in payload.operating_points} == {50, 60}


def test_builder_uses_fixed_logistics_and_image_slots(inputs: BuildInputs) -> None:
    payload = build_payload(inputs)
    assert payload.delivery_time == "48小时发货"
    assert payload.shipping_template == "运费"
    assert payload.package_cm == (28, 28, Decimal("7.35"))
    assert payload.package_weight_g == 1800
    assert [image.role for image in payload.main_images] == ["front", "side", "rear", "nameplate"]
    assert payload.white_background_image.role == "white_background"
```

- [ ] **Run and confirm failure**

Run: `python -m pytest tests/unit/products/test_builder.py -q`
Expected: FAIL during import.

- [ ] **Implement evidence-only mapping**

Require exact reconciled model, verified dimensions and model weight, exactly four regular images plus one white-background image, and an inventory record. Preserve all operating points but expose 50 Hz as primary. Missing required evidence raises `ManualReviewRequired`; optional absent fields remain `None`.

- [ ] **Verify the immutable payload**

Run: `python -m pytest tests/unit/products/test_builder.py -q`
Expected: all pass.

- [ ] **Commit**

```powershell
git add app/products/builder.py tests/unit/products/test_builder.py
git commit -m "feat: build evidence-bound 1688 payload"
```

### Task 9: Render the approved answer-first GEO detail

**Files:**
- Create: `app/products/geo_detail.py`
- Modify: `app/cli.py`
- Modify: `config/detail_templates.yaml`
- Create: `tests/unit/products/test_geo_detail.py`
- Create: `tests/fixtures/geo_payload.json`

- [ ] **Write structure and anti-inference tests**

```python
def test_geo_detail_has_fixed_answer_first_structure(payload: ProductPayload) -> None:
    html = render_geo_detail(payload)
    doc = BeautifulSoup(html, "html.parser")
    assert [node["data-geo-section"] for node in doc.select("[data-geo-section]")] == [
        "entity_answer", "product_definition", "core_parameters", "operating_points",
        "structure_and_installation", "purchase_confirmation", "faq", "one_sentence_selection",
    ]
    assert "A2E250-AL06-01" in doc.select_one('[data-geo-section="entity_answer"]').get_text()


def test_geo_detail_hides_missing_and_unsupported_claims(payload: ProductPayload) -> None:
    html = render_geo_detail(payload.model_copy(update={"certification": None, "warranty": None}))
    assert "认证" not in html
    assert "质保" not in html
    assert "适用于" not in html


def test_geo_images_have_semantic_alt(payload: ProductPayload) -> None:
    images = BeautifulSoup(render_geo_detail(payload), "html.parser").select("img")
    assert len(images) == 4
    assert all("A2E250-AL06-01" in image["alt"] for image in images)


def test_fourth_geo_image_is_unused_current_model_photo(payload: ProductPayload) -> None:
    images = BeautifulSoup(render_geo_detail(payload), "html.parser").select("img")
    sources = [image["src"] for image in images]
    assert len(sources) == len(set(sources)) == 4
    assert images[3]["data-image-role"] == "unused_main_photo"
    assert images[3]["src"] != payload.white_background_image.hosted_url
```

- [ ] **Run the red GEO tests**

Run: `python -m pytest tests/unit/products/test_geo_detail.py -q`
Expected: FAIL during import.

- [ ] **Implement the frozen eight-section renderer**

Render only escaped payload values. Include parameter meanings beside values and label operating-point frequency. Place the first three hosted images after entity answer/core parameters/structure; place a fourth, previously unused current-model real photo after the structure section with `data-image-role="unused_main_photo"`. Build alt text from `{brand} {model} {image_role}`. Reject duplicate URLs, the white-background slot, and any image whose model evidence conflicts. Omit empty rows and empty optional blocks. Never generate application scenarios, certifications, warranty, or related-model comparisons.

```yaml
# config/detail_templates.yaml
geo_detail:
  image_policy:
    required_count: 4
    positions:
      - after_entity_answer
      - after_core_parameters
      - after_structure_and_installation
      - after_structure_and_installation_secondary
    fourth_image_role: unused_main_photo
    reject_white_background: true
    reject_duplicate_urls: true
```

- [ ] **Verify the exact local detail artifact**

Run: `python -m pytest tests/unit/products/test_geo_detail.py -q`
Expected: all pass.

Run: `python -m app.cli render-detail tests/fixtures/geo_payload.json --output automation/A2E250-AL06-01/detail.html`
Expected: exits 0 and produces UTF-8 HTML matching the approved browser preview.

- [ ] **Commit**

```powershell
git add app/products/geo_detail.py app/cli.py config/detail_templates.yaml tests/unit/products/test_geo_detail.py tests/fixtures/geo_payload.json
git commit -m "feat: render approved GEO product detail"
```

### Task 10: Load UTF-8 business configuration without scattered selectors

**Files:**
- Create: `app/config.py`
- Modify: `config/categories.yaml`
- Modify: `config/logistics_rules.yaml`
- Create: `config/field_rules.yaml`
- Create: `config/image_rules.yaml`
- Create: `config/sales_rules.yaml`
- Create: `config/service_rules.yaml`
- Create: `config/qualification_rules.yaml`
- Create: `config/safety_rules.yaml`
- Create: `config/selectors.yaml`
- Create: `tests/unit/test_config.py`

- [ ] **Write config contract tests**

```python
def test_approved_fixed_rules_load_as_utf8() -> None:
    settings = load_settings(Path("config"))
    assert settings.category.path[-1] == "其他工业风扇"
    assert settings.category.category_id == 1034320
    assert settings.category.industry_category_id == 2293
    assert settings.logistics.delivery_time == "48小时发货"
    assert settings.logistics.shipping_template == "运费"
    assert settings.logistics.shipping_template != "8元"
```

- [ ] **Run and expose current encoding/schema failures**

Run: `python -m pytest tests/unit/test_config.py -q`
Expected: FAIL because the loader/config set is incomplete.

- [ ] **Add typed settings and centralized verified selectors**

Put the verified module IDs and field locators in YAML, including `guid-title`, `guid-catProp`, `guid-salePropTable`, `guid-priceRange`, `guid-skuTable`, `guid-beginAmount`, `guid-buyerProtection`, `guid-freight`, `guid-officialLogistics`, `guid-blockCrossBorder`, `guid-description`, `guid-submit`, `saveDraftButton`, and forbidden `submitFormButton`. Configure primary and backup image albums and the post-login domain allowlist.

- [ ] **Verify all YAML and values**

Run: `python -m pytest tests/unit/test_config.py -q`
Expected: all pass.

- [ ] **Commit**

```powershell
git add app/config.py config tests/unit/test_config.py
git commit -m "feat: centralize verified 1688 business configuration"
```

### Task 11: Guard domains and prohibit publish controls

**Files:**
- Create: `app/publisher/safety.py`
- Create: `app/publisher/browser.py`
- Create: `tests/unit/publisher/test_safety.py`
- Create: `tests/unit/publisher/test_browser.py`

- [ ] **Write security boundary tests**

```python
@pytest.mark.parametrize("url", [
    "https://work.1688.com/", "https://offer-new.1688.com/select.htm",
    "https://foo.alibaba.com/path",
])
def test_business_domains_allowed(url: str) -> None:
    assert DomainGuard.business().allows(url)


def test_lookalike_and_external_domains_rejected() -> None:
    assert not DomainGuard.business().allows("https://1688.com.evil.test/")
    assert not DomainGuard.business().allows("https://example.com/")


def test_publish_selectors_are_forbidden() -> None:
    guard = ActionGuard()
    with pytest.raises(ForbiddenAction):
        guard.check_click("#submitFormButton", "发布商品")
```

- [ ] **Run and confirm failure**

Run: `python -m pytest tests/unit/publisher/test_safety.py tests/unit/publisher/test_browser.py -q`
Expected: FAIL during collection.

- [ ] **Implement URL parsing and guarded browser connection**

Compare parsed hostnames by exact suffix boundaries. Allow configured Taobao authentication redirects only during login, then switch to `1688.com`/`alibaba.com`. Attach navigation listeners that stop the current item and capture an incident on boundary violations. Connect to the dedicated Chrome CDP endpoint; never launch against the user's default profile.

- [ ] **Verify safety tests**

Run: `python -m pytest tests/unit/publisher/test_safety.py tests/unit/publisher/test_browser.py -q`
Expected: all pass.

- [ ] **Commit**

```powershell
git add app/publisher/safety.py app/publisher/browser.py tests/unit/publisher
git commit -m "feat: guard browser domains and forbidden actions"
```

### Task 12: Resolve selectors safely and persist only validated candidates

**Files:**
- Create: `app/publisher/locators.py`
- Create: `app/publisher/selector_store.py`
- Create: `tests/unit/publisher/test_locators.py`

- [ ] **Write locator validation tests**

```python
@pytest.mark.asyncio
async def test_candidate_must_be_unique_visible_and_enabled(fake_page: FakePage) -> None:
    locator = await LocatorResolver(fake_page).resolve([Candidate("#unique")])
    assert locator.selector == "#unique"


@pytest.mark.asyncio
async def test_candidate_matching_publish_control_is_rejected(fake_page: FakePage) -> None:
    with pytest.raises(UnsafeLocator):
        await LocatorResolver(fake_page).resolve([Candidate("#submitFormButton")])
```

- [ ] **Run the red test**

Run: `python -m pytest tests/unit/publisher/test_locators.py -q`
Expected: FAIL during import.

- [ ] **Implement ordered locator strategies**

Try role, label, placeholder, stable module ID, `cat-prop-id`, and nearby field heading in that order. Reject zero/multiple matches, invisibility, disabled controls, and publish text/selectors. Store AI-suggested candidates only after those checks, scoped by page fingerprint and field key; never rewrite source configuration automatically.

- [ ] **Verify candidate rejection paths**

Run: `python -m pytest tests/unit/publisher/test_locators.py -q`
Expected: all pass.

- [ ] **Commit**

```powershell
git add app/publisher/locators.py app/publisher/selector_store.py tests/unit/publisher/test_locators.py
git commit -m "feat: add validated locator resolution"
```

### Task 13: Upload and place the five product images

**Files:**
- Create: `app/publisher/image_bank.py`
- Create: `app/publisher/sections/base.py`
- Create: `app/publisher/sections/main_media.py`
- Create: `tests/integration/publisher/test_main_media.py`
- Create: `tests/fixtures/picman.html`

- [ ] **Write the browser-fixture test**

```python
@pytest.mark.asyncio
async def test_main_media_uploads_four_plus_white_and_disables_watermark(page, payload) -> None:
    result = await MainMediaSection().fill(page, payload)
    assert result.completed
    assert await page.locator("[data-slot=main] img").count() == 4
    assert await page.locator("[data-slot=white] img").count() == 1
    assert not await page.get_by_label("图片水印").is_checked()
```

- [ ] **Run and confirm failure**

Run: `python -m pytest tests/integration/publisher/test_main_media.py -q`
Expected: FAIL during import.

- [ ] **Implement album fallback and upload completion checks**

Work inside the `picman.1688.com` frame, choose “我的电脑”, select the first configured non-full album, turn watermark off, upload paths through the file input, wait for five explicit success states, insert, then verify four main slots and one separate white-background slot with no pending/failed marker. A full album is not retried; all albums full raises `ManualReviewRequired`.

- [ ] **Verify the fixture interaction**

Run: `python -m pytest tests/integration/publisher/test_main_media.py -q`
Expected: all pass.

- [ ] **Commit**

```powershell
git add app/publisher/image_bank.py app/publisher/sections tests/integration/publisher/test_main_media.py tests/fixtures/picman.html
git commit -m "feat: fill verified main media slots"
```

### Task 14: Fill basic, sales, service, logistics, and qualification sections

**Files:**
- Create: `app/publisher/sections/basic_information.py`
- Create: `app/publisher/sections/sales_information.py`
- Create: `app/publisher/sections/service_commitment.py`
- Create: `app/publisher/sections/logistics_information.py`
- Create: `app/publisher/sections/qualifications_services.py`
- Create: `tests/integration/publisher/test_form_sections.py`
- Create: `tests/fixtures/publish_page.html`

- [ ] **Write one observable test per section**

```python
@pytest.mark.asyncio
async def test_sales_uses_excel_price_stock_and_one_piece_minimum(page, payload) -> None:
    await SalesInformationSection().fill(page, payload)
    assert await page.locator("#guid-priceRange input").input_value() == "10000"
    assert await page.locator("#guid-skuTable [data-field=stock]").input_value() == "10"
    assert await page.locator("#guid-beginAmount input").input_value() == "1"


@pytest.mark.asyncio
async def test_logistics_uses_approved_values(page, payload) -> None:
    await LogisticsInformationSection().fill(page, payload)
    assert await selected_text(page, "#guid-freight") == "运费"
    assert await package_values(page) == ["28", "28", "7.35", "1800"]
```

Also assert the fixed category IDs, `48小时发货`, and that missing certificates leave the optional section untouched.

- [ ] **Run the red fixture suite**

Run: `python -m pytest tests/integration/publisher/test_form_sections.py -q`
Expected: FAIL during import.

- [ ] **Implement five isolated section fillers**

Each returns `SectionResult` with start/end timestamps, action summary, locator keys, and validation results. Read only `ProductPayload` plus typed config. Never infer commitments, material, authorization, certificates, or services.

- [ ] **Verify all section postconditions**

Run: `python -m pytest tests/integration/publisher/test_form_sections.py -q`
Expected: all pass.

- [ ] **Commit**

```powershell
git add app/publisher/sections tests/integration/publisher/test_form_sections.py tests/fixtures/publish_page.html
git commit -m "feat: fill verified 1688 form sections"
```

### Task 15: Write GEO HTML through the verified legacy TinyMCE API

**Files:**
- Create: `app/publisher/sections/detail_information.py`
- Create: `tests/integration/publisher/test_detail_information.py`
- Create: `tests/fixtures/tinymce.html`

- [ ] **Write the exact event-sequence test**

```python
@pytest.mark.asyncio
async def test_detail_uses_legacy_tinymce_sequence(page, payload) -> None:
    await DetailInformationSection().fill(page, payload)
    calls = await page.evaluate("window.editorCalls")
    assert [call[0] for call in calls] == ["setContent", "onChange.dispatch", "save"]
    assert "A2E250-AL06-01" in calls[0][1]
    assert len(BeautifulSoup(calls[0][1], "html.parser").select("img")) == 4
```

- [ ] **Run and confirm failure**

Run: `python -m pytest tests/integration/publisher/test_detail_information.py -q`
Expected: FAIL during import.

- [ ] **Implement the old API bridge and postcondition**

Inside `guid-description`, obtain the existing editor instance and call `setContent(html)`, `onChange.dispatch()`, and `save()` in order. Read back the hidden textarea/editor content and require all eight `data-geo-section` markers, exactly four distinct hosted images, and a semantic `alt` on every image before returning success. Refresh `guid-assistBoard` and require the “详情信息 / 完善产品说明” warning to disappear; do not enable unrelated video or buyer-protection options.

- [ ] **Verify GEO injection**

Run: `python -m pytest tests/integration/publisher/test_detail_information.py -q`
Expected: all pass.

- [ ] **Commit**

```powershell
git add app/publisher/sections/detail_information.py tests/integration/publisher/test_detail_information.py tests/fixtures/tinymce.html
git commit -m "feat: write GEO detail through legacy TinyMCE"
```

### Task 16: Save drafts with three signals and no publish path

**Files:**
- Create: `app/publisher/draft_saver.py`
- Create: `tests/integration/publisher/test_draft_saver.py`
- Create: `tests/unit/publisher/test_no_publish_api.py`

- [ ] **Write save safety and evidence tests**

```python
@pytest.mark.asyncio
async def test_save_click_requires_exact_anchor_and_collects_three_signals(page) -> None:
    evidence = await DraftSaver().save(page)
    assert evidence.response_status == 200
    assert evidence.success_message == "保存草稿成功"
    assert evidence.draft_id == "fixture-draft-id"
    assert await page.locator("#submitFormButton").get_attribute("data-clicked") is None


def test_publisher_has_no_publish_or_submit_product_symbol() -> None:
    names = exported_callable_names(Path("app/publisher"))
    assert not {name for name in names if "publish" in name.lower() or "submit_product" in name.lower()}
```

- [ ] **Run the red tests**

Run: `python -m pytest tests/integration/publisher/test_draft_saver.py tests/unit/publisher/test_no_publish_api.py -q`
Expected: FAIL during import.

- [ ] **Implement exact button verification and response observation**

Scope to `guid-submit`; require `#saveDraftButton`, tag `A`, normalized exact text `保存草稿`, and no `发布` substring. Register the `/industry/draftSubmit.htm` response listener before the click, then collect HTTP 200, success message, and URL `draftId`. Require at least one signal, store all observed signals, and prefer all three. Never click or expose `#submitFormButton`.

- [ ] **Verify draft-only behavior**

Run: `python -m pytest tests/integration/publisher/test_draft_saver.py tests/unit/publisher/test_no_publish_api.py -q`
Expected: all pass.

- [ ] **Commit**

```powershell
git add app/publisher/draft_saver.py tests/integration/publisher/test_draft_saver.py tests/unit/publisher/test_no_publish_api.py
git commit -m "feat: save drafts with verified evidence"
```

### Task 17: Persist state, incidents, and reusable lessons

**Files:**
- Create: `app/workflow/state_store.py`
- Create: `app/workflow/incidents.py`
- Create: `app/workflow/knowledge.py`
- Create: `tests/unit/workflow/test_state_store.py`
- Create: `tests/unit/workflow/test_incidents.py`

- [ ] **Write atomic state and incident tests**

```python
def test_state_write_is_atomic(tmp_path: Path, state: TaskState) -> None:
    store = JsonStateStore(tmp_path / "task_state.json")
    store.save(state)
    assert store.load() == state
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.asyncio
async def test_browser_failure_captures_complete_incident(fake_page, payload) -> None:
    bundle = await IncidentCollector(tmp_path).capture(fake_page, payload, section="sales", action="fill_stock", selector="#stock")
    assert bundle.screenshot.exists()
    assert bundle.html.exists()
    assert bundle.console_log.exists()
    assert bundle.network_errors.exists()
    assert bundle.context_json.exists()
```

- [ ] **Run and confirm failure**

Run: `python -m pytest tests/unit/workflow/test_state_store.py tests/unit/workflow/test_incidents.py -q`
Expected: FAIL during import.

- [ ] **Implement atomic JSON and incident bundles**

Write temporary files then replace. Capture screenshot, full HTML, reduced DOM, accessibility snapshot when supported, console, network errors, payload, section/action/selector, and timestamps. Separate `mature_rules.json` from append-only `lessons.ndjson`; selector lessons may be reused only after deterministic validation.

- [ ] **Verify persistence and redaction**

Run: `python -m pytest tests/unit/workflow -q`
Expected: all pass, including redaction of cookies, tokens, and local usernames.

- [ ] **Commit**

```powershell
git add app/workflow tests/unit/workflow
git commit -m "feat: persist task state and failure evidence"
```

### Task 18: Orchestrate batches and continue after one product fails

**Files:**
- Create: `app/publisher/orchestrator.py`
- Create: `app/workflow/runner.py`
- Modify: `app/cli.py`
- Create: `tests/integration/test_batch_runner.py`
- Create: `tests/unit/test_cli_run.py`

- [ ] **Write dry-run, save-draft, and continuation tests**

```python
@pytest.mark.asyncio
async def test_batch_continues_after_first_product_fails(fake_pipeline) -> None:
    summary = await BatchRunner(fake_pipeline).run(["A2E250-AL06-01", "A2E250-AL06-02"], save_draft=False)
    assert summary.failed == ["A2E250-AL06-01"]
    assert summary.completed == ["A2E250-AL06-02"]


def test_dry_run_is_default() -> None:
    result = CliRunner().invoke(app, ["run", "--once"])
    assert result.exit_code == 0
    assert "stopped before save" in result.stdout
```

- [ ] **Run the red tests**

Run: `python -m pytest tests/integration/test_batch_runner.py tests/unit/test_cli_run.py -q`
Expected: FAIL because the command and runner do not exist.

- [ ] **Implement the ordered seven-section workflow**

Move through ingestion, analysis, payload build, main media, basic, sales, service, logistics, qualifications, detail, and optional draft save. Persist state after every boundary. `--dry-run` is default; `--save-draft` is explicit and mutually exclusive. Map domain/model/captcha/missing-required/unsafe-selector errors to `MANUAL_REVIEW`, deterministic internal errors to `FAILED`, archive `DRAFT_SAVED`, and continue the loop.

- [ ] **Verify batch semantics**

Run: `python -m pytest tests/integration/test_batch_runner.py tests/unit/test_cli_run.py -q`
Expected: all pass.

- [ ] **Commit**

```powershell
git add app/publisher/orchestrator.py app/workflow/runner.py app/cli.py tests/integration/test_batch_runner.py tests/unit/test_cli_run.py
git commit -m "feat: orchestrate resumable draft batches"
```

### Task 19: Document Windows setup and add an environment doctor

**Files:**
- Modify: `app/cli.py`
- Create: `.env.example`
- Create: `README.md`
- Create: `tests/unit/test_doctor.py`

- [ ] **Write the doctor test**

```python
def test_doctor_reports_required_local_dependencies(fake_environment) -> None:
    result = CliRunner().invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Python 3.12: OK" in result.stdout
    assert "codex exec: OK" in result.stdout
    assert "Chrome CDP: OK" in result.stdout
    assert "work.1688.com login: OK" in result.stdout
```

- [ ] **Run and confirm missing command**

Run: `python -m pytest tests/unit/test_doctor.py -q`
Expected: FAIL because `doctor` does not exist.

- [ ] **Implement read-only diagnostics and operator instructions**

Document virtual environment setup, Playwright browser install, dedicated Chrome launch with remote debugging and a non-default profile, `work.1688.com` login, folder/Excel naming, `render-detail`, default dry-run, explicit `--save-draft`, output locations, and recovery states. The doctor may inspect but must not launch, log in, alter browser state, or save a draft.

- [ ] **Verify docs command and help text**

Run: `python -m pytest tests/unit/test_doctor.py tests/unit/test_cli.py tests/unit/test_cli_run.py -q`
Expected: all pass.

- [ ] **Commit**

```powershell
git add app/cli.py .env.example README.md tests/unit/test_doctor.py
git commit -m "docs: add Windows operation and environment checks"
```

### Task 20: Run full offline acceptance and static safety gates

**Files:**
- Modify: `tests/integration/test_batch_runner.py`
- Create: `tests/integration/test_offline_acceptance.py`
- Create: `tests/unit/test_static_safety.py`

- [ ] **Add the end-to-end offline acceptance test**

```python
@pytest.mark.asyncio
async def test_offline_fixture_reaches_draft_saved_without_publish(offline_system) -> None:
    result = await offline_system.run_model("A2E250-AL06-01", save_draft=True)
    assert result.state.status is ProductStatus.DRAFT_SAVED
    assert result.state.draft_evidence.draft_id == "fixture-draft-id"
    assert result.archive.name == "A2E250-AL06-01"
    assert result.publish_clicks == 0
```

- [ ] **Add a source-level forbidden-action gate**

Scan Python AST and configured selectors to fail on browser clicks whose selector/text targets `submitFormButton`, `发布`, `确认发布`, or any callable named `publish*`/`submit_product*`. Exempt test assertions and constants used only by `ActionGuard`.

- [ ] **Run focused acceptance first**

Run: `python -m pytest tests/integration/test_offline_acceptance.py tests/unit/test_static_safety.py -q`
Expected: all pass.

- [ ] **Run the complete verification suite**

```powershell
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m mypy app
git diff --check
```

Expected: every command exits 0; pytest reports no skipped safety or integration tests.

- [ ] **Perform the controlled real-browser acceptance**

Run `python -m app.cli doctor`, then `python -m app.cli run --once --dry-run` against the dedicated logged-in Chrome. Inspect the seven section results and the rendered GEO detail. Only after the dry-run evidence is clean, run one item with `python -m app.cli run --once --save-draft`. Require `/industry/draftSubmit.htm` HTTP 200, `保存草稿成功`, and a URL `draftId`. Do not reopen the saved draft.

- [ ] **Commit the final acceptance coverage**

```powershell
git add tests/integration/test_batch_runner.py tests/integration/test_offline_acceptance.py tests/unit/test_static_safety.py
git commit -m "test: add offline acceptance and draft safety gates"
```

## Completion checklist

- [ ] Every source field in `1688_payload.json` has current-model evidence or is null/omitted.
- [ ] Missing Excel model row stops only that product; blank price/stock cells resolve independently to `10000`/`50`.
- [ ] Fixed category, 48-hour delivery, `运费` template, drawing dimensions, and model weight are config-backed and tested.
- [ ] GEO HTML uses the approved eight-section answer-first structure, four distinct semantic images, parameter meanings, operating-point context, and no unsupported claims; the fourth image is an unused current-model real photo rather than the white-background image.
- [ ] All seven page sections validate their postconditions before draft save.
- [ ] No code path can click a publish control; only the exact draft anchor is allowed.
- [ ] Successful drafts are archived without reopening; failures create incident evidence and do not stop the batch.
- [ ] Offline suite, Ruff, formatting, mypy, diff check, dry-run, and one controlled draft save all pass.
