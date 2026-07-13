# Auto-Alibaba Repository Guidance

- Use Python 3.12+ and run `python -m pytest -q`, `python -m ruff check .`, and `python -m mypy app` after code changes.
- Preserve the exact business model, including `/`; use `model_folder_key()` only for filesystem directories.
- Treat `price_inventory.xlsx`, `data/`, `automation/`, `.chrome-profile/`, logs, cookies, credentials, and `.env` as local-only data.
- Use the bundled `upload-1688-products` Skill for uploads. Do not bypass its preparation, lock, preflight, or UTF-8 wrapper.
- Only use the dedicated local Google Chrome CDP endpoint `http://127.0.0.1:9223` and the operator's own 1688 login.
- Never click “保存草稿”, publish, or an equivalent final action. Stop at `READY_TO_SAVE`.
- Do not invent model evidence, technical parameters, image identity, or package values.
