# 1688 商品自动上传 Skill 设计

## 目标

在个人 Codex Skills 目录创建 `upload-1688-products`，让本机其他 Codex 会话能够通过“快速上传型号 XXX”等请求，稳定调用 `D:\Auto-Alibab` 的现有持久化上传器。

Skill 只负责编排、检查和安全约束，不复制上传器代码，也不修改现有业务实现。

当前上传器没有 `prepare` 命令，因此本 Skill 的直接上传范围是“本地原始资料和三个JSON自动化产物均已准备完成的型号”。如果型号尚未准备，Skill 必须列出缺失项并停止，不得声称已经完成端到端上传，也不得临时猜测或编造商品参数。

## 安装位置与触发

- 安装目录：`C:\Users\小城\.codex\skills\upload-1688-products`
- 典型触发语：
  - “快速上传型号 W3G710-NU31-03”
  - “上传1688商品 XXX”
  - “继续1688草稿上传”
- 固定项目根目录：`D:\Auto-Alibab`
- 固定执行目录：`D:\Auto-Alibab`

## 工作流

1. 从用户请求中取得并规范化型号，不猜测相近型号。请求没有型号时，先使用 Skill 自带的 `scripts/inspect_session.py` 读取Chrome页面的 `window.name`，再检查最近的 `automation/*/task_state.json`。只有页面标签和符合当前格式的状态唯一指向同一型号时才能续传，否则询问用户型号。忽略 `READY_TO_SAVE_DRAFT`、`DRAFT_SAVED` 等旧版状态。
2. 确认项目存在，并读取项目 `README.md` 获取当前命令契约。所有项目命令均以 `D:\Auto-Alibab` 为工作目录执行。
3. 先确认Python 3.12，再在项目目录运行 `python -m app.cli version` 验证应用及运行时依赖可导入。只有该命令因依赖缺失而失败时才运行 `python -m pip install -e .`；不默认安装开发依赖，安装失败则停止并报告。
4. 请求 `http://127.0.0.1:9223/json/version`。端口不可用时，定位本机 Google Chrome，并使用项目专用用户目录 `D:\Auto-Alibab\.chrome-profile` 和 `--remote-debugging-port=9223` 启动；等待端口就绪后再次检查。不得改用内置浏览器或Playwright自带Chromium。
5. 运行 `python -m app.cli doctor --root D:\Auto-Alibab`。任何检查失败时停止，不继续运行上传命令。
6. 运行 `scripts/inspect_session.py --model <MODEL> --cdp-url http://127.0.0.1:9223`。脚本通过Playwright CDP只读连接本机Chrome，仅读取页面URL、`window.name`、登录/发布表单状态和当前主图托管URL数量，不点击、不填写、不导航。只有 `window.name` 严格等于 `1688-uploader:<MODEL>` 的发布页才属于当前型号。
7. 运行 `scripts/preflight.py --model <MODEL> --root D:\Auto-Alibab --existing-main-images <COUNT>`。脚本复用项目的型号规范化、Excel读取和素材目录选择函数，并以JSON输出最终型号、价格、库存、素材目录和检查结果。Excel必须存在精确型号行；素材目录必须严格按照上传器的 `data/processing/<MODEL>`、`data/inbox/<MODEL>`、`data/draft_saved/<MODEL>` 顺序选择第一个存在的目录。PDF、四张当前型号照片、`1688_payload.json`、`image_analysis.json` 和 `detail_assets.json` 必须齐全且型号一致。
8. `preflight.py` 校验 `1688_payload.json` 中的固定业务字段，不依赖当前未接入应用代码的YAML配置：`category_id` 必须为 `1034320`，`industry_category_id` 必须为 `2293`，`delivery_time` 必须为 `48小时发货`，`shipping_template` 必须为 `运费`。任一不符立即停止，不让上传器直接采用错误值。
9. 当当前型号页面没有恰好4张托管主图时，`preflight.py` 检查 `image_analysis.json` 选中的前四张本地主图均存在、非空且每张严格小于 `5,000,000` 字节；没有合规副本时停止并报告。如果带当前型号标签的页面已经有4张有效1688托管主图，则允许断点续传，不因不会再次上传的本地图片大小而阻塞。
10. 运行 `scripts/run_upload.py --model <MODEL> --root D:\Auto-Alibab --cdp-url http://127.0.0.1:9223`。脚本在调用CLI前保存状态文件是否存在、文件大小、SHA-256和纳秒级修改时间，再调用 `python -m app.cli run <MODEL> --root D:\Auto-Alibab`，保留退出码、标准输出和错误输出，最后以JSON输出本次运行结论。
11. `run_upload.py` 只有在状态文件指纹相对运行前发生变化、`model` 与请求一致且结构符合本次结果时，才采用新状态。命令失败时先使用本次CLI的退出码和错误输出分类：
   - 新写入的 `FAILED`：报告保存的异常类型和页面地址；只重试明确可恢复的网络中断或上传中断。
   - 新写入的 `BLOCKED`：报告质量错误和待处理建议，不绕过检查。
   - 状态文件没有更新：以本次错误输出为准。型号行不存在、素材加载失败、CDP连接失败和登录页跳转均可能发生在状态存储器创建前，不得引用旧状态。
   - 登录失效、页面结构变化、素材缺失、相册不存在或图片超限：停止并给出准确处理项。
12. 只有本次运行新写入的状态满足以下结构时，`run_upload.py` 才输出 `READY_TO_SAVE`：`status` 为 `READY_TO_SAVE`、`quality_check.errors` 为 `0`、`detail.template_version` 为 `reference-faithful-v1`、`detail.image_count` 为 `5`、`browser.cdp_url` 为 `http://127.0.0.1:9223`，且 `browser.page_url` 属于1688发布页面。四张主图就绪由本次CLI成功路径返回4个托管URL这一上传器不变量保证；如需独立复核，再由 `inspect_session.py` 读取当前页面DOM。全部通过后才向用户报告页面已停在保存草稿前。

## 固定业务规则

- 型号行不存在时停止。
- 型号行存在但价格或库存为空时，分别使用 `10000` 和 `50`。
- 类目固定为“机械及行业设备 > 风机、排风设备 > 工业风扇 > 其他工业风扇”。
- 固定类目ID为 `category_id=1034320`、`industry_category_id=2293`。
- 发货时效为48小时。
- 包装长宽高取PDF型号图纸，重量取型号重量。
- 运费模板选择“运费”，不选择“8元”。
- 使用本机 Google Chrome、Playwright CDP 和 `9223` 端口。
- 默认使用1688图片相册 `ebm(L)` 或 `ebm(LCC)`；两者均不存在时停止，不擅自选择其他相册。

## 安全边界

- Skill 不点击“保存草稿”、发布或任何等价按钮。
- 只有严格验证 `READY_TO_SAVE`、质量错误为零并确认按钮文本为“保存草稿”后，才报告完成。
- 页面结构变化、登录失效、关键素材缺失或上传失败时停止，不绕过质量检查。
- 不复制或存储1688账号、Cookie、密码等登录凭据。
- 不关闭用户现有Chrome页面；只复用带当前型号会话标签的页面，避免覆盖其他型号的编辑页。
- 自动重试不得从头重复上传已经托管成功的图片，必须依赖现有页面、托管地址和 `task_state.json` 续跑。

## Skill 结构

```text
upload-1688-products/
├─ SKILL.md
├─ agents/
│  └─ openai.yaml
└─ scripts/
   ├─ inspect_session.py
   ├─ preflight.py
   └─ run_upload.py
```

`SKILL.md` 保持简洁，以触发条件、三个确定性脚本的调用顺序和安全边界为核心。上传器自身的详细说明继续以项目 `README.md` 和CLI帮助为准。新会话不得为这些检查临时拼接替代脚本；若Skill脚本失败，应报告错误并修复同一脚本。

Skill 脚本不重复实现商品加载、表单填写、详情生成或质量检测逻辑。`preflight.py` 必须导入并复用项目现有函数，只额外实现上传器尚未提供的固定业务字段和主图字节限制；若静态检查与上传器的真实校验结果冲突，以上传器返回结果为准，并停止等待人工复核。

项目中的 `config/categories.yaml` 和 `config/logistics_rules.yaml` 当前不是运行时数据源。Skill 可以把它们用于人工交叉检查，但固定业务字段是否安全，必须以对 `1688_payload.json` 的显式校验结果为准。

## 验证

- RED：记录未安装 Skill 时，新会话无法自动获得项目路径、命令、安全边界、无型号续传和失败分类规则的基线缺口。
- GREEN：验证 Skill 元数据、目录结构和内容规范；分别测试三个脚本。场景覆盖型号提取、旧版及缺字段状态排除、状态文件指纹、素材目录优先级、固定业务字段、5,000,000字节边界、已有4张托管主图的断点续传、缺失素材、9223不可用、未登录、连接前失败、`BLOCKED` 和严格结构的 `READY_TO_SAVE` 报告。
- 新会话验收：安装后在一个新的Codex会话中用“快速上传型号 XXX”触发，确认能够发现Skill并遵循相同安全边界。真实1688运行仍停在保存草稿前。
- 回归：运行项目现有测试，确保新增 Skill 不影响上传器。

## 非目标

- 不将项目改造成跨电脑安装包。
- 不把上传器源代码复制进 Skill。
- 不自动创建缺失的产品原始资料。
- 不在缺少 `1688_payload.json`、`image_analysis.json` 或 `detail_assets.json` 时临时生成未经验证的替代数据。
- 不自动保存草稿或发布商品。
