# Portable GitHub Distribution Design

## Goal

Publish Auto-Alibaba as a public GitHub repository that any Windows Codex user can clone, install, and run without depending on the original computer's username or `D:\Auto-Alibaba` path.

## Repository Layout

The existing Python application remains at the repository root. The Codex workflow becomes a repository plugin:

```text
Auto-Alibaba/
  app/
  tests/
  plugins/auto-alibaba/
    .codex-plugin/plugin.json
    skills/upload-1688-products/
      SKILL.md
      agents/openai.yaml
      scripts/
  .agents/plugins/marketplace.json
  AGENTS.md
  setup.ps1
  pyproject.toml
```

The plugin has no MCP server, connector, hook, or external service. Its only bundled component is the upload skill.

## Portable Path Rules

- The project root comes from the current repository/workspace, an explicit `--root`, or `AUTO_ALIBABA_ROOT`; no fixed drive or username is allowed.
- Skill commands invoke scripts relative to the installed skill directory, never through `C:\Users\<name>`.
- PowerShell and Python scripts continue to accept explicit root and CDP URL arguments.
- Repository tests load the repository copy of the skill. They do not require a preinstalled personal skill.

## Installation and Use

`setup.ps1` verifies Python 3.12+, creates `.venv`, installs `.[dev]`, and runs local checks. The repository marketplace exposes `auto-alibaba` for installation in Codex. After cloning and installing the plugin, the operator supplies local business data, starts the dedicated Chrome profile on port 9223, signs in to 1688, and runs the existing doctor/preflight workflow.

## Data and Security Boundary

Git tracks source code, tests, documentation, plugin files, marketplace metadata, and setup tooling. It must not track:

- `price_inventory.xlsx`
- product PDFs or photographs under `data/`
- generated `automation/` state and optimized images
- `.chrome-profile/`, cookies, credentials, `.env`, logs, caches, or temporary files

The GitHub repository is public, so every tracked file and every pushed commit is treated as permanently visible. Each receiving computer creates its own Chrome profile and logs in independently. No secret or business data is copied from the original machine. A staged-content secret and personal-path scan is mandatory before the first push.

## Publishing

Create `liucace/Auto-Alibaba` as a public GitHub repository, add it as `origin`, and push `main`. Existing unrelated untracked local files remain uncommitted. The repository README documents clone, setup, plugin installation, local data placement, login, doctor, and safe upload boundaries.

## Verification

- Plugin manifest and repository marketplace pass the official local validators.
- Contract tests fail if fixed personal paths return or if the skill cannot locate the project from a different root.
- `setup.ps1` receives a non-destructive validation mode used by tests.
- Full pytest, Ruff, mypy, Skill validation, secret/personal-path scans, and `git diff --check` pass before publishing.
- A post-push check verifies the remote is public and the expected commit is present.
