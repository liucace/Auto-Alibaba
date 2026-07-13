# Product Input Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-use product-input guide that creates the inventory workbook and model source directory, explains their purposes, and blocks upload until the operator has supplied a PDF and four product photos.

**Architecture:** Put all filesystem and workbook behavior in a focused `app.products.input_onboarding` module. Expose it through a JSON `init-product` CLI command, call the same project API from the Plugin upload wrapper before locking or browser work, and teach the bundled Skill to run and explain that gate before all preparation.

**Tech Stack:** Python 3.12, Typer, openpyxl, pytest, Codex Skill Markdown, PowerShell verification commands.

---

## File map

- Create `app/products/input_onboarding.py`: idempotent workbook/directory initialization, source-file inspection, structured result types.
- Create `tests/unit/products/test_input_onboarding.py`: core creation, preservation, idempotency, input counting, and corruption tests.
- Modify `app/cli.py`: add the `init-product` JSON command.
- Create `tests/unit/test_init_product_cli.py`: CLI status, JSON, exit-code, and error tests.
- Modify `plugins/auto-alibaba/skills/upload-1688-products/scripts/run_upload.py`: enforce onboarding before lock, prepare, session, or browser work.
- Create `tests/unit/test_run_upload.py`: verify early `NEEDS_INPUT` short-circuit and ready-path ordering.
- Modify `plugins/auto-alibaba/skills/upload-1688-products/SKILL.md`: make onboarding the first product-specific action and require a user-facing explanation.
- Modify `tests/unit/test_upload_skill_contract.py`: assert the wrapper and Skill contain the onboarding gate.
- Modify `README.md`: document the generated inputs, their purposes, and the rerun flow.
- Modify `tests/unit/test_distribution_contract.py`: keep README/Plugin distribution guidance enforceable.
- Sync the verified bundled Skill into `C:/Users/小城/.codex/skills/upload-1688-products/`; this installed copy is deployment state and is not committed.

### Task 1: Core product-input initialization

**Files:**
- Create: `app/products/input_onboarding.py`
- Create: `tests/unit/products/test_input_onboarding.py`

- [ ] **Step 1: Write failing tests for creation and structured guidance**

Create tests that call the wished-for API and assert the exact business model remains in Excel while the folder key removes `/`:

```python
from pathlib import Path

import openpyxl

from app.products.input_onboarding import initialize_product_inputs


MODEL = "W3G800-KS39-03/F01"


def test_missing_inputs_create_inventory_template_and_model_folder(tmp_path: Path) -> None:
    result = initialize_product_inputs(tmp_path, MODEL)

    workbook = tmp_path / "price_inventory.xlsx"
    source = tmp_path / "data" / "draft_saved" / "W3G800-KS39-03F01"
    assert workbook.is_file()
    assert source.is_dir()
    assert result.status == "NEEDS_INPUT"
    assert result.ok is False
    assert str(workbook.resolve()) in result.created
    assert str(source.resolve()) in result.created

    book = openpyxl.load_workbook(workbook, read_only=True, data_only=True)
    try:
        rows = list(book.active.iter_rows(values_only=True))
    finally:
        book.close()
    assert rows == [("型号", "价格", "库存"), (MODEL, None, None)]

    requirements = {item.key: item for item in result.requirements}
    assert "1688价格和库存" in requirements["inventory"].purpose
    assert "PDF" in requirements["source_files"].action
    assert "四张" in requirements["source_files"].action
```

- [ ] **Step 2: Run the creation test and verify RED**

Run:

```powershell
python -m pytest tests/unit/products/test_input_onboarding.py::test_missing_inputs_create_inventory_template_and_model_folder -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'app.products.input_onboarding'`.

- [ ] **Step 3: Add preservation, idempotency, readiness, and invalid-workbook tests**

Add tests that establish the remaining behavior before implementation:

```python
import json

import pytest
from PIL import Image

from app.domain.errors import ManualReviewRequired


def _write_workbook(path: Path, rows: list[tuple[object, object, object]]) -> None:
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["型号", "价格", "库存"])
    for row in rows:
        sheet.append(list(row))
    book.save(path)


def test_existing_workbook_appends_model_once_and_preserves_rows(tmp_path: Path) -> None:
    workbook = tmp_path / "price_inventory.xlsx"
    _write_workbook(workbook, [("EXISTING-01", 88, 9)])

    first = initialize_product_inputs(tmp_path, MODEL)
    second = initialize_product_inputs(tmp_path, MODEL)

    book = openpyxl.load_workbook(workbook, read_only=True, data_only=True)
    try:
        rows = list(book.active.iter_rows(values_only=True))
    finally:
        book.close()
    assert rows == [
        ("型号", "价格", "库存"),
        ("EXISTING-01", 88, 9),
        (MODEL, None, None),
    ]
    assert first.status == "NEEDS_INPUT"
    assert second.created == ()


def test_ready_requires_top_level_pdf_and_four_source_images(tmp_path: Path) -> None:
    workbook = tmp_path / "price_inventory.xlsx"
    _write_workbook(workbook, [(MODEL, 100, 6)])
    source = tmp_path / "data" / "draft_saved" / "W3G800-KS39-03F01"
    source.mkdir(parents=True)
    (source / "spec.pdf").write_bytes(b"%PDF-input")
    for index in range(4):
        Image.new("RGB", (10, 10)).save(source / f"photo-{index}.jpg")
    optimized = source / "upload_optimized"
    optimized.mkdir()
    Image.new("RGB", (10, 10)).save(optimized / "derived.jpg")

    result = initialize_product_inputs(tmp_path, MODEL)

    assert result.status == "READY"
    assert result.ok is True
    assert result.checks["pdf_files"] == 1
    assert result.checks["source_images"] == 4


def test_derived_images_do_not_satisfy_source_photo_requirement(tmp_path: Path) -> None:
    initialize_product_inputs(tmp_path, MODEL)
    source = tmp_path / "data" / "draft_saved" / "W3G800-KS39-03F01"
    (source / "spec.pdf").write_bytes(b"%PDF-input")
    optimized = source / "upload_optimized"
    optimized.mkdir()
    for index in range(4):
        Image.new("RGB", (10, 10)).save(optimized / f"derived-{index}.jpg")

    result = initialize_product_inputs(tmp_path, MODEL)

    assert result.status == "NEEDS_INPUT"
    assert result.checks["source_images"] == 0


def test_invalid_inventory_workbook_is_not_overwritten(tmp_path: Path) -> None:
    workbook = tmp_path / "price_inventory.xlsx"
    original = b"not-an-xlsx"
    workbook.write_bytes(original)

    with pytest.raises(ManualReviewRequired, match="无法读取"):
        initialize_product_inputs(tmp_path, MODEL)

    assert workbook.read_bytes() == original
```

- [ ] **Step 4: Run the focused test file and verify RED**

Run:

```powershell
python -m pytest tests/unit/products/test_input_onboarding.py -q
```

Expected: all tests fail because the module/API is not implemented.

- [ ] **Step 5: Implement the minimal focused module**

Create `app/products/input_onboarding.py` with these public types and API:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from zipfile import BadZipFile

import openpyxl
from openpyxl.utils.exceptions import InvalidFileException

from app.domain.errors import ManualReviewRequired
from app.ingest.model_number import exact_model_match, model_folder_key, normalize_model

HEADERS = ("型号", "价格", "库存")
SOURCE_IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"})


@dataclass(frozen=True)
class InputRequirement:
    key: str
    path: str
    purpose: str
    action: str
    ready: bool


@dataclass(frozen=True)
class ProductInputResult:
    ok: bool
    status: str
    model: str
    folder_key: str
    created: tuple[str, ...]
    checks: dict[str, object]
    requirements: tuple[InputRequirement, ...]
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "status": self.status,
            "model": self.model,
            "folder_key": self.folder_key,
            "created": list(self.created),
            "checks": self.checks,
            "requirements": [asdict(item) for item in self.requirements],
            "message": self.message,
        }


def initialize_product_inputs(root: Path, model: str) -> ProductInputResult:
    root = root.resolve()
    normalized = normalize_model(model)
    folder_key = model_folder_key(normalized)
    workbook = root / "price_inventory.xlsx"
    source = root / "data" / "draft_saved" / folder_key
    created: list[str] = []

    workbook.parent.mkdir(parents=True, exist_ok=True)
    if not workbook.exists():
        book = openpyxl.Workbook()
        sheet = book.active
        sheet.title = "库存"
        sheet.append(list(HEADERS))
        sheet.append([normalized, None, None])
        book.save(workbook)
        book.close()
        created.append(str(workbook.resolve()))
        inventory_needs_review = True
    else:
        try:
            book = openpyxl.load_workbook(workbook)
        except (OSError, ValueError, BadZipFile, InvalidFileException) as error:
            raise ManualReviewRequired(f"库存表无法读取，未覆盖原文件: {workbook}") from error
        try:
            sheet = book.active
            headers = tuple(sheet.cell(row=1, column=index).value for index in range(1, 4))
            if headers != HEADERS:
                raise ManualReviewRequired(
                    f"库存表表头必须为 型号、价格、库存，未修改原文件: {workbook}"
                )
            has_model = any(
                raw_model is not None and exact_model_match(str(raw_model), normalized)
                for raw_model, *_ in sheet.iter_rows(min_row=2, values_only=True)
            )
            inventory_needs_review = not has_model
            if not has_model:
                sheet.append([normalized, None, None])
                book.save(workbook)
                created.append(f"{workbook.resolve()}#{normalized}")
        finally:
            book.close()

    if not source.is_dir():
        source.mkdir(parents=True, exist_ok=True)
        created.append(str(source.resolve()))

    pdf_count = sum(1 for path in source.iterdir() if path.is_file() and path.suffix.lower() == ".pdf" and path.stat().st_size > 0)
    image_count = sum(1 for path in source.iterdir() if path.is_file() and path.suffix.lower() in SOURCE_IMAGE_SUFFIXES and path.stat().st_size > 0)
    source_ready = pdf_count >= 1 and image_count >= 4
    ready = not created and not inventory_needs_review and source_ready
    requirements = (
        InputRequirement(
            key="inventory",
            path=str(workbook),
            purpose="提供当前完整型号在1688使用的价格和库存。",
            action="打开表格核对型号、价格和库存；价格或库存留空时分别使用默认值10000和50。",
            ready=not inventory_needs_review,
        ),
        InputRequirement(
            key="source_files",
            path=str(source),
            purpose="保存当前型号的原始PDF规格书和真实产品照片。",
            action="放入至少一份包含完整型号的PDF，以及至少四张当前型号产品照片。",
            ready=source_ready,
        ),
    )
    return ProductInputResult(
        ok=ready,
        status="READY" if ready else "NEEDS_INPUT",
        model=normalized,
        folder_key=folder_key,
        created=tuple(created),
        checks={
            "inventory_workbook": True,
            "inventory_model": True,
            "source_directory": True,
            "pdf_files": pdf_count,
            "source_images": image_count,
        },
        requirements=requirements,
        message=(
            "商品资料已齐全，可以继续准备和上传。"
            if ready
            else "已创建或发现待补充资料；请按requirements核对后重新运行。"
        ),
    )
```

During implementation, keep line wrapping and exception handling Ruff/mypy clean without broadening behavior.

- [ ] **Step 6: Run core tests and verify GREEN**

Run:

```powershell
python -m pytest tests/unit/products/test_input_onboarding.py -q
```

Expected: all tests in the file pass.

- [ ] **Step 7: Commit the core module**

```powershell
git add app/products/input_onboarding.py tests/unit/products/test_input_onboarding.py
git commit -m "feat: initialize product input templates"
```

### Task 2: `init-product` CLI contract

**Files:**
- Modify: `app/cli.py:11-70`
- Create: `tests/unit/test_init_product_cli.py`

- [ ] **Step 1: Write failing CLI tests**

```python
import json
from pathlib import Path

from typer.testing import CliRunner

import app.cli as cli_module
from app.domain.errors import ManualReviewRequired
from app.products.input_onboarding import InputRequirement, ProductInputResult


def test_init_product_emits_needs_input_json_and_exit_two(monkeypatch, tmp_path: Path) -> None:
    expected = ProductInputResult(
        ok=False,
        status="NEEDS_INPUT",
        model="W3G800-KS39-03/F01",
        folder_key="W3G800-KS39-03F01",
        created=(str(tmp_path / "price_inventory.xlsx"),),
        checks={"pdf_files": 0, "source_images": 0},
        requirements=(
            InputRequirement(
                key="inventory",
                path=str(tmp_path / "price_inventory.xlsx"),
                purpose="提供当前完整型号在1688使用的价格和库存。",
                action="打开表格核对数据。",
                ready=False,
            ),
        ),
        message="请补充资料。",
    )
    monkeypatch.setattr(cli_module, "initialize_product_inputs", lambda root, model: expected)

    result = CliRunner().invoke(
        cli_module.app,
        ["init-product", "W3G800-KS39-03/F01", "--root", str(tmp_path)],
    )

    assert result.exit_code == 2
    assert json.loads(result.stdout) == expected.to_dict()


def test_init_product_emits_ready_json_and_exit_zero(monkeypatch, tmp_path: Path) -> None:
    expected = ProductInputResult(
        ok=True,
        status="READY",
        model="W3G800-KS39-03/F01",
        folder_key="W3G800-KS39-03F01",
        created=(),
        checks={"pdf_files": 1, "source_images": 4},
        requirements=(),
        message="商品资料已齐全。",
    )
    monkeypatch.setattr(cli_module, "initialize_product_inputs", lambda root, model: expected)

    result = CliRunner().invoke(
        cli_module.app,
        ["init-product", "W3G800-KS39-03/F01", "--root", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout)["status"] == "READY"


def test_init_product_reports_safe_block_for_invalid_workbook(monkeypatch, tmp_path: Path) -> None:
    def fail(root: Path, model: str) -> ProductInputResult:
        raise ManualReviewRequired("库存表无法读取，未覆盖原文件")

    monkeypatch.setattr(cli_module, "initialize_product_inputs", fail)
    result = CliRunner().invoke(
        cli_module.app,
        ["init-product", "W3G800-KS39-03/F01", "--root", str(tmp_path)],
    )

    payload = json.loads(result.stdout)
    assert result.exit_code == 2
    assert payload["status"] == "BLOCKED"
    assert "未覆盖原文件" in payload["message"]
```

- [ ] **Step 2: Run the CLI tests and verify RED**

Run:

```powershell
python -m pytest tests/unit/test_init_product_cli.py -q
```

Expected: tests fail because `app.cli` has no `init-product` command/import.

- [ ] **Step 3: Implement the Typer command**

Import `initialize_product_inputs` and add this command before `prepare`:

```python
from app.products.input_onboarding import initialize_product_inputs


@app.command("init-product")
def init_product(
    model: Annotated[str, typer.Argument(help="完整商品型号")],
    root: Annotated[Path, typer.Option("--root", help="商品资料工作区")] = Path("."),
) -> None:
    """Create and explain required local product inputs."""
    try:
        result = initialize_product_inputs(root.resolve(), model)
        payload = result.to_dict()
    except AutomationError as error:
        payload = {
            "ok": False,
            "status": "BLOCKED",
            "model": model,
            "created": [],
            "checks": {},
            "requirements": [],
            "message": str(error),
        }
    typer.echo(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    if not payload["ok"]:
        raise typer.Exit(code=2)
```

- [ ] **Step 4: Run CLI and core tests and verify GREEN**

Run:

```powershell
python -m pytest tests/unit/test_init_product_cli.py tests/unit/products/test_input_onboarding.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit the CLI**

```powershell
git add app/cli.py tests/unit/test_init_product_cli.py
git commit -m "feat: add product input guide command"
```

### Task 3: Enforce onboarding before upload side effects

**Files:**
- Modify: `plugins/auto-alibaba/skills/upload-1688-products/scripts/run_upload.py:269-315`
- Create: `tests/unit/test_run_upload.py`

- [ ] **Step 1: Write a failing wrapper-order test**

Create the test module with this loader and early-gate test:

```python
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "auto-alibaba"
    / "skills"
    / "upload-1688-products"
    / "scripts"
    / "run_upload.py"
)


def _load_run_upload():
    scripts = SCRIPT.parent
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location("test_run_upload_module", SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(scripts))


def test_execute_stops_on_input_guide_before_lock_or_prepare(monkeypatch, tmp_path: Path) -> None:
    module = _load_run_upload()
    calls: list[str] = []
    guided = {
        "ok": False,
        "status": "NEEDS_INPUT",
        "model": "W3G800-KS39-03/F01",
        "folder_key": "W3G800-KS39-03F01",
        "created": [str(tmp_path / "price_inventory.xlsx")],
        "checks": {"pdf_files": 0, "source_images": 0},
        "requirements": [
            {
                "key": "source_files",
                "purpose": "保存PDF和照片。",
                "action": "放入PDF和四张照片。",
                "ready": False,
            }
        ],
        "message": "请补充资料。",
    }
    monkeypatch.setattr(
        module,
        "_product_inputs_from_project",
        lambda root, model: ("W3G800-KS39-03/F01", "W3G800-KS39-03F01", guided),
    )
    monkeypatch.setattr(module, "acquire_lock", lambda *args, **kwargs: calls.append("lock"))
    monkeypatch.setattr(module, "run_prepare", lambda *args, **kwargs: calls.append("prepare"))

    result = module.execute(tmp_path, "W3G800-KS39-03/F01")

    assert result == guided
    assert calls == []
    assert not (tmp_path / ".uploader.lock").exists()
```

- [ ] **Step 2: Run the wrapper test and verify RED**

Run:

```powershell
python -m pytest tests/unit/test_run_upload.py::test_execute_stops_on_input_guide_before_lock_or_prepare -q
```

Expected: FAIL because `_product_inputs_from_project` and the early gate do not exist.

- [ ] **Step 3: Implement the project API bridge and early return**

Replace `_model_paths_from_project` with:

```python
def _product_inputs_from_project(
    root: Path, model: str
) -> tuple[str, str, dict[str, object]]:
    resolved = str(root.resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)
    from app.ingest.model_number import model_folder_key, normalize_model
    from app.products.input_onboarding import initialize_product_inputs

    normalized = normalize_model(model)
    result = initialize_product_inputs(root, normalized)
    return normalized, model_folder_key(normalized), result.to_dict()
```

At the start of `execute`, after the fixed CDP URL check and before `acquire_lock`, add:

```python
try:
    normalized, folder_key, inputs = _product_inputs_from_project(root, model)
except Exception as error:
    return _failure(model, f"{type(error).__name__}: {error}", product_inputs=False)
if not inputs["ok"]:
    return cast(dict[str, Any], inputs)
```

No browser session inspection, upload lock, artifact preparation, or subprocess may run before this gate returns `READY`.

- [ ] **Step 4: Add the ready-path ordering test**

Add this test to the same file:

```python
def test_execute_ready_inputs_reach_lock_and_prepare_in_order(monkeypatch, tmp_path: Path) -> None:
    module = _load_run_upload()
    events: list[str] = []

    def guide(root: Path, model: str):
        events.append("guide")
        return (
            "W3G800-KS39-03/F01",
            "W3G800-KS39-03F01",
            {"ok": True, "status": "READY", "checks": {"pdf_files": 1, "source_images": 4}},
        )

    def lock(path: Path, model: str):
        events.append("lock")
        return {"path": path, "token": "test"}

    def prepare(root: Path, model: str):
        events.append("prepare")
        return {"returncode": 2, "stdout": "preparation stopped", "stderr": ""}

    monkeypatch.setattr(module, "_product_inputs_from_project", guide)
    monkeypatch.setattr(module, "acquire_lock", lock)
    monkeypatch.setattr(module, "release_lock", lambda handle: events.append("release"))
    monkeypatch.setattr(module, "prepared_artifacts_complete", lambda root, key: False)
    monkeypatch.setattr(module, "run_prepare", prepare)

    result = module.execute(tmp_path, "W3G800-KS39-03/F01")

    assert result["checks"] == {"prepare": False}
    assert events == ["guide", "lock", "prepare", "release"]
```

This proves the new check is first while preserving the existing lock and preparation boundary.

- [ ] **Step 5: Run wrapper tests and verify GREEN**

Run:

```powershell
python -m pytest tests/unit/test_run_upload.py tests/unit/test_upload_skill_contract.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit the upload guard**

```powershell
git add plugins/auto-alibaba/skills/upload-1688-products/scripts/run_upload.py tests/unit/test_run_upload.py
git commit -m "feat: gate uploads on local product inputs"
```

### Task 4: Skill behavior and distribution guidance

**Files:**
- Modify: `plugins/auto-alibaba/skills/upload-1688-products/SKILL.md`
- Modify: `tests/unit/test_upload_skill_contract.py`
- Modify: `README.md`
- Modify: `tests/unit/test_distribution_contract.py`

- [ ] **Step 1: Run a Skill baseline scenario without the new instructions**

Use a fresh subagent without exposing the bundled `SKILL.md`. Give it this scenario:

```text
You are operating D:\Auto-Alibab for model W3G800-KS39-03/F01. The repository was freshly cloned, so price_inventory.xlsx and data/draft_saved/W3G800-KS39-03F01 do not exist. Start the upload workflow. State the commands/actions you would take and what you tell the user. Do not invent product data.
```

Record whether it creates both templates, explains both purposes, requires the PDF and four photos, and stops before browser work. This is the RED baseline required by `writing-skills`.

- [ ] **Step 2: Write failing repository contract tests**

Add assertions:

```python
def test_skill_requires_product_input_guide_before_upload() -> None:
    skill = (
        ROOT
        / "plugins"
        / "auto-alibaba"
        / "skills"
        / "upload-1688-products"
        / "SKILL.md"
    ).read_text(encoding="utf-8")

    assert 'python -m app.cli init-product "<MODEL>" --root "<PROJECT_ROOT>"' in skill
    assert skill.index("init-product") < skill.index("doctor")
    assert "NEEDS_INPUT" in skill
    assert "price_inventory.xlsx" in skill
    assert "PDF" in skill
    assert "四张" in skill
    assert "不得在同一轮" in skill
```

Extend `test_setup_and_guidance_are_portable` with:

```python
assert "python -m app.cli init-product" in readme
assert "1688价格和库存" in readme
assert "PDF规格书" in readme
assert "四张" in readme
```

- [ ] **Step 3: Run contract tests and verify RED**

Run:

```powershell
python -m pytest tests/unit/test_upload_skill_contract.py tests/unit/test_distribution_contract.py -q
```

Expected: new assertions fail because the onboarding command and stop rule are undocumented.

- [ ] **Step 4: Update the Skill minimally from the baseline failures**

Insert this immediately after project-root and model resolution:

```markdown
3. 在任何 `doctor`、`prepare`、Chrome 会话检查或上传锁之前，运行资料初始化向导：
   ```powershell
   python -m app.cli init-product "<MODEL>" --root "<PROJECT_ROOT>"
   ```
   - `price_inventory.xlsx` 用于提供当前完整型号的1688价格和库存；型号保留 `/`，价格和库存留空时分别使用 `10000` 和 `50`。
   - `data/draft_saved/<FOLDER_KEY>/` 用于保存当前型号的原始资料；目录名去掉 `/`，其中需要至少一份包含完整型号的 PDF 规格书和至少四张真实产品照片。
   - 如果返回 `NEEDS_INPUT`，向使用者列出 `created`、逐项转述 `requirements` 的用途和操作，随后停止。不得在同一轮再次运行向导或进入浏览器；等待使用者补充并重新调用 Skill。
```

Renumber later steps without changing their existing safety behavior.

- [ ] **Step 5: Update README with the generated-versus-user-supplied boundary**

Add a “首次资料向导” subsection containing the exact command, the two generated paths, their purposes, the required PDF/four photos, and this continuation rule:

```markdown
首次运行若创建了模板或资料尚不完整，会输出 `NEEDS_INPUT` 并停止。补充、核对资料后，用同一型号再次调用 Skill。`automation/` JSON、详情页和 `upload_optimized/` 图片由程序生成，不需要手写。
```

- [ ] **Step 6: Run the same Skill scenario with the updated Skill**

Give a fresh subagent the exact Task 4 Step 1 scenario plus the updated `SKILL.md`. Verify its response:

1. runs `init-product` first;
2. explains the workbook purpose and blank defaults;
3. explains the folder naming and PDF/four-photo requirement;
4. stops on `NEEDS_INPUT` before Chrome, `prepare`, or upload.

If it finds a new ambiguity, tighten only the relevant Skill sentence and rerun the same scenario.

- [ ] **Step 7: Run contract tests and verify GREEN**

Run:

```powershell
python -m pytest tests/unit/test_upload_skill_contract.py tests/unit/test_distribution_contract.py -q
```

Expected: all selected tests pass.

- [ ] **Step 8: Commit Skill and documentation**

```powershell
git add plugins/auto-alibaba/skills/upload-1688-products/SKILL.md tests/unit/test_upload_skill_contract.py README.md tests/unit/test_distribution_contract.py
git commit -m "docs: guide first-time product inputs"
```

### Task 5: Deployment synchronization and full verification

**Files:**
- Copy from: `plugins/auto-alibaba/skills/upload-1688-products/`
- Copy to: `C:/Users/小城/.codex/skills/upload-1688-products/`
- Verify all changed tracked files.

- [ ] **Step 1: Run the complete automated suite**

```powershell
python -m pytest -q
python -m ruff check .
python -m mypy app
```

Expected: zero test failures, zero Ruff violations, and mypy exits `0`.

- [ ] **Step 2: Validate the Plugin and Skill packages**

Run the installed Plugin validator and Skill validator:

```powershell
python "C:\Users\小城\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py" "D:\Auto-Alibab\plugins\auto-alibaba"
python "C:\Users\小城\.codex\skills\.system\skill-creator\scripts\quick_validate.py" "D:\Auto-Alibab\plugins\auto-alibaba\skills\upload-1688-products"
Get-ChildItem "D:\Auto-Alibab\plugins\auto-alibaba\skills\upload-1688-products\scripts" -Filter *.py | ForEach-Object { python -m py_compile $_.FullName }
```

Expected: both validators exit `0`. Also compile all Python files under the bundled Skill scripts with `python -m py_compile`.

- [ ] **Step 3: Verify the setup and public-payload boundary**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1 -CheckOnly
git ls-files
git diff --check HEAD
```

Confirm no tracked file includes `price_inventory.xlsx`, product PDFs/photos, `data/draft_saved`, `automation` runtime JSON, `.chrome-profile`, credentials, tokens, the original local username, or fixed personal filesystem paths in the distributable Plugin.

- [ ] **Step 4: Sync the installed Skill only after repository verification passes**

Use a recursive copy from the bundled Skill directory to `C:/Users/小城/.codex/skills/upload-1688-products/`, then byte-compare all relative files. The `writing-skills` deployment gate requires the tested repository copy to be the source of truth.

- [ ] **Step 5: Perform a clean temporary-directory smoke test**

Run `init-product` against a temporary root and model `W3G800-KS39-03/F01`. Verify JSON status `NEEDS_INPUT`, the Excel row contains the exact model, the folder is `W3G800-KS39-03F01`, and no `automation`, `.uploader.lock`, or browser state is created.

- [ ] **Step 6: Push the verified main branch**

```powershell
git status --short
git log -5 --oneline
git push origin main
```

Expected: only the known unrelated untracked files remain locally, and GitHub `main` advances to the verified onboarding commits.
