# 1688 Upload Pipeline Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic product preparation and make resumed 1688 uploads reject stale media, verify critical fields, and report exact blocking errors.

**Architecture:** New preparation and media modules remain browser-independent. The Skill performs the visual evidence step and writes typed `preparation_evidence.json`; the preparation command validates it and creates deterministic artifacts. The browser port receives a content fingerprint, uses it to decide whether a tagged unsaved page is reusable, and centralizes critical-field verification. The installed upload skill calls preparation and preserves structured UTF-8 results.

**Tech Stack:** Python 3.14, PyMuPDF, Pillow, Pydantic, Playwright, Typer, pytest.

---

### Task 1: Deterministic square media and fingerprints

**Files:**
- Create: `app/products/main_images.py`
- Create: `tests/unit/products/test_main_images.py`
- Modify: `pyproject.toml`

- [ ] Write tests that create a 1200x800 image, call `prepare_square_image(source, output)`, and assert a square RGB JPEG no larger than 2000x2000 and below 5,000,000 bytes; also assert `media_fingerprint(paths)` changes when file bytes change.
- [ ] Run `python -m pytest tests/unit/products/test_main_images.py -v`; expect import failure.
- [ ] Implement `prepare_square_image()` with Pillow proportional thumbnailing, centered white padding, quality 90, atomic replacement, and source preservation. Implement `media_fingerprint()` as SHA-256 over each file name, size, and content digest in order.
- [ ] Add `pillow>=10` to project dependencies and run the focused test; expect PASS.

### Task 2: Evidence-backed prepare command

**Files:**
- Create: `app/products/preparer.py`
- Create: `tests/unit/products/test_preparer.py`
- Modify: `app/cli.py`

- [x] Define and test a typed evidence file containing the visually verified PDF fields, four photographs, package values, and drawing crop. The application validates that the declared PDF contains the exact requested model instead of attempting unreliable OCR of vector dimension outlines.
- [ ] Write an integration test with a synthetic six-page PDF, four photographs, and an inventory workbook; call `prepare_product()` and assert all three JSON files plus four square copies and a drawing JPEG exist under the slash-free folder key.
- [ ] Run `python -m pytest tests/unit/products/test_preparer.py -v`; expect import failure.
- [x] Implement `prepare_product(root, model)`. Reject missing/mismatched evidence and path escapes, require exactly four declared source photos below the source directory, create square copies, write validated JSON atomically, and render the drawing through existing `prepare_detail_drawing()`.
- [ ] Add Typer command `prepare MODEL --root PATH` that prints a compact JSON result and exits nonzero on `AutomationError`.
- [ ] Run focused prepare tests; expect PASS.

### Task 3: Fingerprint-aware page reuse

**Files:**
- Modify: `app/publisher/playwright_port.py`
- Modify: `app/cli.py`
- Modify: `tests/unit/publisher/test_idempotence.py`
- Modify: `tests/unit/test_cli_run.py`

- [ ] Add tests proving a matching `sessionStorage['1688-uploader:media-fingerprint']` reuses a tagged page and a mismatch closes that unsaved page and creates a fresh tagged page.
- [ ] Run the focused tests; expect failures because `media_fingerprint` is not passed to `connect()`.
- [ ] Compute the fingerprint from `product.local_images` in `run_product()` and pass it to `Playwright1688Port.connect()`.
- [ ] Extend `connect()` with `media_fingerprint`. Reuse only on a match; on mismatch close only the exact tagged publish page, create a fresh page, and set the expected fingerprint in session storage after four hosted image URLs are confirmed.
- [ ] Run focused tests; expect PASS.

### Task 4: Critical field read-back

**Files:**
- Modify: `app/publisher/playwright_port.py`
- Create: `tests/unit/publisher/test_field_verification.py`

- [ ] Add fake-field tests for `_fill_and_verify()`: first fill persists, first fill clears then retry persists, and two mismatches raise `ManualReviewRequired` with the field label.
- [ ] Run the focused test; expect import failure.
- [ ] Implement `_fill_and_verify(field, value, label, retries=1)` and replace price, stock, SKU, package, and freight write paths with fill/select followed by normalized read-back. Verify all four package inputs again after the group is filled.
- [ ] Run focused and publisher tests; expect PASS.

### Task 5: Structured blocking quality details

**Files:**
- Modify: `app/publisher/quality.py`
- Modify: `app/publisher/orchestrator.py`
- Modify: `app/cli.py`
- Modify: `tests/unit/publisher/test_quality.py`
- Modify: `tests/unit/publisher/test_orchestrator.py`
- Modify: `tests/unit/test_cli.py`

- [ ] Add a parser test using UI text containing `物流信息`, `1个报错`, `件重尺`, and `重量均不能为空`; expect `error_details=[{'section':'物流信息','item':'件重尺','message':'重量均不能为空'}]` while advice stays separate.
- [ ] Run focused tests; expect failure because the result lacks `error_details`.
- [ ] Extend quality result, `UploadResult`, and task state with immutable structured error details. Preserve zero-error behavior and do not treat advice as blocking.
- [ ] Run focused tests; expect PASS.

### Task 6: Upload skill prepare integration and UTF-8

**Files:**
- Modify: `<SKILL_DIR>/scripts/run_upload.py`
- Modify: `<SKILL_DIR>/scripts/preflight.py`
- Modify: `<SKILL_DIR>/SKILL.md`

- [ ] Add a `run_prepare()` subprocess helper that calls `python -m app.cli prepare MODEL --root ROOT`, sets `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8`, and returns structured stdout/stderr.
- [ ] Call preparation only when the three artifacts are absent; never overwrite a complete prepared set during a resume.
- [ ] Add square-dimension checks to preflight in addition to byte-size checks and include SHA-256 fingerprints in `checks`.
- [ ] Update Skill workflow and fixed rules to state that preparation is automatic, deterministic, evidence-backed, and non-generative.
- [ ] Run `py_compile`, a missing-artifact diagnostic in a temporary root, and the real prepared-model preflight; expect success with UTF-8 output.

### Task 7: Full verification

**Files:**
- Verify all files above.

- [ ] Run `python -m pytest -q`; expect zero failures.
- [ ] Run `python -m ruff check .`; expect no issues.
- [ ] Run `python -m mypy app`; expect no issues.
- [ ] Run `python -m app.cli prepare W3G800-KS39-03/F01 --root D:\Auto-Alibaba`; expect validated artifacts without changing the exact business model.
- [ ] Run upload-skill preflight for the model; expect `READY`, four square images, and contained paths.
