# 1688 Upload Pipeline Hardening Design

## Goal

Turn a model-number upload request into a deterministic prepare-and-upload workflow that fails early with actionable diagnostics and never saves or publishes automatically.

## Scope

The approved change has two components.

1. Preparation: add a `prepare` command for ebm-papst fan source folders. The upload Skill visually verifies the current-model PDF and photographs and writes a typed `preparation_evidence.json`; the command validates that evidence, creates deterministic square JPEG copies with white padding, writes the three required runtime JSON artifacts, and renders the configured drawing crop. It must reject missing or ambiguous evidence instead of inventing values.
2. Upload hardening: fingerprint prepared main images so a changed image set cannot reuse stale hosted images, verify every critical field after blur, return structured quality-error details, and force UTF-8 in the skill subprocess.

## Architecture

- `app/products/preparer.py` owns typed evidence validation and artifact generation. It does not pretend that vector drawing dimensions are reliably extractable as PDF text.
- `app/products/main_images.py` owns deterministic square conversion and SHA-256 media fingerprints.
- `app.cli prepare <MODEL>` exposes preparation without opening Chrome.
- `Playwright1688Port` receives the expected media fingerprint. A tagged page is reusable only when its session-stored fingerprint matches; otherwise it is replaced with a fresh unsaved page.
- Critical inputs are filled through one read-back helper with one retry. Package values receive a final group verification before quality calculation.
- Quality parsing separates blocking error details from non-blocking advice and persists both in `task_state.json`.
- The installed `upload-1688-products` skill runs preparation before preflight and starts the child CLI with UTF-8 enabled.

## Evidence Rules

Preparation preserves the exact business model including `/`, while filesystem paths use `model_folder_key()`. Required evidence is: exact model, rated voltage and range, frequency, speed, power, current, maximum pressure, weight, size, protection class, insulation class, product drawing page, and at least one airflow table. The Skill derives these only after inspecting the PDF and photographs and records them in `preparation_evidence.json`; the program then confirms the exact model appears in the declared PDF, validates all paths, and requires exactly four source photographs. Package dimensions come from the visually verified drawing's outer square and axial depth; weight comes from the technical-data page. Any missing or conflicting field stops preparation.

Square copies use local Pillow operations only: proportional resize when an edge exceeds 2000 pixels, centered white padding, JPEG quality 90, and no generative editing. Original images are never overwritten.

## Safety and Recovery

Preparation may write only under `automation/<FOLDER_KEY>/` and `data/<lifecycle>/<FOLDER_KEY>/upload_optimized/`. Upload still cannot click save or publish. A changed media fingerprint causes a fresh unsaved page rather than deletion or mutation of an existing page's images. Browser and quality failures keep an actionable structured state for the next run.

## Verification

Tests cover typed evidence validation, exact PDF model matching, square-image dimensions and size, artifact generation, fingerprint changes, stale-page replacement, field read-back retry, quality error extraction, and UTF-8 subprocess environment. The full pytest, Ruff, and mypy suites must pass before using the real upload entry point.
