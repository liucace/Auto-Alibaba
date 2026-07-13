# Portable GitHub Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Auto-Alibaba cloneable and installable from the public `liucace/Auto-Alibaba` GitHub repository with its Codex upload workflow bundled as a repository plugin.

**Architecture:** Keep the Python application at the repository root and package the existing upload skill under `plugins/auto-alibaba/`. Resolve the project root from explicit input, environment, or workspace rather than personal paths. A repository marketplace exposes the plugin, while setup documentation and scripts configure Python locally without carrying business data or credentials.

**Tech Stack:** Python 3.12+, PowerShell, Codex plugins and skills, Git, GitHub CLI, pytest, Ruff, mypy.

---

### Task 1: Add portability contracts

**Files:**
- Modify: `tests/unit/test_upload_skill_contract.py`
- Create: `tests/unit/test_distribution_contract.py`

- [ ] Add tests that load the repository skill path, reject original-machine absolute paths in distributable files, verify the plugin manifest and marketplace paths, and assert ignored business-data patterns remain present.
- [ ] Run `python -m pytest tests/unit/test_upload_skill_contract.py tests/unit/test_distribution_contract.py -q` and confirm failure because the repository plugin does not exist yet.

### Task 2: Scaffold and populate the repository plugin

**Files:**
- Create: `plugins/auto-alibaba/.codex-plugin/plugin.json`
- Create: `plugins/auto-alibaba/skills/upload-1688-products/SKILL.md`
- Create: `plugins/auto-alibaba/skills/upload-1688-products/agents/openai.yaml`
- Create: `plugins/auto-alibaba/skills/upload-1688-products/scripts/ensure_chrome.ps1`
- Create: `plugins/auto-alibaba/skills/upload-1688-products/scripts/inspect_session.py`
- Create: `plugins/auto-alibaba/skills/upload-1688-products/scripts/preflight.py`
- Create: `plugins/auto-alibaba/skills/upload-1688-products/scripts/run_upload.py`
- Create: `.agents/plugins/marketplace.json`

- [ ] Run the plugin-creator scaffold for `auto-alibaba` with the repository marketplace path.
- [ ] Copy the verified personal upload skill into the scaffold while excluding `__pycache__` and bytecode.
- [ ] Replace fixed script invocations with skill-relative paths and define project-root resolution as explicit `--root`, `AUTO_ALIBABA_ROOT`, or current workspace.
- [ ] Run the focused contract tests and confirm they pass.
- [ ] Run plugin and skill validators against the repository copies.

### Task 3: Add clone-time setup and repository guidance

**Files:**
- Create: `setup.ps1`
- Create: `AGENTS.md`
- Modify: `README.md`
- Modify: `.gitignore`

- [ ] Implement `setup.ps1` with a `-CheckOnly` mode. It validates Python 3.12+, Chrome, repository files, and ignored-data boundaries; normal mode creates `.venv` and installs `.[dev]`.
- [ ] Add compact `AGENTS.md` instructions for tests, safety boundaries, model-folder rules, and never saving or publishing automatically.
- [ ] Document clone, setup, plugin installation, local `price_inventory.xlsx` and `data/draft_saved/` placement, Chrome login, doctor, and upload usage.
- [ ] Extend `.gitignore` for credentials and common local archives without allowing business data.
- [ ] Run setup contract tests and `powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1 -CheckOnly`.

### Task 4: Verify the public payload

**Files:**
- Verify all tracked and staged files.

- [ ] Run `python -m pytest -q`, `python -m ruff check .`, and `python -m mypy app`.
- [ ] Run plugin validation, Skill validation, `python -m py_compile` on bundled Python scripts, and `git diff --check`.
- [ ] Scan tracked/staged content for personal absolute paths, the disclosed password, GitHub tokens, cookies, `.env` values, business spreadsheets, PDFs, photographs, Chrome profiles, generated state, and logs. Stop if any match is part of the public payload.
- [ ] Commit only the portability implementation; preserve unrelated untracked local files.

### Task 5: Create and verify the public GitHub repository

**Files:**
- No source-file changes.

- [ ] Confirm `gh auth status` reports active account `liucace` with `repo` scope.
- [ ] Create and push with `gh repo create liucace/Auto-Alibaba --public --source . --remote origin --push`.
- [ ] Verify `gh repo view liucace/Auto-Alibaba --json nameWithOwner,visibility,url,defaultBranchRef` reports `PUBLIC`, `liucace/Auto-Alibaba`, and `main` at the pushed commit.
