---
name: upload-1688-products
description: Use when uploading, fast-uploading, resuming, or checking prepared 1688 industrial-fan products from the local Auto-Alibaba project, including requests containing a fan model number, 快速上传商品, 上传型号, 1688草稿, or 继续上传.
---

# 1688 商品快速上传

## Overview

调用当前 Auto-Alibaba 工作区的持久化上传器，从操作者提供的当前型号 PDF、真实照片和 Excel 价格/库存中生成全部商品数据，再通过本机 Google Chrome CDP 9223 填写商品，并严格停在“保存草稿”前。

开始时解析两个路径：`<PROJECT_ROOT>` 优先使用用户明确给出的项目目录，其次使用 `AUTO_ALIBABA_ROOT`，最后使用当前包含 `pyproject.toml` 和 `app/` 的工作区；`<SKILL_DIR>` 是本 `SKILL.md` 所在目录。无法唯一解析时停止并询问，不猜测磁盘位置。

## Workflow

1. 解析 `<PROJECT_ROOT>`，并把仓库根目录入口作为所有智能体的共同事实来源。Codex Plugin 不是必需条件；只要当前智能体能运行 PowerShell 和 Python，就可以使用本流程。

2. 没有用户明确提供的真实完整型号时，先运行：

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File "<PROJECT_ROOT>\agent-onboard.ps1"
   ```

   只能转述 `NEEDS_SETUP` 或 `NEEDS_MODEL` 的 `next_action`，随后等待用户。不得创建示例型号，也不得从目录名、历史商品或相近型号猜测。

3. 获得用户的真实完整型号后，在任何 doctor、prepare、Chrome、上传锁或浏览器动作之前运行：

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File "<PROJECT_ROOT>\agent-onboard.ps1" -Model "<MODEL>" -Open
   ```

   - `NEEDS_SETUP`：只处理 `next_action` 指出的当前环境问题，随后重新运行同一步。
   - `NEEDS_PRICE_STOCK`：请用户在已打开 Excel 的当前精确型号行填写真实价格和库存；价格和库存不能为空。随后停止并等待用户说“已填好”。
   - `NEEDS_SOURCE_FILES`：只转述当前唯一 `next_action`，随后停止并等待用户。PDF 和照片直接放在已打开的型号目录，不需要子目录或固定文件名。
   - `READY_TO_UPLOAD`：才允许继续现有 Chrome、doctor、证据准备和上传流程。
   - `BLOCKED`：准确报告 `message`，不得覆盖或替换已有文件。
   - 每个状态只要求用户完成一个动作。不得在同一轮假定用户已经完成并继续检查或上传。
   - `price_inventory.xlsx` 用于提供当前完整型号的1688价格和库存；业务型号保留 `/`，目录键使用项目 `model_folder_key()`。
   - `data/draft_saved/<FOLDER_KEY>/` 保存当前型号原始资料，其中需要至少一份包含完整型号的 PDF 规格书和至少四张真实产品照片。
   - 操作者的外部输入仅限当前型号 PDF、至少四张真实产品照片，以及 Excel 中的价格和库存。品牌、标题、属性、规格、包装值、图片角色、尺寸图裁剪和全部运行 JSON 均由本 Skill 从这些资料中生成；不得要求操作者手工填写 JSON、品牌或技术参数。

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

6. 如果 `automation/<FOLDER_KEY>/` 缺少证据/运行 JSON，或运行 JSON 早于 `preparation_evidence.json`，先读取当前型号 PDF（文本与尺寸图页面）并逐张查看照片，由本 Skill 创建或刷新内部证据。证据必须包含从规格书制造商标识或清晰铭牌/产品标识确认的品牌，以及完整型号、PDF文件、标题、属性、规格、包装长宽高/重量、恰好四张当前型号照片及角色、尺寸图页码与裁剪范围。普通技术字段没有证据时直接省略；关键必填值没有证据时停止。禁止使用目录名、历史商品、默认品牌或相近型号猜测。

   - 标题由证据生成，标题不超过 60 个字符（1688 加权计数：ASCII 字符计 1、中文字符计 2），并且包含品牌、完整型号和产品名称；禁止添加无证据营销词。平台计数超限时先删除冗余品牌别名或低价值修饰语，不得让页面截断完整型号或产品名称。
   - 规格书中的 50/60Hz 斜杠参数按前值50Hz、后值60Hz写入商品规格；它们属于同一个完整型号，不得拆成多个 SKU，也不得写进 SKU 名称或商家编码。
   - 销售规格只建立一个 SKU：规格型号和商家编码均为完整型号，库存来自 Excel。
   - 详情按证据自适应生成：有值才显示；当前型号四张实物图和一张尺寸图之后，固定六张公司介绍图片必须放在详情最末公司区，并用于每个品牌的商品。
   - 目录键通过项目 `model_folder_key()` 生成；业务型号始终保留原字符，包括 `/`。

7. 正常上传只调用以下入口，不要绕过它直接运行项目CLI：

   ```powershell
   python "<SKILL_DIR>\scripts\run_upload.py" --root "<PROJECT_ROOT>" --model "<MODEL>" --cdp-url "http://127.0.0.1:9223"
   ```

   入口会在运行 JSON 缺失时自动调用 `python -m app.cli prepare`，以本地确定性方式生成1:1白边主图副本和三个运行 JSON；不覆盖原照片，不使用生成式图像编辑。

8. 只根据最终JSON和退出码判断结果：

   - `READY_TO_SAVE`：报告质量错误为0、任务状态记录的动态图片数量，并说明已停在保存草稿前。图片数量与有序 `image_sources` 必须一致且无重复。
   - `NEEDS_LOGIN`：请用户在专用Chrome登录 `work.1688.com` 后再继续。
   - `BLOCKED`/`FAILED`：准确报告 `message` 和失败检查，不声称完成。

## Fixed Rules

- 型号行不存在即停止；价格和库存不能为空，也不得使用默认值代替用户输入。
- 类目ID固定为 `1034320`/`2293`；48小时发货；运费模板为“运费”，绝不选“8元”。
- 四张待上传主图必须为1:1且分别小于 `5,000,000` 字节；非1:1源照片由 `prepare` 确定性等比缩放并补白边。
- 仅处理 PDF、四张照片及完整证据均已准备的型号；三个运行JSON可由 `prepare` 自动生成，但不要临时编造缺失参数。
- 标题和规格必须来自当前型号证据；规格书没有的普通值不填写。单个 50/60Hz 型号始终保持一个 SKU。
- GEO 详情按现有证据自适应省略空模块；固定六张公司介绍图片只出现在最末公司区，对 SUNON、Delta、Sanyo、Multifan、ebm-papst 等每个品牌均保持相同顺序。
- 本地主图内容变化时必须使旧页面媒体缓存失效，不得复用不匹配的托管图片。
- `preparation_evidence.json` 晚于任一运行 JSON 时必须重新执行 `prepare`，不得上传陈旧产物。
- 图片相册按精确品牌名使用 `品牌(NN)` 连续编号。优先选择当前品牌编号最大的相册；不存在时创建 `(01)`；上传明确返回容量不足时只允许创建下一编号并重试当前批次一次。禁止使用其他品牌或近似名称相册。
- 子进程固定 `PYTHONUTF8=1` 和 `PYTHONIOENCODING=utf-8`，错误输出保留中文。
- 不并发运行，不临时重写替代检查脚本。脚本异常时修复同一Skill脚本。

## Safety Boundary

永远不要点击“保存草稿”、发布或等价按钮。不要复制Cookie、密码或账号凭据。页面结构、登录状态或素材证据不确定时立即停止。

`price_inventory.xlsx`、`data/`、`automation/`、PDF、照片和浏览器资料均为用户业务数据；未经用户针对具体路径明确授权，不得删除、移动、改名、清空或覆盖，也不得在 Git/worktree 清理时处理这些路径。
