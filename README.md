# 1688 持久化草稿上传器

该工具通过 Playwright CDP 连接本机 Google Chrome 的 `9223` 端口，读取指定型号已经准备好的本地资料，一次完成 1688 固定类目商品表单，并停在“保存草稿”前。仓库同时包含可安装的 Codex `auto-alibaba` Plugin 和 `upload-1688-products` Skill。

## 克隆与安装

```powershell
git clone https://github.com/liucace/Auto-Alibab.git
Set-Location Auto-Alibab
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
```

也可以先执行无写入检查：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1 -CheckOnly
```

在 Codex 中打开克隆后的仓库，重启 Codex 后从仓库 marketplace 安装 `auto-alibaba` Plugin。若仓库 marketplace 没有自动出现，可运行 `codex plugin marketplace add .` 后重启 Codex。Plugin 只包含工作流，不包含商品资料或登录状态。

Chrome 必须使用专用用户目录和远程调试端口启动，并提前登录 `work.1688.com`：

```powershell
$ProjectRoot = (Get-Location).Path
$ChromeProfile = Join-Path $ProjectRoot ".chrome-profile"
& "$env:ProgramFiles\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9223 `
  --user-data-dir="$ChromeProfile"
```

## 资料约定

```text
price_inventory.xlsx
data/draft_saved/<MODEL>/
  <PDF规格书>
  <四张产品照片>
  upload_optimized/<照片名>-square.jpg
  upload_optimized/detail-drawing.jpg
automation/<MODEL>/
  preparation_evidence.json
  1688_payload.json
  image_analysis.json
  detail_assets.json
  detail.html
  task_state.json
```

`detail_assets.json` 指定当前型号 PDF 文件、产品图纸页、归一化裁剪范围和尺寸图输出路径。上传器会保留原 PDF，生成小于平台限制的尺寸图副本，并缓存其 1688 托管地址供中断续跑复用。

`preparation_evidence.json` 是资料与运行 JSON 之间的证据层。操作 Skill 会先核对 PDF 和四张照片，再生成该文件；用户不需要手写。程序只负责校验精确型号、读取库存、确定性生成 1:1 白边 JPEG 和三个运行 JSON，不会自动猜测 PDF 图纸中无法可靠文本提取的尺寸。

Excel 必须存在精确型号行。价格或库存为空时分别使用 `10000`、`50`；型号行不存在时停止。

## 使用

先做只读检查：

```powershell
python -m app.cli doctor --root .
```

根据已经核验的证据生成运行产物（不会打开浏览器）：

```powershell
python -m app.cli prepare "W3G800-KS39-03/F01" --root .
```

上传并填写一个型号：

```powershell
python -m app.cli run W3G630-NU33-03 --root .
```

默认规则固定为：

- 类目：机械及行业设备 > 风机、排风设备 > 工业风扇 > 其他工业风扇
- 发货时效：48 小时
- 运费模板：运费
- 四张主图
- 参考页忠实版 GEO 详情：产品尺寸图、场景使用、产品组成、型号定义、买家选择理由、核心参数、适用场景、选型提醒、采购确认、FAQ 与一句话选型
- 详情至少五张当前型号真实图片：一张 PDF 尺寸图和四张实拍图
- 只执行一次平台质量检测

业务型号始终保留 `/` 等原字符，目录名使用统一的无斜杠键。运行页面用完整型号标记；只有本地主图 SHA-256 指纹与页面记录一致时才会复用已上传图片，图片内容改变后会新建未保存页面，避免误用旧媒体。

价格、库存、SKU、包装和运费模板写入后都会回读，首次不一致会自动重试一次。质量检测结果在 `task_state.json` 中同时记录错误总数、建议和包含区块/字段/提示的 `error_details`，便于直接定位阻塞项。

## 安全边界

工具没有保存草稿、发布商品或点击发布按钮的函数。详情尺寸图、关键参数或当前型号图片缺失时会在覆盖编辑器前停止。质量检测错误为 `0` 后仅验证 `#saveDraftButton` 的文本严格等于“保存草稿”，随后输出 `READY_TO_SAVE` 并停止。保存动作由用户确认后另行执行。
