# Auto-Alibaba Repository Guidance

- When the user says “开始使用”, is new to the project, or asks where files go, read `START-HERE.md` first and run `agent-onboard.ps1` without a model.
- Treat Codex, WorkBuddy, or another command-capable external agent as required; the repository does not contain an AI model.
- Before the user provides a real complete model, do not run `init-product`, pass `--model`, create workbook rows, or create product directories.
- 一次只要求用户完成一个可操作事项。Translate structured states into short Chinese and do not make a beginner read JSON or copy commands.
- After receiving the exact model, run `agent-onboard.ps1 -Model "<完整型号>" -Open`. Re-run the same command after the user says the requested input is ready.
- Ask the user only for the exact model, one matching PDF, at least four real photos, price, and stock. Derive brand and supported listing content from current evidence only.
- The bundled Codex Plugin is optional. The repository entry and upload scripts remain the source of truth for every compatible agent.
- Use Python 3.12+ and run `python -m pytest -q`, `python -m ruff check .`, and `python -m mypy app` after code changes.
- Preserve the exact business model, including `/`; use `model_folder_key()` only for filesystem directories.
- Treat `price_inventory.xlsx`, `data/`, `automation/`, `.chrome-profile/`, logs, cookies, credentials, and `.env` as local-only data.
- 未经用户明确授权具体路径，never delete, move, rename, overwrite, clean, reset, or replace protected business data, including during Git/worktree cleanup.
- Reuse existing model folders and exact Excel rows. Never clear a folder or rewrite an existing price or stock value during onboarding.
- Never invent a sample/default product model, brand, technical value, SKU value, package value, price, or stock.
- Use the bundled `upload-1688-products` Skill for uploads. Do not bypass its preparation, lock, preflight, or UTF-8 wrapper.
- Only use the dedicated local Google Chrome CDP endpoint `http://127.0.0.1:9223` and the operator's own 1688 login.
- Never click “保存草稿”, publish, or an equivalent final action. Stop at `READY_TO_SAVE`.
- Do not invent model evidence, technical parameters, image identity, or package values.
