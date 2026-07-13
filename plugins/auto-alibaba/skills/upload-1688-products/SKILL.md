---
name: upload-1688-products
description: Use when uploading, fast-uploading, resuming, or checking prepared 1688 industrial-fan products from the local Auto-Alibab project, including requests containing a fan model number, 快速上传商品, 上传型号, 1688草稿, or 继续上传.
---

# 1688 商品快速上传

## Overview

调用当前 Auto-Alibab 工作区的持久化上传器，必要时先从当前型号 PDF、四张照片和库存表准备运行产物，再通过本机 Google Chrome CDP 9223 填写商品，并严格停在“保存草稿”前。

开始时解析两个路径：`<PROJECT_ROOT>` 优先使用用户明确给出的项目目录，其次使用 `AUTO_ALIBABA_ROOT`，最后使用当前包含 `pyproject.toml` 和 `app/` 的工作区；`<SKILL_DIR>` 是本 `SKILL.md` 所在目录。无法唯一解析时停止并询问，不猜测磁盘位置。

## Workflow

1. 从请求取得完整型号并规范化，不猜测相近型号。没有型号时先运行：

   ```powershell
   python "<SKILL_DIR>\scripts\inspect_session.py" --root "<PROJECT_ROOT>" --cdp-url "http://127.0.0.1:9223"
   ```

   仅当JSON返回唯一 `model` 时继续，否则询问用户。

2. 确保项目存在。在 `<PROJECT_ROOT>` 中运行 `python -m app.cli version`。仅当错误明确为缺少Python依赖时运行 `python -m pip install -e .`，其他错误直接报告。

3. 在任何 `doctor`、`prepare`、Chrome 会话检查或上传锁之前，运行资料初始化向导：

   ```powershell
   python -m app.cli init-product "<MODEL>" --root "<PROJECT_ROOT>"
   ```

   - `price_inventory.xlsx` 用于提供当前完整型号的1688价格和库存；型号保留 `/`，价格和库存留空时分别使用 `10000` 和 `50`。
   - `data/draft_saved/<FOLDER_KEY>/` 用于保存当前型号的原始资料；目录名去掉 `/`，其中需要至少一份包含完整型号的 PDF 规格书和至少四张真实产品照片。
   - 如果返回 `NEEDS_INPUT`，向使用者列出 `created`、逐项转述 `requirements` 的用途和操作，随后停止。不得在同一轮再次运行向导或进入浏览器；等待使用者补充并重新调用 Skill。
   - 如果返回 `BLOCKED`，准确报告 `message`，不要覆盖已有库存表或猜测资料。

4. 运行专用Chrome检查：

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File "<SKILL_DIR>\scripts\ensure_chrome.ps1" -Root "<PROJECT_ROOT>"
   ```

   失败时停止；不要终止端口占用者，不要改用内置浏览器或Playwright Chromium。

5. 在项目目录运行：

   ```powershell
   python -m app.cli doctor --root "<PROJECT_ROOT>"
   ```

   任一检查失败时停止。

6. 如果 `automation/<FOLDER_KEY>/` 缺少任一运行 JSON，先读取当前型号 PDF（文本与尺寸图页面）并逐张查看照片，创建 `preparation_evidence.json`。证据必须包含完整型号、PDF文件、标题、属性、规格、包装长宽高/重量、恰好四张当前型号照片及角色、尺寸图页码与裁剪范围。只写有明确 PDF/铭牌/照片证据的值；任何关键值不确定时停止，禁止猜测相近型号或参数。目录键通过项目 `model_folder_key()` 生成，业务型号始终保留原字符。

7. 正常上传只调用以下入口，不要绕过它直接运行项目CLI：

   ```powershell
   python "<SKILL_DIR>\scripts\run_upload.py" --root "<PROJECT_ROOT>" --model "<MODEL>" --cdp-url "http://127.0.0.1:9223"
   ```

   入口会在运行 JSON 缺失时自动调用 `python -m app.cli prepare`，以本地确定性方式生成1:1白边主图副本和三个运行 JSON；不覆盖原照片，不使用生成式图像编辑。

8. 只根据最终JSON和退出码判断结果：

   - `READY_TO_SAVE`：报告质量错误为0、详情图为5张，并说明已停在保存草稿前。
   - `NEEDS_LOGIN`：请用户在专用Chrome登录 `work.1688.com` 后再继续。
   - `BLOCKED`/`FAILED`：准确报告 `message` 和失败检查，不声称完成。

## Fixed Rules

- 型号行不存在即停止；价格/库存为空时使用 `10000`/`50`。
- 类目ID固定为 `1034320`/`2293`；48小时发货；运费模板为“运费”，绝不选“8元”。
- 四张待上传主图必须为1:1且分别小于 `5,000,000` 字节；非1:1源照片由 `prepare` 确定性等比缩放并补白边。
- 仅处理 PDF、四张照片及完整证据均已准备的型号；三个运行JSON可由 `prepare` 自动生成，但不要临时编造缺失参数。
- 本地主图内容变化时必须使旧页面媒体缓存失效，不得复用不匹配的托管图片。
- 子进程固定 `PYTHONUTF8=1` 和 `PYTHONIOENCODING=utf-8`，错误输出保留中文。
- 不并发运行，不临时重写替代检查脚本。脚本异常时修复同一Skill脚本。

## Safety Boundary

永远不要点击“保存草稿”、发布或等价按钮。不要复制Cookie、密码或账号凭据。页面结构、登录状态或素材证据不确定时立即停止。
