# Agent-First Beginner Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让第一次从 GitHub 拉取项目的电脑小白，只向外部智能体提供真实型号、规格书 PDF、至少四张真实照片、价格和库存，就能被一步一步带到现有高质量上传流程，并且永远不会因示例值创建错误商品资料。

**Architecture:** 外部智能体继续作为唯一“智能大脑”；仓库新增一个无默认型号的 PowerShell 稳定入口，并由 `app.cli onboard` 提供唯一的确定性资料状态机。状态机复用现有型号、Excel 和目录逻辑，文档与仓库 Skill 只负责按状态引导，不复制业务判断。原始 PDF、照片、Excel、`data/` 和 `automation/` 均按不可破坏的用户业务资料处理。

**Tech Stack:** Python 3.12、Typer、openpyxl、PowerShell 5.1、pytest、ruff、mypy、Markdown、Codex Plugin Skill

---

**执行约束：** 用户已经明确要求不要生成子代理。因此实现本计划时默认使用 `superpowers:executing-plans`，由主智能体逐任务执行；只有用户以后明确要求委派或并行代理时，才允许改用子代理。开始任何任务前先运行 `git status --short`，保留所有与本计划无关的已有修改，并且每次只显式暂存本任务列出的文件。

## Task 1: 取消空价格/库存默认值，建立真实输入硬边界

**Files:**
- Modify: `app/ingest/inventory.py`
- Modify: `app/products/input_onboarding.py`
- Modify: `tests/unit/ingest/test_inventory.py`
- Modify: `tests/unit/products/test_input_onboarding.py`

- [ ] **Step 1: 先把旧的“空值使用默认值”测试改成失败测试**

在 `tests/unit/ingest/test_inventory.py` 中导入 `ManualReviewRequired`，将默认值测试改为：

```python
from app.domain.errors import ManualReviewRequired, ModelRowNotFound


def test_blank_price_and_stock_stop_product(workbook_path: Path) -> None:
    with pytest.raises(ManualReviewRequired, match="价格和库存不能为空"):
        load_inventory(workbook_path, "A2E250-AL06-01")
```

再补充只缺一个值时也明确指出缺失项：

```python
@pytest.mark.parametrize(
    ("price", "stock", "missing"),
    [(None, 8, "价格不能为空"), (120, None, "库存不能为空")],
)
def test_one_blank_inventory_value_stops_product(
    tmp_path: Path, price: object, stock: object, missing: str
) -> None:
    path = tmp_path / "price_inventory.xlsx"
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["型号", "价格", "库存"])
    sheet.append(["REAL-MODEL-01", price, stock])
    book.save(path)
    book.close()

    with pytest.raises(ManualReviewRequired, match=missing):
        load_inventory(path, "REAL-MODEL-01")
```

- [ ] **Step 2: 运行测试，确认当前默认值行为导致失败**

Run:

```powershell
python -m pytest tests/unit/ingest/test_inventory.py -q
```

Expected: `test_blank_price_and_stock_stop_product` 和参数化空值用例失败，因为当前实现仍返回 `10000`/`50`。

- [ ] **Step 3: 在库存读取层禁止虚构价格和库存**

将 `app/ingest/inventory.py` 改为保留精确型号匹配，但取消 `default_price` 和 `default_stock` 参数：

```python
from dataclasses import dataclass
from pathlib import Path

import openpyxl

from app.domain.errors import ManualReviewRequired, ModelRowNotFound
from app.domain.models import InventoryRecord
from app.ingest.model_number import normalize_model


@dataclass(frozen=True)
class InventoryValuePresence:
    price_present: bool
    stock_present: bool


def _is_present(value: object) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def inspect_inventory_values(workbook_path: Path, model: str) -> InventoryValuePresence:
    wanted = normalize_model(model)
    book = openpyxl.load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        sheet = book.active
        for raw_model, price, stock, *_ in sheet.iter_rows(min_row=2, values_only=True):
            if raw_model is None or normalize_model(str(raw_model)) != wanted:
                continue
            return InventoryValuePresence(
                price_present=_is_present(price),
                stock_present=_is_present(stock),
            )
    finally:
        book.close()
    raise ModelRowNotFound(f"model row does not exist: {wanted}")


def load_inventory(workbook_path: Path, model: str) -> InventoryRecord:
    wanted = normalize_model(model)
    book = openpyxl.load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        sheet = book.active
        for raw_model, price, stock, *_ in sheet.iter_rows(min_row=2, values_only=True):
            if raw_model is None or normalize_model(str(raw_model)) != wanted:
                continue
            missing = [
                name
                for name, value in (("价格", price), ("库存", stock))
                if not _is_present(value)
            ]
            if missing:
                raise ManualReviewRequired(
                    f"{wanted} 的{'和'.join(missing)}不能为空；请填写真实值后重试"
                )
            try:
                return InventoryRecord(model=wanted, price=int(price), stock=int(stock))
            except (TypeError, ValueError) as error:
                raise ManualReviewRequired(
                    f"{wanted} 的价格和库存必须是有效数字；未修改原表"
                ) from error
    finally:
        book.close()
    raise ModelRowNotFound(f"model row does not exist: {wanted}")
```

这一步故意把规则放在所有准备和上传入口共同使用的 `load_inventory()` 中，确保即使有人绕过新手文档，空值也不能进入上传。

- [ ] **Step 4: 更新资料初始化提示，不再宣称存在默认价格/库存**

将 `app/products/input_onboarding.py` 中库存 action 改为：

```python
action="打开表格，在当前完整型号行填写真实价格和真实库存；两项都不能留空。",
```

在 `tests/unit/products/test_input_onboarding.py` 的第一个测试加入：

```python
assert "真实价格" in requirements["inventory"].action
assert "不能留空" in requirements["inventory"].action
assert "10000" not in requirements["inventory"].action
```

- [ ] **Step 5: 运行聚焦测试和静态检查**

Run:

```powershell
python -m pytest tests/unit/ingest/test_inventory.py tests/unit/products/test_input_onboarding.py -q
python -m ruff check app/ingest/inventory.py app/products/input_onboarding.py tests/unit/ingest/test_inventory.py tests/unit/products/test_input_onboarding.py
python -m mypy app/ingest/inventory.py app/products/input_onboarding.py
```

Expected: 全部通过，空值不再产生任何业务默认值。

- [ ] **Step 6: 只提交本任务文件**

```powershell
git add app/ingest/inventory.py app/products/input_onboarding.py tests/unit/ingest/test_inventory.py tests/unit/products/test_input_onboarding.py
git commit -m "fix: require explicit price and stock"
```

## Task 2: 实现无默认型号的单商品资料状态机

**Files:**
- Create: `app/products/onboarding.py`
- Create: `tests/unit/products/test_onboarding.py`

- [ ] **Step 1: 为全部状态和数据保护规则写失败测试**

创建 `tests/unit/products/test_onboarding.py`，覆盖以下完整场景：

```python
from pathlib import Path

import openpyxl

from app.products.onboarding import onboard_product

MODEL = "REAL-AC-FAN/01"
FOLDER_KEY = "REAL-AC-FAN01"


def _write_workbook(path: Path, price: object, stock: object) -> None:
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["型号", "价格", "库存"])
    sheet.append([MODEL, price, stock])
    book.save(path)
    book.close()


def _add_source_files(root: Path, *, pdfs: int = 1, images: int = 4) -> Path:
    source = root / "data" / "draft_saved" / FOLDER_KEY
    source.mkdir(parents=True, exist_ok=True)
    for index in range(pdfs):
        (source / f"spec-{index}.pdf").write_bytes(b"%PDF-real-input")
    for index in range(images):
        (source / f"photo-{index}.jpg").write_bytes(b"real-image-input")
    return source


def test_no_model_is_read_only_and_requests_only_model(tmp_path: Path) -> None:
    result = onboard_product(tmp_path, None)

    assert result.status == "NEEDS_MODEL"
    assert result.model is None
    assert result.created == ()
    assert "完整型号" in result.next_action
    assert list(tmp_path.iterdir()) == []


def test_real_model_creates_only_exact_row_and_folder(tmp_path: Path) -> None:
    result = onboard_product(tmp_path, MODEL)

    assert result.status == "NEEDS_PRICE_STOCK"
    assert result.model == MODEL
    assert result.folder_key == FOLDER_KEY
    assert (tmp_path / "price_inventory.xlsx").is_file()
    assert (tmp_path / "data" / "draft_saved" / FOLDER_KEY).is_dir()
    assert not (tmp_path / "automation").exists()

    book = openpyxl.load_workbook(tmp_path / "price_inventory.xlsx", read_only=True)
    try:
        rows = list(book.active.iter_rows(values_only=True))
    finally:
        book.close()
    assert rows == [("型号", "价格", "库存"), (MODEL, None, None)]


def test_price_and_stock_are_requested_before_source_files(tmp_path: Path) -> None:
    _write_workbook(tmp_path / "price_inventory.xlsx", None, None)
    _add_source_files(tmp_path, pdfs=0, images=0)

    result = onboard_product(tmp_path, MODEL)

    assert result.status == "NEEDS_PRICE_STOCK"
    assert result.checks["price_present"] is False
    assert result.checks["stock_present"] is False
    assert "价格和库存" in result.next_action


def test_missing_pdf_is_the_only_next_source_action(tmp_path: Path) -> None:
    _write_workbook(tmp_path / "price_inventory.xlsx", 120, 8)
    _add_source_files(tmp_path, pdfs=0, images=4)

    result = onboard_product(tmp_path, MODEL)

    assert result.status == "NEEDS_SOURCE_FILES"
    assert "PDF" in result.next_action
    assert "照片" not in result.next_action


def test_missing_photos_reports_exact_remaining_count(tmp_path: Path) -> None:
    _write_workbook(tmp_path / "price_inventory.xlsx", 120, 8)
    _add_source_files(tmp_path, pdfs=1, images=2)

    result = onboard_product(tmp_path, MODEL)

    assert result.status == "NEEDS_SOURCE_FILES"
    assert "2张" in result.next_action


def test_complete_inputs_are_ready_to_upload(tmp_path: Path) -> None:
    _write_workbook(tmp_path / "price_inventory.xlsx", 120, 8)
    source = _add_source_files(tmp_path)

    result = onboard_product(tmp_path, MODEL)

    assert result.ok is True
    assert result.status == "READY_TO_UPLOAD"
    assert result.paths["source_directory"] == str(source.resolve())


def test_repeat_run_preserves_business_files_and_does_not_duplicate_row(
    tmp_path: Path,
) -> None:
    _write_workbook(tmp_path / "price_inventory.xlsx", 120, 8)
    source = _add_source_files(tmp_path)
    protected = source / "用户原图.jpg"
    protected.write_bytes(b"do-not-change")

    first = onboard_product(tmp_path, MODEL)
    second = onboard_product(tmp_path, MODEL)

    assert first.status == second.status == "READY_TO_UPLOAD"
    assert protected.read_bytes() == b"do-not-change"
    book = openpyxl.load_workbook(tmp_path / "price_inventory.xlsx", read_only=True)
    try:
        models = [row[0] for row in book.active.iter_rows(min_row=2, values_only=True)]
    finally:
        book.close()
    assert models == [MODEL]
```

另加一个多目录保护测试：先建立 `data/draft_saved/OTHER-MODEL/keep.pdf`，再初始化 `MODEL`，断言原文件字节不变且原目录仍存在。

- [ ] **Step 2: 运行测试，确认模块尚不存在**

Run:

```powershell
python -m pytest tests/unit/products/test_onboarding.py -q
```

Expected: collection 阶段因 `app.products.onboarding` 不存在而失败。

- [ ] **Step 3: 创建结构化状态结果和状态优先级**

创建 `app/products/onboarding.py`：

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.ingest.inventory import inspect_inventory_values, load_inventory
from app.products.input_onboarding import initialize_product_inputs


@dataclass(frozen=True)
class OnboardingResult:
    ok: bool
    status: str
    model: str | None
    folder_key: str | None
    created: tuple[str, ...]
    checks: dict[str, object]
    paths: dict[str, str]
    next_action: str
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "status": self.status,
            "model": self.model,
            "folder_key": self.folder_key,
            "created": list(self.created),
            "checks": self.checks,
            "paths": self.paths,
            "next_action": self.next_action,
            "message": self.message,
        }


def onboard_product(root: Path, model: str | None) -> OnboardingResult:
    resolved_root = root.resolve()
    if model is None or not model.strip():
        return OnboardingResult(
            ok=False,
            status="NEEDS_MODEL",
            model=None,
            folder_key=None,
            created=(),
            checks={"model_provided": False},
            paths={"project_root": str(resolved_root)},
            next_action="请告诉我准备上传商品的完整型号。",
            message="尚未提供真实型号；没有创建任何商品资料。",
        )

    initialized = initialize_product_inputs(resolved_root, model)
    workbook = resolved_root / "price_inventory.xlsx"
    source = resolved_root / "data" / "draft_saved" / initialized.folder_key
    presence = inspect_inventory_values(workbook, initialized.model)
    checks = {
        **initialized.checks,
        "model_provided": True,
        "price_present": presence.price_present,
        "stock_present": presence.stock_present,
    }
    paths = {
        "project_root": str(resolved_root),
        "inventory_workbook": str(workbook.resolve()),
        "source_directory": str(source.resolve()),
    }

    if not presence.price_present or not presence.stock_present:
        missing = [
            name
            for name, present in (
                ("价格", presence.price_present),
                ("库存", presence.stock_present),
            )
            if not present
        ]
        next_action = (
            f"请在已打开的 Excel 中填写当前完整型号的{'和'.join(missing)}，填写后告诉我“已填好”。"
        )
        return OnboardingResult(
            False,
            "NEEDS_PRICE_STOCK",
            initialized.model,
            initialized.folder_key,
            initialized.created,
            checks,
            paths,
            next_action,
            next_action,
        )

    load_inventory(workbook, initialized.model)
    pdf_count = int(initialized.checks["pdf_files"])
    image_count = int(initialized.checks["source_images"])
    if pdf_count < 1:
        next_action = (
            "请把至少一份包含当前完整型号的规格书 PDF，直接放入已打开的型号文件夹，完成后告诉我“已放好”。"
        )
        status = "NEEDS_SOURCE_FILES"
    elif image_count < 4:
        remaining = 4 - image_count
        next_action = (
            f"请再把{remaining}张当前型号的真实产品照片直接放入已打开的型号文件夹，完成后告诉我“已放好”。"
        )
        status = "NEEDS_SOURCE_FILES"
    else:
        next_action = "当前型号资料齐全；可以进入证据准备和1688上传流程。"
        status = "READY_TO_UPLOAD"

    return OnboardingResult(
        status == "READY_TO_UPLOAD",
        status,
        initialized.model,
        initialized.folder_key,
        initialized.created,
        checks,
        paths,
        next_action,
        next_action,
    )
```

实现时保持以下顺序不变：真实型号 → 价格/库存 → PDF → 照片 → 就绪。这样每次只给用户一个动作。

- [ ] **Step 4: 运行状态机测试和静态检查**

Run:

```powershell
python -m pytest tests/unit/products/test_onboarding.py tests/unit/products/test_input_onboarding.py tests/unit/ingest/test_inventory.py -q
python -m ruff check app/products/onboarding.py tests/unit/products/test_onboarding.py
python -m mypy app/products/onboarding.py
```

Expected: 全部通过；无型号测试的临时目录保持完全为空。

- [ ] **Step 5: 只提交状态机文件**

```powershell
git add app/products/onboarding.py tests/unit/products/test_onboarding.py
git commit -m "feat: add beginner product onboarding states"
```

## Task 3: 新增 `app.cli onboard` 和安全打开路径能力

**Files:**
- Modify: `app/cli.py`
- Create: `tests/unit/test_onboard_cli.py`

- [ ] **Step 1: 为 CLI 状态、退出码和 `--open` 写失败测试**

创建 `tests/unit/test_onboard_cli.py`。测试必须使用虚构测试型号 `REAL-AC-FAN/01`，不能把任何业务型号写入新手入口：

```python
import json
from pathlib import Path

from typer.testing import CliRunner

import app.cli as cli_module
from app.domain.errors import ManualReviewRequired
from app.products.onboarding import OnboardingResult


def _result(tmp_path: Path, status: str) -> OnboardingResult:
    model = None if status == "NEEDS_MODEL" else "REAL-AC-FAN/01"
    folder_key = None if model is None else "REAL-AC-FAN01"
    return OnboardingResult(
        ok=status == "READY_TO_UPLOAD",
        status=status,
        model=model,
        folder_key=folder_key,
        created=(),
        checks={},
        paths={
            "project_root": str(tmp_path),
            "inventory_workbook": str(tmp_path / "price_inventory.xlsx"),
            "source_directory": str(tmp_path / "data" / "draft_saved" / "REAL-AC-FAN01"),
        },
        next_action="下一步",
        message="状态说明",
    )


def test_onboard_without_model_returns_actionable_state_and_exit_zero(
    monkeypatch, tmp_path: Path
) -> None:
    expected = _result(tmp_path, "NEEDS_MODEL")
    monkeypatch.setattr(cli_module, "onboard_product", lambda root, model: expected)

    result = CliRunner().invoke(cli_module.app, ["onboard", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == expected.to_dict()


def test_onboard_forwards_explicit_model(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake(root: Path, model: str | None) -> OnboardingResult:
        captured.update(root=root, model=model)
        return _result(tmp_path, "NEEDS_PRICE_STOCK")

    monkeypatch.setattr(cli_module, "onboard_product", fake)
    result = CliRunner().invoke(
        cli_module.app,
        ["onboard", "--root", str(tmp_path), "--model", "REAL-AC-FAN/01"],
    )

    assert result.exit_code == 0
    assert captured["model"] == "REAL-AC-FAN/01"


def test_onboard_open_opens_only_inventory_and_source_paths(
    monkeypatch, tmp_path: Path
) -> None:
    expected = _result(tmp_path, "NEEDS_SOURCE_FILES")
    opened: list[Path] = []
    monkeypatch.setattr(cli_module, "onboard_product", lambda root, model: expected)
    monkeypatch.setattr(cli_module, "open_local_path", opened.append)

    result = CliRunner().invoke(
        cli_module.app,
        ["onboard", "--root", str(tmp_path), "--model", "REAL-AC-FAN/01", "--open"],
    )

    assert result.exit_code == 0
    assert opened == [
        Path(expected.paths["inventory_workbook"]),
        Path(expected.paths["source_directory"]),
    ]


def test_onboard_blocked_is_json_and_exit_two(monkeypatch, tmp_path: Path) -> None:
    def fail(root: Path, model: str | None) -> OnboardingResult:
        raise ManualReviewRequired("库存表被占用或格式错误；未覆盖原文件")

    monkeypatch.setattr(cli_module, "onboard_product", fail)
    result = CliRunner().invoke(
        cli_module.app,
        ["onboard", "--root", str(tmp_path), "--model", "REAL-AC-FAN/01"],
    )

    payload = json.loads(result.stdout)
    assert result.exit_code == 2
    assert payload["status"] == "BLOCKED"
    assert "未覆盖原文件" in payload["message"]
```

再补两个保护测试：无型号即使传入 `--open` 也不调用 opener；目标路径不存在时 `open_local_path()` 抛出 `ManualReviewRequired` 而不是创建或猜测路径。

- [ ] **Step 2: 运行 CLI 测试，确认命令不存在**

Run:

```powershell
python -m pytest tests/unit/test_onboard_cli.py -q
```

Expected: 因 `onboard` 命令和导入尚不存在而失败。

- [ ] **Step 3: 在 CLI 中实现唯一业务入口和 Windows 安全 opener**

在 `app/cli.py` 顶部增加：

```python
import os

from app.products.onboarding import OnboardingResult, onboard_product
```

增加安全打开函数：

```python
def open_local_path(path: Path) -> None:
    resolved = path.resolve()
    if not resolved.exists():
        raise ManualReviewRequired(f"需要打开的路径不存在，未创建替代路径: {resolved}")
    startfile = getattr(os, "startfile", None)
    if startfile is None:
        raise ManualReviewRequired(f"当前系统无法自动打开路径: {resolved}")
    startfile(str(resolved))


def _open_onboarding_inputs(result: OnboardingResult) -> None:
    if result.model is None:
        return
    open_local_path(Path(result.paths["inventory_workbook"]))
    open_local_path(Path(result.paths["source_directory"]))
```

增加命令：

```python
@app.command()
def onboard(
    root: Annotated[Path, typer.Option("--root", help="商品资料工作区")] = Path("."),
    model: Annotated[
        str | None, typer.Option("--model", help="用户明确提供的完整商品型号")
    ] = None,
    open_inputs: Annotated[
        bool, typer.Option("--open", help="打开价格库存表和当前型号资料目录")
    ] = False,
) -> None:
    """Return the next beginner-safe onboarding action as JSON."""
    try:
        result = onboard_product(root.resolve(), model)
        if open_inputs:
            _open_onboarding_inputs(result)
        payload = result.to_dict()
    except AutomationError as error:
        payload = {
            "ok": False,
            "status": "BLOCKED",
            "model": model,
            "folder_key": None,
            "created": [],
            "checks": {},
            "paths": {"project_root": str(root.resolve())},
            "next_action": str(error),
            "message": str(error),
        }
    typer.echo(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    if payload["status"] == "BLOCKED":
        raise typer.Exit(code=2)
```

`NEEDS_MODEL`、`NEEDS_PRICE_STOCK` 和 `NEEDS_SOURCE_FILES` 都是智能体可继续处理的正常状态，因此退出码为 `0`；只有 `BLOCKED` 使用退出码 `2`。

- [ ] **Step 4: 运行所有 CLI 相关测试和静态检查**

Run:

```powershell
python -m pytest tests/unit/test_onboard_cli.py tests/unit/test_init_product_cli.py tests/unit/test_cli.py -q
python -m ruff check app/cli.py tests/unit/test_onboard_cli.py
python -m mypy app/cli.py
```

Expected: 新旧 CLI 入口均通过；`init-product` 保持兼容。

- [ ] **Step 5: 只提交 CLI 文件**

```powershell
git add app/cli.py tests/unit/test_onboard_cli.py
git commit -m "feat: expose agent onboarding command"
```

## Task 4: 新增所有智能体通用的 PowerShell 稳定入口

**Files:**
- Create: `agent-onboard.ps1`
- Modify: `tests/unit/test_distribution_contract.py`

- [ ] **Step 1: 写脚本契约和无型号无写入测试**

在 `tests/unit/test_distribution_contract.py` 增加：

```python
import shutil

import pytest


def test_agent_onboard_is_model_free_and_forwards_only_explicit_model() -> None:
    script = (ROOT / "agent-onboard.ps1").read_text(encoding="utf-8")

    assert "[string]$Model" in script
    assert '"--model"' in script
    assert "app.cli" in script
    assert '"onboard"' in script
    assert "init-product" not in script
    assert "W3G800" not in script
    assert "W3G630" not in script
    assert "Remove-Item" not in script
    assert "Move-Item" not in script


@pytest.mark.skipif(shutil.which("powershell") is None, reason="Windows PowerShell required")
def test_agent_onboard_without_model_does_not_create_business_data(
    tmp_path: Path,
) -> None:
    clone = tmp_path / "clean-project"
    shutil.copytree(ROOT / "app", clone / "app")
    for name in ("agent-onboard.ps1", "pyproject.toml"):
        shutil.copy2(ROOT / name, clone / name)

    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(clone / "agent-onboard.ps1"),
        ],
        cwd=clone,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )

    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    assert payload["status"] in {"NEEDS_SETUP", "NEEDS_MODEL"}
    assert not (clone / "price_inventory.xlsx").exists()
    assert not (clone / "data").exists()
    assert not (clone / "automation").exists()
```

- [ ] **Step 2: 运行测试，确认根入口尚不存在**

Run:

```powershell
python -m pytest tests/unit/test_distribution_contract.py -q
```

Expected: 新增测试因 `agent-onboard.ps1` 不存在而失败。

- [ ] **Step 3: 创建只做环境适配和转发的 `agent-onboard.ps1`**

创建根目录 `agent-onboard.ps1`，参数和行为固定如下：

```powershell
param(
    [string]$Model,
    [switch]$Open
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$Root = $PSScriptRoot

function Write-SetupState {
    param([string]$Check, [string]$Action)
    [ordered]@{
        ok = $false
        status = "NEEDS_SETUP"
        model = if ([string]::IsNullOrWhiteSpace($Model)) { $null } else { $Model }
        checks = [ordered]@{ failed = $Check }
        paths = [ordered]@{ project_root = $Root }
        next_action = $Action
        message = $Action
    } | ConvertTo-Json -Compress -Depth 5
    exit 0
}

foreach ($RelativePath in @("pyproject.toml", "app\cli.py")) {
    if (-not (Test-Path -LiteralPath (Join-Path $Root $RelativePath))) {
        Write-SetupState "project_file" "项目文件 $RelativePath 缺失；请重新完整拉取项目。"
    }
}

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $VenvPython) {
    $Python = $VenvPython
}
else {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $PythonCommand) {
        Write-SetupState "python" "请先安装 Python 3.12 或更高版本，安装后告诉我“已安装”。"
    }
    $Python = $PythonCommand.Source
}

& $Python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-SetupState "python_version" "当前 Python 版本低于 3.12；请安装 Python 3.12 或更高版本。"
}

$ChromeCandidates = @(
    (Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Google\Chrome\Application\chrome.exe"),
    (Join-Path $env:LOCALAPPDATA "Google\Chrome\Application\chrome.exe")
) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
if (($ChromeCandidates | Where-Object { Test-Path -LiteralPath $_ }).Count -eq 0) {
    Write-SetupState "chrome" "请先安装 Google Chrome，安装后告诉我“已安装”。"
}

$PreviousLocation = Get-Location
Set-Location $Root
try {
    & $Python -c "import app.cli"
    $ImportExitCode = $LASTEXITCODE
}
finally {
    Set-Location $PreviousLocation
}
if ($ImportExitCode -ne 0) {
    Write-SetupState "dependencies" "项目依赖尚未安装；请让智能体运行根目录 setup.ps1。"
}

$Arguments = @("-m", "app.cli", "onboard", "--root", $Root)
if (-not [string]::IsNullOrWhiteSpace($Model)) {
    $Arguments += @("--model", $Model)
}
if ($Open) {
    $Arguments += "--open"
}

Push-Location $Root
try {
    & $Python @Arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
```

环境脚本不得自动安装软件、创建示例型号、调用上传或删除路径。它只返回当前第一个未满足条件，或转发到 Python 状态机。

- [ ] **Step 4: 运行脚本契约、CLI 和 setup 检查**

Run:

```powershell
python -m pytest tests/unit/test_distribution_contract.py tests/unit/test_onboard_cli.py -q
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1 -CheckOnly
powershell -NoProfile -ExecutionPolicy Bypass -File .\agent-onboard.ps1
```

Expected: 测试通过；最后一条命令返回 `NEEDS_MODEL` 或真实的单项 `NEEDS_SETUP`，并且没有创建新商品资料。

- [ ] **Step 5: 只提交通用入口与测试**

```powershell
git add agent-onboard.ps1 tests/unit/test_distribution_contract.py
git commit -m "feat: add universal agent onboarding entry"
```

## Task 5: 建立小白第一屏、智能体协议和双击备用入口

**Files:**
- Create: `START-HERE.md`
- Create: `开始使用.ps1`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `tests/unit/test_distribution_contract.py`

- [ ] **Step 1: 先写文档内容和双击入口的失败契约**

在 `tests/unit/test_distribution_contract.py` 增加：

```python
def test_beginner_guidance_states_exact_user_inputs_and_locations() -> None:
    start = (ROOT / "START-HERE.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    for phrase in (
        "完整型号",
        "规格书 PDF",
        "至少四张",
        "价格",
        "库存",
        "price_inventory.xlsx",
        "data/draft_saved/<FOLDER_KEY>/",
    ):
        assert phrase in start
    assert "品牌、参数、标题、SKU、JSON 和详情页由智能体" in start
    assert "不要创建示例型号" in start
    assert "不要删除、移动或覆盖" in start
    assert "START-HERE.md" in readme
    assert "一次只" in agents
    assert "未经用户明确授权" in agents


def test_beginner_facing_guidance_has_no_fixed_business_model() -> None:
    for relative in ("START-HERE.md", "README.md", "AGENTS.md"):
        content = (ROOT / relative).read_text(encoding="utf-8")
        assert "W3G800-KS39-03/F01" not in content
        assert "W3G630-NU33-03" not in content


def test_double_click_entry_only_opens_project_and_instructions() -> None:
    script = (ROOT / "开始使用.ps1").read_text(encoding="utf-8")

    assert "$PSScriptRoot" in script
    assert "START-HERE.md" in script
    assert "Start-Process" in script
    for forbidden in (
        "app.cli",
        "setup.ps1",
        "agent-onboard.ps1",
        "run_upload",
        "chrome.exe",
        "Remove-Item",
        "Move-Item",
    ):
        assert forbidden not in script


def test_setup_never_initializes_a_product() -> None:
    setup = (ROOT / "setup.ps1").read_text(encoding="utf-8")

    assert "init-product" not in setup
    assert "app.cli onboard" not in setup
```

同时把旧 `test_setup_and_guidance_are_portable()` 中要求 README 出现 `init-product` 的断言，改为要求出现 `agent-onboard.ps1` 和 `START-HERE.md`。

- [ ] **Step 2: 运行文档契约，确认新文件缺失**

Run:

```powershell
python -m pytest tests/unit/test_distribution_contract.py -q
```

Expected: 因 `START-HERE.md` 和 `开始使用.ps1` 尚不存在而失败。

- [ ] **Step 3: 创建 `START-HERE.md` 第一屏**

文件开头必须直接面向小白，不先展示命令：

```markdown
# 从这里开始：让智能体带你上传第一个商品

这个项目必须配合 Codex、WorkBuddy 或其他能运行 PowerShell 和 Python 的智能体使用。你不需要懂代码，也不需要自己制作商品 JSON。

把下面这句话直接发给智能体：

> 开始使用这个项目。我是电脑小白。请先读取 START-HERE.md 和 AGENTS.md，再一步一步带我操作；一次只告诉我一个动作。不要创建示例型号，也不要删除、移动或覆盖我的商品资料。

## 这个项目需要你准备什么

电脑首次使用需要 Windows、Google Chrome、你自己的 1688 账号，以及一个能运行本地命令的智能体。

每个商品只需要你提供：

1. 完整型号；
2. 至少一份包含该完整型号的规格书 PDF；
3. 至少四张该型号真实产品照片；
4. 价格；
5. 库存。

品牌、参数、标题、SKU、JSON 和详情页由智能体从当前型号的规格书或照片中处理。规格书和照片没有的普通值不填写，关键值无法确认时停止。

## 文件放在哪里

- 价格和库存填写在项目根目录的 `price_inventory.xlsx`。
- 规格书 PDF 和照片直接放进 `data/draft_saved/<FOLDER_KEY>/`，不需要建立子文件夹，文件名也不限制。
- 智能体获得你的真实型号后会创建或复用正确位置，并自动打开 Excel 和型号文件夹；你不需要自己寻找目录。
- `automation/<FOLDER_KEY>/` 由程序生成，不需要打开或编辑。

## 你实际只做五步

1. 告诉智能体准备上传的完整型号。
2. 在智能体打开的 Excel 中填写该型号的价格和库存。
3. 把规格书 PDF 和至少四张真实照片放进智能体打开的型号文件夹。
4. 告诉智能体“资料放好了”，需要时在专用 Chrome 中登录 1688。
5. 检查智能体填好的 1688 页面；程序会停在“保存草稿”前，不会替你保存或发布。

> 重要：没有真实型号时不要创建任何型号行或资料目录。未经你的明确允许，不得删除、移动、改名或覆盖 `data/`、`automation/`、`price_inventory.xlsx`、PDF、照片和浏览器资料。
```

- [ ] **Step 4: 扩展 `AGENTS.md` 为跨智能体强制协议**

保留首行 `# Auto-Alibaba Repository Guidance`，随后明确加入：

```markdown
## Beginner onboarding protocol

- When the user says “开始使用”, is new to the project, or asks where files go, read `START-HERE.md` first and run `agent-onboard.ps1` without a model.
- Treat Codex, WorkBuddy, or another command-capable external agent as required; the repository does not contain an AI model.
- Before the user provides a real complete model, do not run `init-product`, pass `--model`, create workbook rows, or create product directories.
- Ask for one actionable item at a time. Translate structured states into short Chinese and do not make a beginner read JSON or copy commands.
- After receiving the exact model, run `agent-onboard.ps1 -Model "<完整型号>" -Open`. Re-run the same command after the user says the requested input is ready.
- Ask the user only for the exact model, one matching PDF, at least four real photos, price, and stock. Derive brand and supported listing content from current evidence only.
- The bundled Codex Plugin is optional. The repository entry and upload scripts remain the source of truth for every compatible agent.

## Non-destructive business-data boundary

- Treat `data/`, `automation/`, `price_inventory.xlsx`, PDFs, photos, `.chrome-profile/`, cookies, credentials, and `.env` as protected user-owned data.
- Without explicit permission for exact paths, never delete, move, rename, overwrite, clean, reset, or replace protected business data, including during Git/worktree cleanup.
- Reuse existing model folders and exact Excel rows. Never clear a folder or rewrite an existing price or stock value during onboarding.
- Never invent a sample/default product model, brand, technical value, SKU value, package value, price, or stock.
```

保留已有的上传质量、安全和验证规则。

- [ ] **Step 5: 重写 README 首次使用部分并删除可复制的固定型号**

README 第一部分改为：

1. 项目定位：外部智能体必需，内置 AI 不存在；
2. 克隆后首先阅读 `[START-HERE.md](START-HERE.md)`；
3. 新用户直接发送自然语言提示，不需要复制命令；
4. `agent-onboard.ps1` 作为高级/智能体入口；
5. 高级命令全部使用 `"<完整型号>"` 参数，不出现具体业务型号；
6. 明确价格和库存不能为空，移除 `10000`/`50` 默认值说明；
7. 保留现有 GEO 详情、单 SKU、相册、质量检查和保存边界说明。

高级示例统一写为：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\agent-onboard.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\agent-onboard.ps1 -Model "<完整型号>" -Open
python -m app.cli prepare "<完整型号>" --root .
python -m app.cli run "<完整型号>" --root .
```

- [ ] **Step 6: 创建只读双击备用入口**

创建 `开始使用.ps1`：

```powershell
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Guide = Join-Path $Root "START-HERE.md"

Start-Process -FilePath "explorer.exe" -ArgumentList $Root
Start-Process -FilePath "notepad.exe" -ArgumentList $Guide
```

- [ ] **Step 7: 运行文档契约和关键词检查**

Run:

```powershell
python -m pytest tests/unit/test_distribution_contract.py -q
rg -n "W3G800-KS39-03/F01|W3G630-NU33-03|默认值.*10000|留空.*10000" README.md START-HERE.md AGENTS.md plugins/auto-alibaba/skills/upload-1688-products/SKILL.md
```

Expected: pytest 通过。`rg` 此时只允许命中尚待 Task 6 更新的仓库 Skill，不能命中 README、`START-HERE.md` 或 `AGENTS.md`。

- [ ] **Step 8: 只提交新手入口和文档**

```powershell
git add START-HERE.md README.md AGENTS.md "开始使用.ps1" tests/unit/test_distribution_contract.py
git commit -m "docs: add agent-first beginner start guide"
```

## Task 6: 把上传 Skill 接入新状态机，但保持 Plugin 可选

**Files:**
- Modify: `plugins/auto-alibaba/skills/upload-1688-products/SKILL.md`
- Modify: `plugins/auto-alibaba/.codex-plugin/plugin.json`
- Modify: `tests/unit/test_upload_skill_contract.py`
- Sync after verification: active installed `upload-1688-products/SKILL.md`

- [ ] **Step 1: 把 Skill 契约测试改成新入口和新状态**

将 `test_skill_requires_product_input_guide_before_upload()` 改为：

```python
def test_skill_requires_agent_onboarding_before_upload() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    command = (
        'powershell -NoProfile -ExecutionPolicy Bypass -File '
        '"<PROJECT_ROOT>\\agent-onboard.ps1" -Model "<MODEL>" -Open'
    )
    assert command in skill
    assert skill.index("agent-onboard.ps1") < skill.index("ensure_chrome.ps1")
    for status in (
        "NEEDS_SETUP",
        "NEEDS_MODEL",
        "NEEDS_PRICE_STOCK",
        "NEEDS_SOURCE_FILES",
        "READY_TO_UPLOAD",
        "NEEDS_LOGIN",
        "READY_TO_SAVE",
    ):
        assert status in skill
    assert "价格和库存不能为空" in skill
    assert "Codex Plugin 不是必需条件" in skill
    assert "init-product" not in skill
    assert "10000" not in skill
    assert "不得在同一轮" in skill
```

再增加数据保护断言：

```python
def test_skill_protects_all_user_business_inputs() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    for phrase in (
        "不得删除、移动、改名、清空或覆盖",
        "price_inventory.xlsx",
        "data/",
        "automation/",
        "PDF",
        "照片",
        "明确授权",
    ):
        assert phrase in skill
```

- [ ] **Step 2: 运行 Skill 契约，确认旧流程失败**

Run:

```powershell
python -m pytest tests/unit/test_upload_skill_contract.py -q
```

Expected: 新入口、状态、空值和数据保护断言失败。

- [ ] **Step 3: 修改 Skill 的前置流程，不改后续质量标准**

将 `plugins/auto-alibaba/skills/upload-1688-products/SKILL.md` 的前置步骤替换为：

```markdown
1. 解析 `<PROJECT_ROOT>`。Codex Plugin 不是必需条件；只要当前智能体能运行 PowerShell 和 Python，就以仓库根目录入口为准。

2. 没有用户明确提供的真实完整型号时，先运行：

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File "<PROJECT_ROOT>\agent-onboard.ps1"
   ```

   只能转述 `NEEDS_SETUP` 或 `NEEDS_MODEL` 的 `next_action`，随后等待用户。不得创建示例型号。

3. 获得完整型号后，在任何 doctor、prepare、Chrome、锁或上传动作之前运行：

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File "<PROJECT_ROOT>\agent-onboard.ps1" -Model "<MODEL>" -Open
   ```

   - `NEEDS_SETUP`：只处理 `next_action` 指出的当前环境问题。
   - `NEEDS_PRICE_STOCK`：请用户在已打开 Excel 的当前精确型号行填写真实价格和库存；价格和库存不能为空。随后停止并等待用户说已填好。
   - `NEEDS_SOURCE_FILES`：只转述当前唯一 `next_action`，随后停止并等待用户。PDF 和照片直接放在已打开的型号目录。
   - `READY_TO_UPLOAD`：才允许继续现有 Chrome、doctor、证据准备和上传流程。
   - `BLOCKED`：准确报告 `message`，不得覆盖或替换已有文件。
   - 每次状态只要求一个动作；不得在同一轮假定用户已经完成并继续上传。
```

保留并复核后续所有已确认规则：当前证据、标题加权长度、一个精确 SKU、50/60Hz 同 SKU、丰富 GEO 详情、固定六张公司图在最后、相册满后递增一次、UTF-8、锁、图片指纹、质量检查一次、永远停在保存草稿前。

在 `Safety Boundary` 增加：

```markdown
`price_inventory.xlsx`、`data/`、`automation/`、PDF、照片和浏览器资料均为用户业务数据；未经用户针对具体路径明确授权，不得删除、移动、改名、清空或覆盖，也不得在 Git/worktree 清理时处理这些路径。
```

- [ ] **Step 4: 更新 Plugin cachebuster**

只修改 `plugins/auto-alibaba/.codex-plugin/plugin.json` 的 `version`，保持 `0.1.0+codex.` 前缀，并使用执行时的 14 位时间戳。用下面的 PowerShell 生成值，避免手填错误：

```powershell
Get-Date -Format yyyyMMddHHmmss
```

- [ ] **Step 5: 运行 Skill 契约和完整关键词回归**

Run:

```powershell
python -m pytest tests/unit/test_upload_skill_contract.py tests/unit/test_distribution_contract.py -q
rg -n "价格/库存为空时使用|留空时分别使用|init-product \"<MODEL>\"|W3G800-KS39-03/F01" README.md START-HERE.md AGENTS.md plugins/auto-alibaba/skills/upload-1688-products/SKILL.md
```

Expected: pytest 通过，`rg` 无输出。

- [ ] **Step 6: 同步当前机器已安装 Skill 并做字节级验证**

仅在仓库 Skill 测试通过后，执行机械同步：

```powershell
$Source = Resolve-Path .\plugins\auto-alibaba\skills\upload-1688-products\SKILL.md
$Target = Join-Path $HOME ".codex\skills\upload-1688-products\SKILL.md"
Copy-Item -LiteralPath $Source -Destination $Target -Force
(Get-FileHash -Algorithm SHA256 $Source).Hash
(Get-FileHash -Algorithm SHA256 $Target).Hash
```

Expected: 两个 SHA-256 完全一致。这个同步只覆盖 Skill 指令文件，不接触任何商品资料。

- [ ] **Step 7: 只提交仓库 Skill、manifest 和测试**

```powershell
git add plugins/auto-alibaba/skills/upload-1688-products/SKILL.md plugins/auto-alibaba/.codex-plugin/plugin.json tests/unit/test_upload_skill_contract.py
git commit -m "feat: route uploads through beginner onboarding"
```

## Task 7: 完整回归与全新克隆验收

**Files:**
- Verify only; do not edit user business data

- [ ] **Step 1: 先确认没有误暂存或误修改用户文件**

Run:

```powershell
git status --short
git diff --cached --name-only
```

Expected: 暂存区为空。所有实施前就存在的无关修改仍原样保留，没有被本计划的提交带走。不得为“清理状态”执行 reset、checkout、clean、递归删除或移动。

- [ ] **Step 2: 运行全部自动化验证**

Run:

```powershell
python -m pytest -q
python -m ruff check .
python -m mypy app
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1 -CheckOnly
```

Expected: pytest、ruff、mypy 和环境检查全部成功。若环境检查只因本机缺少外部软件失败，记录精确失败项；不要把它伪装成代码通过。

- [ ] **Step 3: 在独立全新克隆中验证“无型号零业务写入”**

先创建唯一临时路径，不覆盖已有目录：

```powershell
$SmokeRoot = Join-Path $env:TEMP ("Auto-Alibaba-onboard-" + [guid]::NewGuid().ToString("N"))
git clone --no-hardlinks . $SmokeRoot
Set-Location $SmokeRoot
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\agent-onboard.ps1
Test-Path .\price_inventory.xlsx
Test-Path .\data
Test-Path .\automation
```

Expected: onboarding 返回 `NEEDS_MODEL`；三个 `Test-Path` 都是 `False`。若 `NEEDS_SETUP`，先按其唯一动作完成环境，再重试，不能手工创建商品文件。

- [ ] **Step 4: 在同一临时克隆验证真实显式型号只创建对应输入**

使用只用于验收的测试型号，不使用任何真实业务型号：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\agent-onboard.ps1 -Model "ACCEPTANCE-FAN/001"
```

Expected:

- 返回 `NEEDS_PRICE_STOCK`；
- `price_inventory.xlsx` 只有表头和 `ACCEPTANCE-FAN/001` 一行；
- 只创建 `data/draft_saved/ACCEPTANCE-FAN001/`；
- 不创建 `automation/`；
- 不出现任何固定或历史业务型号。

随后在临时克隆的 Excel 填入测试价格/库存，直接放入一个非空 PDF 和四张非空测试图片，再次运行同一命令。Expected: `READY_TO_UPLOAD`。此验收不执行 1688 保存或发布。

- [ ] **Step 5: 从项目外的兼容智能体视角人工验收文档**

只给一个未读过项目规则的主智能体以下一句话：

```text
开始使用这个项目，我是电脑小白。
```

逐项确认：

1. 它先读 `START-HERE.md` 和 `AGENTS.md`；
2. 不让用户复制命令；
3. 不创建示例型号；
4. 一次只询问真实型号或一个缺失动作；
5. 获得型号后自动打开正确 Excel 和目录；
6. 不询问品牌、参数、SKU 或 JSON；
7. 资料齐全才进入原有高质量上传；
8. 最终停在保存草稿前；
9. 不删除、移动、改名或覆盖任何业务资料。

- [ ] **Step 6: 安全离开临时验收目录并报告路径**

先回到真实仓库：

```powershell
Set-Location "D:\Auto-Alibaba"
Write-Output $SmokeRoot
```

不要自动递归删除 `$SmokeRoot`。把临时验收目录路径报告给用户；只有用户明确允许删除该精确路径时，才在重新解析并确认它位于 `$env:TEMP` 下后删除。

- [ ] **Step 7: 检查提交序列和最终差异**

Run:

```powershell
git log --oneline -7
git status --short --branch
git diff origin/main...HEAD --stat
```

Expected: 设计提交后紧跟本计划的六个实施提交；无关的用户修改仍未被提交。若所有验收都通过，向用户报告新入口、测试结果、临时验收路径和仍保留的无关工作区修改。

## Task 8: 第一阶段稳定后再规划批量队列（本计划不实施）

**Files:**
- No changes in this phase

- [ ] **Step 1: 记录第二阶段的启动条件**

只有第一阶段经过真实单商品使用且用户确认稳定后，才单独启动批量设计。届时必须重新使用 brainstorming，重点确认：多个型号如何录入、目录批量创建、Excel 多行引导、每商品独立状态、浏览器串行队列、断电续跑和只复制不移动外部资料。

- [ ] **Step 2: 本阶段明确不实现批量行为**

本计划不得提前加入批量扫描、自动推断目录型号、并发上传、自动保存草稿或自动删除已完成资料。这样可保证本次变更只解决“小白如何安全上传一个新商品”，不降低现有详情、SKU 和证据质量。
