# Upload 1688 Products Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install a deterministic personal Codex Skill that safely orchestrates the existing `D:\Auto-Alibab` uploader from new conversations and always stops before saving.

**Architecture:** Keep the uploader as the only owner of form-filling logic. Add four Skill scripts: a PowerShell Chrome guard, a read-only CDP inspector, a local artifact preflight, and a locked subprocess wrapper that validates fresh task state. `SKILL.md` exposes one normal execution path through the wrapper.

**Tech Stack:** Codex Agent Skills, Python 3.12, Playwright CDP, PowerShell, Pydantic, pytest, Typer CLI.

---

## File map

- Create `<SKILL_DIR>\SKILL.md`: trigger and orchestration instructions.
- Create `<SKILL_DIR>\agents\openai.yaml`: Codex UI metadata.
- Create `<SKILL_DIR>\scripts\ensure_chrome.ps1`: verify or start the dedicated local Chrome CDP instance.
- Create `<SKILL_DIR>\scripts\inspect_session.py`: read-only session and page inspection.
- Create `<SKILL_DIR>\scripts\preflight.py`: local artifact and fixed-rule validation.
- Create `<SKILL_DIR>\scripts\run_upload.py`: lock, invoke the project CLI, and validate fresh state.
- Create then remove `<CODEX_HOME>\tmp\upload-1688-products-tests\`: temporary RED/GREEN test harness.

### Task 1: Establish RED baseline and initialize the Skill

- [ ] **Step 1: Write a failing discovery test**

Create a temporary pytest that asserts `SKILL.md` and all four scripts exist and that `preflight.py` imports successfully.

```python
from pathlib import Path

SKILL = Path.home() / ".codex" / "skills" / "upload-1688-products"

def test_skill_runtime_files_exist():
    required = [
        "SKILL.md",
        "scripts/ensure_chrome.ps1",
        "scripts/inspect_session.py",
        "scripts/preflight.py",
        "scripts/run_upload.py",
    ]
    assert all((SKILL / name).is_file() for name in required)
```

- [ ] **Step 2: Run the baseline and verify RED**

Run: `python -m pytest -q <CODEX_HOME>\tmp\upload-1688-products-tests`

Expected: FAIL because the Skill directory does not exist.

- [ ] **Step 3: Initialize the Skill**

Run `init_skill.py upload-1688-products --path <CODEX_HOME>\skills --resources scripts` with interface values for display name, short description, and default prompt.

- [ ] **Step 4: Verify the scaffold exists**

Expected: `SKILL.md`, `agents/openai.yaml`, and `scripts/` exist; the runtime-files test still fails because the four scripts are missing.

### Task 2: Implement the dedicated Chrome guard

- [ ] **Step 1: Add RED checks for the active 9223 instance**

Test that the script exits `0`, emits exactly one JSON object, reports `status=READY`, and confirms the listener process is `chrome.exe` with both required command-line arguments.

- [ ] **Step 2: Implement `ensure_chrome.ps1`**

Use `Get-NetTCPConnection` and `Get-CimInstance Win32_Process` to verify an existing listener. If absent, locate Chrome in Program Files or LocalAppData and call `Start-Process` with an argument list. Poll `/json/version` for at most 20 seconds. Never terminate an occupant. Emit JSON with `ok`, `status`, `model=$null`, `checks`, and `message`.

- [ ] **Step 3: Run the Chrome test and verify GREEN**

Expected: one JSON object with `ok=true`, `status=READY`, and `dedicated_profile=true` against the current live Chrome.

### Task 3: Implement read-only session inspection

- [ ] **Step 1: Add RED unit tests**

Test pure functions for exact session-tag parsing, current-state schema filtering, page/model matching, and login tri-state. Verify legacy `READY_TO_SAVE_DRAFT` and incomplete `READY_TO_SAVE` states are rejected.

```python
def test_current_ready_state_requires_detail_schema():
    assert is_current_state({"model": "X", "status": "READY_TO_SAVE"}) is False
```

- [ ] **Step 2: Implement `inspect_session.py`**

Provide `normalize_model`, `is_current_state`, `read_state_candidates`, `inspect_pages`, and `main`. Connect with `async_playwright().chromium.connect_over_cdp`, inspect only HTTP(S) pages, evaluate `window.name`, read the current SKU/model field and normalized hosted main-image URLs, and stop only the Playwright runtime. Support optional `--model` and required `--root`/`--cdp-url`.

- [ ] **Step 3: Run unit and live read-only tests**

Expected: unit tests pass; live invocation returns JSON without changing the number or URLs of Chrome pages.

### Task 4: Implement local product preflight

- [ ] **Step 1: Add RED unit tests**

Build temporary project fixtures and test default price/stock, source priority, exact fixed payload fields, positive package values, model agreement, contained paths, four local images, strict `<5_000_000` bytes, and the validated four-hosted-image bypass.

```python
def test_five_million_bytes_is_rejected(product_fixture):
    product_fixture.main_image.write_bytes(b"x" * 5_000_000)
    result = check_product(product_fixture.root, product_fixture.model, reuse_main_images=False)
    assert result["ok"] is False
```

- [ ] **Step 2: Implement `preflight.py`**

Insert the resolved project root into `sys.path`, then import `load_inventory`, `normalize_model`, `exact_model_match`, and `find_source_directory`. Parse JSON with Pydantic project models without calling `prepare_detail_drawing`. Require fixed IDs/rules, positive package dimensions/weight, contained relative paths, required PDF/files, and conditional image-size checks. Return structured data without writes.

- [ ] **Step 3: Run preflight tests and real prepared-model diagnostics**

Expected: fixture tests pass. `W3G710-NU31-03` passes. Any older incompatible artifact reports a structured nonzero result rather than a traceback.

### Task 5: Implement the locked upload wrapper

- [ ] **Step 1: Add RED unit tests**

Test atomic lock acquisition/release, active/stale locks, state fingerprints, fresh-state detection, strict READY/BLOCKED/FAILED validation, subprocess argument lists using `sys.executable`, timeout handling, and retry allowlisting.

```python
def test_ready_requires_fresh_reference_detail_state(tmp_path):
    before = fingerprint(tmp_path / "task_state.json")
    write_ready_state(tmp_path, template_version="old")
    assert validate_run_state(tmp_path / "task_state.json", before, "MODEL")["ok"] is False
```

- [ ] **Step 2: Implement `run_upload.py`**

Import the sibling inspector and preflight modules. Acquire `.uploader.lock` with exclusive creation. Re-run session inspection and preflight inside the lock. Snapshot task state, invoke `[sys.executable, "-m", "app.cli", "run", model, "--root", root, "--cdp-url", cdp_url]` with `shell=False` and a 900-second timeout, validate the new state, allow at most one exact allowlisted retry, and always release the lock.

- [ ] **Step 3: Run wrapper tests**

Expected: all wrapper tests pass without contacting or mutating1688; subprocess behavior is mocked at the boundary.

### Task 6: Write and validate the Skill instructions

- [ ] **Step 1: Replace scaffold `SKILL.md`**

Use frontmatter:

```yaml
---
name: upload-1688-products
description: Use when uploading, fast-uploading, resuming, or checking prepared 1688 industrial-fan products from the local Auto-Alibab project, including requests containing a fan model number or references to 1688 drafts.
---
```

Keep the body under 500 words. Require `ensure_chrome.ps1`, `doctor`, and `run_upload.py`; allow standalone `inspect_session.py` only to resolve a missing model. State the fixed rules and never-save boundary.

- [ ] **Step 2: Generate `agents/openai.yaml`**

Use `generate_openai_yaml.py` with:

- `display_name=1688 商品快速上传`
- `short_description=用本机 Chrome 9223 安全上传已准备好的1688风机商品`
- `default_prompt=使用 $upload-1688-products 快速上传指定型号，并停在保存草稿前。`

- [ ] **Step 3: Validate the Skill package**

Run: `python <CODEX_HOME>\skills\.system\skill-creator\scripts\quick_validate.py <SKILL_DIR>`

Expected: validation passes.

### Task 7: Final verification and cleanup

- [ ] **Step 1: Run all temporary Skill tests**

Expected: all pass.

- [ ] **Step 2: Run project regression tests and static checks**

Run `python -m pytest -q`, `python -m ruff check .`, `python -m ruff format --check .`, and `python -m mypy app` from `D:\Auto-Alibab`.

Expected: all pass.

- [ ] **Step 3: Run live read-only diagnostics**

Run Chrome guard, `doctor`, session inspection, and preflight for `W3G710-NU31-03`. Do not call the real upload wrapper without a new upload request.

- [ ] **Step 4: Remove temporary tests**

Delete only `<CODEX_HOME>\tmp\upload-1688-products-tests` after all results are recorded. Preserve unrelated untracked project files.

- [ ] **Step 5: Report installation**

Tell the user that new Codex conversations can invoke `$upload-1688-products`, and that existing conversations may need to be reopened before discovery metadata refreshes.
