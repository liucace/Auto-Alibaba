# 1688 持久化草稿上传器

该工具通过 Playwright CDP 连接本机 Google Chrome 的 `9223` 端口，读取指定型号已经准备好的本地资料，一次完成 1688 固定类目商品表单，并停在“保存草稿”前。

## 安装

```powershell
python -m pip install -e ".[dev]"
```

Chrome 必须使用专用用户目录和远程调试端口启动，并提前登录 `work.1688.com`：

```powershell
& "$env:ProgramFiles\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9223 `
  --user-data-dir="D:\Auto-Alibab\.chrome-profile"
```

## 资料约定

```text
price_inventory.xlsx
data/draft_saved/<MODEL>/
automation/<MODEL>/
  1688_payload.json
  image_analysis.json
  detail.html
  task_state.json
```

Excel 必须存在精确型号行。价格或库存为空时分别使用 `10000`、`50`；型号行不存在时停止。

## 使用

先做只读检查：

```powershell
python -m app.cli doctor --root D:\Auto-Alibab
```

上传并填写一个型号：

```powershell
python -m app.cli run W3G630-NU33-03 --root D:\Auto-Alibab
```

默认规则固定为：

- 类目：机械及行业设备 > 风机、排风设备 > 工业风扇 > 其他工业风扇
- 发货时效：48 小时
- 运费模板：运费
- 四张主图和四张 GEO 详情图
- 只执行一次平台质量检测

运行页面用完整型号标记。命令中断后再次执行同一型号，会复用原页面和已上传图片，不会从头重复上传。

## 安全边界

工具没有发布商品或点击发布按钮的函数。质量检测错误为 `0` 后仅验证 `#saveDraftButton` 的文本严格等于“保存草稿”，随后输出 `READY_TO_SAVE` 并停止。保存动作由用户确认后另行执行。
