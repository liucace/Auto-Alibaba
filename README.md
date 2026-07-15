# Auto-Alibaba：智能体引导的 1688 商品上传器

Auto-Alibaba 配合 Codex、WorkBuddy 或其他能够运行 PowerShell 和 Python 的外部智能体使用。智能体从当前型号的规格书和真实照片理解商品，项目负责确定性校验、图片处理、1688 页面填写、质量检查和状态保存。项目本身不内置 AI。

如果你是电脑小白，请先看 [START-HERE.md](START-HERE.md)。你也可以把下面这句话直接发给智能体：

> 开始使用这个项目。我是电脑小白。请先读取 START-HERE.md 和 AGENTS.md，再一步一步带我操作；一次只告诉我一个动作。

## 克隆与首次安装

~~~powershell
git clone https://github.com/liucace/Auto-Alibaba.git
Set-Location Auto-Alibaba
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
~~~

也可以先执行无写入检查：

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1 -CheckOnly
~~~

在 Codex、WorkBuddy 或其他智能体中打开克隆后的项目即可。Codex 用户可以选择安装仓库内的 auto-alibaba Plugin；Plugin 只提供工作流增强，不包含商品资料、账号或登录状态，也不是运行项目的必需条件。

## 智能体通用入口

所有兼容智能体都应优先使用根目录入口：

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\agent-onboard.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\agent-onboard.ps1 -Model "<完整型号>" -Open
~~~

无型号调用只检查环境并返回 `NEEDS_SETUP` 或 `NEEDS_MODEL`，不会创建价格表、型号目录或示例商品。只有显式传入用户的真实完整型号后，才会创建或复用：

- `price_inventory.xlsx`：保存完整型号、1688价格和库存；价格和库存都必须由用户填写真实值，不能留空。
- `data/draft_saved/<FOLDER_KEY>/`：直接放入至少一份包含完整型号的 PDF规格书，以及至少四张当前型号真实产品照片；不需要子目录，也不限制原文件名。

品牌、标题、属性、SKU、包装值、图片角色、详情页和运行 JSON 均由智能体与项目从当前资料中处理。规格书和照片没有的普通值不填写；关键值无法确认时停止。

结构化状态如下：

- NEEDS_SETUP：当前环境缺少一个必要条件；
- NEEDS_MODEL：等待用户提供真实完整型号；
- NEEDS_PRICE_STOCK：等待填写价格或库存；
- NEEDS_SOURCE_FILES：等待 PDF规格书或真实照片；
- READY_TO_UPLOAD：资料齐全，可以进入证据准备和上传；
- NEEDS_LOGIN：等待用户在专用 Chrome 登录 1688；
- READY_TO_SAVE：页面和质量检查完成，已停在“保存草稿”前。

## 资料目录

~~~text
price_inventory.xlsx
data/draft_saved/<FOLDER_KEY>/
  <PDF规格书>
  <产品照片>
  upload_optimized/
    <程序生成的1:1主图>
    detail-drawing.jpg
automation/<FOLDER_KEY>/
  preparation_evidence.json
  1688_payload.json
  image_analysis.json
  detail_assets.json
  detail.html
  task_state.json
~~~

业务型号始终保留 `/` 等原字符；`<FOLDER_KEY>` 只用于本地目录，由统一的 `model_folder_key()` 生成。用户只维护原始 PDF、照片以及 Excel 中的价格和库存；`automation/` 和 `upload_optimized/` 由程序生成。

preparation_evidence.json 是原始资料与运行 JSON 之间的证据层。当前型号 PDF、照片、标题、属性、规格、包装值、图片角色和尺寸图来源都必须可追溯；不得根据目录名、历史商品、默认品牌或相近型号猜测。

## 专用 Chrome

上传前，Google Chrome 必须使用项目专用用户目录和远程调试端口 9223 启动，并由用户登录自己的 work.1688.com 账号：

~~~powershell
$ProjectRoot = (Get-Location).Path
$ChromeProfile = Join-Path $ProjectRoot ".chrome-profile"
& "$env:ProgramFiles\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9223 --user-data-dir="$ChromeProfile"
~~~

只读环境检查：

~~~powershell
python -m app.cli doctor --root .
~~~

## 高级命令

正常新手流程应由智能体调用根目录入口。熟悉项目后，可以使用以下无固定型号命令：

~~~powershell
python -m app.cli onboard --root .
python -m app.cli onboard --root . --model "<完整型号>" --open
python -m app.cli prepare "<完整型号>" --root .
python -m app.cli run "<完整型号>" --root .
~~~

init-product 仅为旧调用保留兼容性；新的智能体流程统一使用 onboard。

## 上传质量规则

- 类目：机械及行业设备 > 风机、排风设备 > 工业风扇 > 其他工业风扇；
- 发货时效：48 小时；
- 运费模板：运费；
- 四张当前型号主图，确定性等比缩放并补白边为 1:1，不覆盖原照片；
- 标题包含有证据的品牌、完整型号和产品名称，并遵守 1688 加权长度；
- 一个完整型号只建立一个精确 SKU；50/60Hz 数据属于同一型号时不拆 SKU；
- GEO 详情按当前证据自适应生成，包含当前型号实物图、尺寸图、参数、选型说明、FAQ 和固定放在末尾的六张公司介绍图；
- 图片相册按精确品牌名和连续编号管理；容量满时只创建下一编号并重试当前批次一次；
- 本地主图内容变化时使旧媒体缓存失效，避免误用历史图片；
- 价格、库存、SKU、包装和运费模板写入后回读校验；
- 只执行一次平台质量检测，并将结果保存到 task_state.json。

## 安全边界

price_inventory.xlsx、data/、automation/、PDF、照片、.chrome-profile/、Cookie、账号凭据和 .env 都是用户业务资料。未经用户针对具体路径明确授权，不得删除、移动、改名、清空或覆盖，也不得在 Git/worktree 清理时处理这些路径。

工具没有自动点击“保存草稿”或发布商品的功能。详情尺寸图、关键证据或当前型号图片缺失时会停止；质量检测错误为 0 后只验证按钮仍是“保存草稿”，输出 READY_TO_SAVE 并停下，最终动作由用户决定。
