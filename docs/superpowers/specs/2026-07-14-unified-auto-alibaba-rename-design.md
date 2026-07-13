# Auto-Alibaba 统一改名设计

## 目标

把当前项目缺少末尾字母的旧名称统一迁移为 `Auto-Alibaba`，覆盖 GitHub 仓库、本地项目目录、Codex Plugin 显示名称、当前说明和历史文档。迁移后，面向使用者的项目名称只有 `Auto-Alibaba`。

Codex Plugin 的技术标识遵守小写连字符规范，继续使用 `auto-alibaba`。环境变量继续使用 `AUTO_ALIBABA_ROOT`。这些是 `Auto-Alibaba` 的技术形式，不属于未迁移的旧名称。

## 命名结果

| 对象 | 迁移后名称 |
| --- | --- |
| GitHub 仓库 | `liucace/Auto-Alibaba` |
| 本地项目目录 | `D:\Auto-Alibaba` |
| Plugin 显示名称 | `Auto-Alibaba` |
| Plugin 目录 | `plugins/auto-alibaba` |
| Plugin manifest ID | `auto-alibaba` |
| Marketplace Plugin ID | `auto-alibaba` |
| 项目根目录环境变量 | `AUTO_ALIBABA_ROOT` |
| 上传 Skill ID | `upload-1688-products` |

上传 Skill 的名称描述任务能力，不是项目品牌，因此不改名。

## 仓库内容迁移

更新所有 Git 跟踪文本中的旧项目名称和固定旧目录，包括：

- `README.md` 的仓库链接、克隆目录、Plugin 安装说明；
- `AGENTS.md` 的仓库标题；
- Plugin manifest 的 `interface.displayName`；
- Skill 的项目名称说明；
- 测试中的 Plugin 路径和项目路径契约；
- 历史设计规格和实施计划中的仓库、目录与命令示例。

Plugin 文件夹和 manifest ID 已经是目标技术标识 `auto-alibaba`，不进行无意义的大小写目录改动。Marketplace 使用相对路径 `./plugins/auto-alibaba`，保持可移植。

新增或更新分发契约测试，用边界明确的正则检测“缺少末尾字母的独立旧名称”，避免把正确的新名称误判为旧名称前缀。测试同时确认：

- Plugin manifest ID 和外层目录仍为 `auto-alibaba`；
- Plugin 显示名称严格为 `Auto-Alibaba`；
- README 克隆地址严格指向 `liucace/Auto-Alibaba`；
- 当前运行文档不包含固定旧项目目录；
- Git 跟踪文本不残留独立旧名称。

## Plugin 更新与本机同步

Plugin 内容发生变化后，使用 `plugin-creator` 提供的 cachebuster 脚本更新 manifest 版本后缀，随后运行 Plugin 和 Skill 验证器。不得手工追加多个 cachebuster。

验证后的仓库 Skill 同步到当前用户的 `upload-1688-products` Skill 目录。由于仓库 Marketplace 的绝对位置会随本地目录改名而变化，本地目录迁移后重新登记 `D:\Auto-Alibaba` 下的 Marketplace，并重新安装或刷新 `auto-alibaba` Plugin。Codex 重启或新建任务后加载新路径。

## 外部和本地迁移顺序

1. 在现有本地目录中完成文本、Plugin 和测试变更。
2. 运行完整测试、Ruff、mypy、Plugin/Skill 验证和公开载荷检查。
3. 提交并推送当前 GitHub 仓库。
4. 使用 GitHub CLI 把仓库改名为 `Auto-Alibaba`。
5. 把本地 `origin` 更新为新的 GitHub URL，并验证远程 `main` 与本地提交一致。
6. 从项目父目录把本地文件夹改为 `D:\Auto-Alibaba`。
7. 在新目录重新验证 Git、项目检查、Marketplace 和本机 Skill。

GitHub 官方说明仓库改名后，常规网页流量以及旧地址的 `git clone`、`fetch`、`push` 会重定向到新名称，但 GitHub Pages 项目站点 URL 和被其他工作流引用的仓库托管 Action 不适用同一保证。本仓库当前没有 `.github/` 目录，也不发布 Pages 或仓库托管 Action；迁移仍会主动更新 README、remote 和安装说明，不依赖旧 URL 重定向。

## 本地目录安全

本地目录改名是最后一步。执行前解析并核对源路径严格等于当前项目根目录、目标路径严格等于 `D:\Auto-Alibaba`，并确认目标目录不存在。不得递归复制后删除源目录，也不得使用跨 shell 拼接的移动命令。

如果专用 Chrome 或其他进程占用 `.chrome-profile` 导致目录无法改名，则保持 GitHub、代码和本地仓库完整，不强制终止进程；准确提示使用者关闭专用 Chrome 后继续最后一步。

现有未跟踪文件和所有被忽略的业务数据、Chrome 配置、登录状态必须随项目目录整体保留，不提交、不删除。

## 验证与完成标准

迁移完成必须满足：

1. 项目测试、Ruff 和 mypy 全部通过。
2. Plugin 与 Skill 验证通过，Plugin cachebuster格式正确。
3. 公开仓库没有业务资料、凭据、个人用户路径或独立旧名称。
4. GitHub 显示 `liucace/Auto-Alibaba`，可见性和默认分支保持不变。
5. `origin` 指向新的仓库 URL，本地和远程 `main` 提交一致。
6. 本地项目根目录为 `D:\Auto-Alibaba`，原目录不再存在。
7. 新路径下 `setup.ps1 -CheckOnly` 通过。
8. Plugin 显示名称为 `Auto-Alibaba`，技术 ID 为 `auto-alibaba`。
9. 本机安装的 Skill 与仓库版本逐文件一致。
10. 原有未跟踪配置和本地业务数据保持不变。
