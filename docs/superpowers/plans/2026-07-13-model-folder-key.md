# Slash-Safe Model Folder Key Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve exact product model `W3G800-KS39-03/F01` through Windows-safe local directories named `W3G800-KS39-03F01` while preserving the slash in all business data and browser fields.

**Architecture:** Add one filesystem-only `model_folder_key()` helper beside existing model normalization. Use it at every product artifact/source path boundary in the project and upload skill, while retaining `normalize_model()` and `exact_model_match()` for inventory, JSON, state, and browser validation.

**Tech Stack:** Python 3.14, pathlib, pytest, Typer, the existing 1688 upload skill scripts.

---

## File Structure

- Modify `app/ingest/model_number.py`: define the single model-to-folder-key rule.
- Modify `app/products/loader.py`: use the folder key for source and artifact directories.
- Modify `tests/unit/ingest/test_model_number.py`: prove filesystem sanitization does not change business normalization.
- Modify `tests/unit/products/test_loader.py`: prove a slash-bearing model loads from the slash-free source and artifact directories.
- Modify `C:/Users/小城/.codex/skills/upload-1688-products/scripts/preflight.py`: resolve prepared artifacts through the project helper.
- Modify `C:/Users/小城/.codex/skills/upload-1688-products/scripts/run_upload.py`: fingerprint task state through the slash-free artifact directory.

### Task 1: Define the filesystem-only folder key

**Files:**
- Modify: `tests/unit/ingest/test_model_number.py`
- Modify: `app/ingest/model_number.py`

- [ ] **Step 1: Write the failing test**

Update the import and add this regression test:

```python
from app.ingest.model_number import exact_model_match, model_folder_key, normalize_model


def test_model_folder_key_removes_slash_without_changing_business_model() -> None:
    model = "W3G800-KS39-03/F01"

    assert normalize_model(model) == model
    assert model_folder_key(model) == "W3G800-KS39-03F01"
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
python -m pytest tests/unit/ingest/test_model_number.py::test_model_folder_key_removes_slash_without_changing_business_model -v
```

Expected: collection fails because `model_folder_key` is not defined.

- [ ] **Step 3: Add the minimal helper**

Append to `app/ingest/model_number.py`:

```python
def model_folder_key(raw: str) -> str:
    return normalize_model(raw).replace("/", "")
```

- [ ] **Step 4: Run the focused test and verify GREEN**

Run the Step 2 command. Expected: one test passes.

- [ ] **Step 5: Commit the helper and test**

```powershell
git add -- app/ingest/model_number.py tests/unit/ingest/test_model_number.py
git commit -m "fix: add slash-safe model folder keys"
```

### Task 2: Use the folder key for project source and artifact paths

**Files:**
- Modify: `tests/unit/products/test_loader.py`
- Modify: `app/products/loader.py`

- [ ] **Step 1: Write a failing end-to-end loader test**

Add this test to `tests/unit/products/test_loader.py`:

```python
def test_slash_model_loads_from_slash_free_folder_key(tmp_path: Path) -> None:
    model = "W3G800-KS39-03/F01"
    folder_key = "W3G800-KS39-03F01"
    artifacts = tmp_path / "automation" / folder_key
    source = tmp_path / "data" / "draft_saved" / folder_key
    artifacts.mkdir(parents=True)
    source.mkdir(parents=True)
    (source / "fan.pdf").write_bytes(b"pdf")
    drawing = source / "upload_optimized" / "detail-drawing.jpg"
    drawing.parent.mkdir()
    drawing.write_bytes(b"jpeg")
    for index in range(4):
        (source / f"photo-{index}.jpg").write_bytes(b"jpg")
    (artifacts / "1688_payload.json").write_text(
        json.dumps(
            {
                "model": model,
                "title": "title",
                "category_id": 1034320,
                "industry_category_id": 2293,
                "attributes": {"电压": "400"},
                "specification": {"规格型号": model},
                "price": 1,
                "stock": 1,
                "delivery_time": "48小时发货",
                "shipping_template": "运费",
                "package": {
                    "length_cm": 80.5,
                    "width_cm": 79.7,
                    "height_cm": 27,
                    "weight_g": 39300,
                },
            }
        ),
        encoding="utf-8",
    )
    (artifacts / "image_analysis.json").write_text(
        json.dumps(
            {
                "model": model,
                "images": [
                    {
                        "local_file": f"photo-{index}.jpg",
                        "role": f"role-{index}",
                        "hosted_url": None,
                    }
                    for index in range(4)
                ],
            }
        ),
        encoding="utf-8",
    )
    (artifacts / "detail_assets.json").write_text(
        json.dumps(
            {
                "model": model,
                "pdf_file": "fan.pdf",
                "page": 1,
                "crop": [0.05, 0.1, 0.95, 0.8],
                "local_file": "upload_optimized/detail-drawing.jpg",
                "hosted_url": None,
            }
        ),
        encoding="utf-8",
    )

    product = load_prepared_product(
        tmp_path,
        model,
        price=10000,
        stock=50,
    )

    assert product.payload.model == "W3G800-KS39-03/F01"
    assert product.source_directory.name == "W3G800-KS39-03F01"
    assert product.artifacts_directory.name == "W3G800-KS39-03F01"
```

- [ ] **Step 2: Run the loader test and verify RED**

Run:

```powershell
python -m pytest tests/unit/products/test_loader.py -v
```

Expected: the new test fails with `prepared artifacts missing` or `source directory does not exist` for the slash-bearing business model.

- [ ] **Step 3: Apply the folder key at both filesystem boundaries**

Update imports in `app/products/loader.py`:

```python
from app.ingest.model_number import exact_model_match, model_folder_key, normalize_model
```

Use the folder key without replacing the business model:

```python
def find_source_directory(root: Path, model: str) -> Path:
    normalized = normalize_model(model)
    folder_key = model_folder_key(normalized)
    for lifecycle in ("processing", "inbox", "draft_saved"):
        candidate = root / "data" / lifecycle / folder_key
        if candidate.is_dir():
            return candidate
    raise ManualReviewRequired(f"source directory does not exist for {normalized}")
```

In `load_prepared_product`, replace only the artifact path construction:

```python
normalized = normalize_model(model)
artifacts = root / "automation" / model_folder_key(normalized)
```

- [ ] **Step 4: Run loader and model-number tests**

```powershell
python -m pytest tests/unit/ingest/test_model_number.py tests/unit/products/test_loader.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit project path resolution**

```powershell
git add -- app/products/loader.py tests/unit/products/test_loader.py
git commit -m "fix: resolve product files with folder keys"
```

### Task 3: Keep the upload skill aligned with project path resolution

**Files:**
- Modify: `C:/Users/小城/.codex/skills/upload-1688-products/scripts/preflight.py`
- Modify: `C:/Users/小城/.codex/skills/upload-1688-products/scripts/run_upload.py`

- [ ] **Step 1: Demonstrate the existing preflight failure**

Run:

```powershell
python "C:\Users\小城\.codex\skills\upload-1688-products\scripts\preflight.py" --root "D:\Auto-Alibab" --model "W3G800-KS39-03/F01"
```

Expected before the skill-script change: the output reports missing prepared artifacts under a slash-derived artifact path, even though project source lookup now resolves the slash-free source directory.

- [ ] **Step 2: Import and expose the folder-key helper in preflight**

Replace `_load_project_api()` with:

```python
def _load_project_api(root: Path) -> dict[str, Any]:
    resolved = str(root.resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)
    from app.domain.models import DetailDrawingSpec, ProductImage, ProductPayload
    from app.ingest.inventory import load_inventory
    from app.ingest.model_number import exact_model_match, model_folder_key, normalize_model
    from app.products.loader import find_source_directory
    from app.publisher.form_plan import build_form_plan

    return {
        "DetailDrawingSpec": DetailDrawingSpec,
        "ProductImage": ProductImage,
        "ProductPayload": ProductPayload,
        "load_inventory": load_inventory,
        "exact_model_match": exact_model_match,
        "model_folder_key": model_folder_key,
        "normalize_model": normalize_model,
        "find_source_directory": find_source_directory,
        "build_form_plan": build_form_plan,
    }
```

Change artifact path construction in `_check_product()` to:

```python
artifacts = (root / "automation" / api["model_folder_key"](normalized)).resolve()
```

- [ ] **Step 3: Resolve task-state fingerprints with the folder key**

Change `_normalize_from_project()` in `run_upload.py` to return both business model and folder key:

```python
def _model_paths_from_project(root: Path, model: str) -> tuple[str, str]:
    resolved = str(root.resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)
    from app.ingest.model_number import model_folder_key, normalize_model

    normalized = normalize_model(model)
    return normalized, model_folder_key(normalized)
```

In `execute()`, unpack the pair and use `folder_key` only here:

```python
normalized, folder_key = _model_paths_from_project(root, model)
state_path = root / "automation" / folder_key / "task_state.json"
```

Keep locks, session inspection, CLI arguments, state model validation, and output model on `normalized`.

- [ ] **Step 4: Run syntax and read-only preflight verification**

```powershell
python -m py_compile "C:\Users\小城\.codex\skills\upload-1688-products\scripts\preflight.py" "C:\Users\小城\.codex\skills\upload-1688-products\scripts\run_upload.py"
python "C:\Users\小城\.codex\skills\upload-1688-products\scripts\preflight.py" --root "D:\Auto-Alibab" --model "W3G800-KS39-03/F01"
```

Expected: syntax succeeds. Preflight either returns `READY` using `automation/W3G800-KS39-03F01`, or reports the exact remaining missing prepared artifacts at that slash-free path. It must not report the source directory missing.

### Task 4: Regression verification and safe upload

**Files:**
- Verify: all project and skill files above

- [ ] **Step 1: Run the complete project quality suite**

```powershell
python -m pytest -q
python -m ruff check .
python -m mypy app
```

Expected: every command exits zero with no failures.

- [ ] **Step 2: Run the mandated environment checks sequentially**

```powershell
python -m app.cli version
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\小城\.codex\skills\upload-1688-products\scripts\ensure_chrome.ps1" -Root "D:\Auto-Alibab"
python -m app.cli doctor --root "D:\Auto-Alibab"
```

Expected: project version prints, dedicated Chrome reports `READY`, and every doctor check is `OK`.

- [ ] **Step 3: Execute only the approved uploader entry point**

```powershell
python "C:\Users\小城\.codex\skills\upload-1688-products\scripts\run_upload.py" --root "D:\Auto-Alibab" --model "W3G800-KS39-03/F01" --cdp-url "http://127.0.0.1:9223"
```

Expected success: final JSON has `status: READY_TO_SAVE`, `quality_errors: 0`, and task-state detail image count 5. The process stops before clicking “保存草稿”. If JSON is `BLOCKED`, `FAILED`, or `NEEDS_LOGIN`, stop and report its exact `message` and failed checks without claiming completion.
