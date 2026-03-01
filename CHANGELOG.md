# 更新日志 (Changelog)

本项目的所有重要更改都将统一记录在此文件中。

此文件的格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
并且本项目遵循 [语义化版本规范 (Semantic Versioning)](https://semver.org/spec/v2.0.0.html)。

## [0.2.0] - 2026-03-01

### 新增 (Added)
- **笔记加入知识库**：新增 `getnotes notebook add-note` 命令，支持将指定笔记（通过 `--note-id`）加入指定知识库（通过 `--name` 或 `--id`）。MCP 同步新增 `add_note_to_notebook(note_id, notebook_id)` 工具。
- **MCP `read_note` 工具**：新增 `read_note(note_id)` MCP 工具，支持通过笔记 ID 直接读取笔记全文 Markdown 内容；优先读取本地缓存文件，本地未命中时自动通过搜索 API 回退获取内容。
- **HTML 导出**：新增 `getnotes export` 命令，将本地已下载的 Markdown 笔记批量转换为带样式的 HTML 文件，并自动生成 `index.html` 索引页，支持 `--force` 重新转换与自定义输出目录。
- **同步检测**：新增 `getnotes sync-check` 命令，对比服务端笔记总数与本地缓存数量，直观展示有多少新笔记待下载。

### 修复 (Fixed)
- **INDEX.md 生成**：修复默认模式（不开启 `--save-json`）下 INDEX.md 笔记列表为空的问题。现在优先使用缓存清单（`cache_manifest.json`）生成索引，无需依赖 `note.json`；索引表格新增标题列和创建时间列，改为时间降序排列。
- **Token 401 错误提示**：下载时遇到 HTTP 401 错误时，现在会明确提示"Token 已过期，请重新运行 `getnotes login`"，而非显示通用错误信息。

## [0.1.6] - 2026-02-28

### 修复 (Fixed)
- **MCP Server stdio 协议兼容**：修复 MCP 工具（如 `download_subscribed_notebook`）执行时因 `print()` 输出到 stdout 导致 JSON-RPC 协议解析失败的问题，将所有下载模块的进度输出改为 `logging`（输出到 stderr），确保 MCP stdio 传输模式正常工作。

## [0.1.5] - 2026-02-28

### 新增 (Added)
- **笔记搜索功能**：新增 `search` CLI 命令，支持根据关键词搜索笔记，结果以 Rich 表格展示，支持分页浏览。
- **MCP 搜索工具**：MCP 服务器新增 `search_notes(query)` 工具，允许 LLM 客户端直接搜索用户笔记并返回结构化结果。

## [0.1.3] - 2026-02-27

### 新增 (Added)
- **MCP 服务器支持**：引入了一个由 `fastmcp` 驱动的原生 MCP (Model Context Protocol) 服务器，允许集成各种大模型客户端（例如 Claude Desktop），通过 `getnotes-mcp` 直接为用户管理笔记和知识库内容。新增工具如下：
  - `download_notes(limit=10)`
  - `create_note(content)`
  - `create_link_note(url)`
  - `list_notebooks()`
  - `download_notebook(notebook_id)`
  - `list_subscribed_notebooks()`
  - `download_subscribed_notebook(notebook_id)`

## [0.1.2] - 2026-02-27

### 新增 (Added)
- **链接笔记**：新增 `create-link` 命令，支持通过 URL 链接自动抓取网页内容并创建笔记。

## [0.1.1] - 2026-02-27

### 新增 (Added)
- **创建笔记功能**：实现创建新笔记功能，支持图片上传并自动转换链接。提供 CLI 命令集成支持本地直接新建笔记。
- **文档完善**：新增了有关知识库 (notebooks)、笔记 (notes) 以及 Agent 工作流 (AGENT.md) 的使用说明；添加了 GitHub 评论操作文档指南。
- **发布配置更新**：优化与新增部分 GitHub Workflow 以支持自动化部署与评论。

## [0.1.0] - 2026-02-27

这是 `getnotes-cli` 的首次发布版本，包含以下核心功能集锦：

### 新增 (Added)
- **核心下载功能**：实现“得到笔记”的自动下载，统一将笔记保存为易于阅读的 Markdown 格式文档，并嵌入本地化保存的附件与图片。
- **浏览器自动登录**：新增基于浏览器的登录功能，一键自动获取最新的认证请求头（Bearer tokens），无需繁杂的手动配置。
- **多维度下载命令**：
  - 支持普通笔记内容的拉取与组织（`download`, `download-all`）。
  - 支持笔记订阅管理，支持列出已订阅的知识库、下载特定知识库以及一次性下载所有订阅知识库的笔记内容。
- **配置持久化管理**：引入 CLI 配置模块（基于 `~/.getnotes-cli/config.json` 开发的 `settings.py`），支持对输出目录、请求延迟和单页拉取数量等参数进行个性化和持久化设置。
- **精细化控制选项**：
  - 新增 `--save-json` 参数，支持显式保存技术文件（例如，JSON 格式的 API 响应源数据），默认仅保存 Markdown 和相关附件文件以精简空间。
  - 新增下载限额提示机制，当遭遇接口下载限制时智能提醒用户。
- **性能优化机制**：内置深度的 API 请求和笔记处理缓存机制 (`cache_manifest.json`)，避免重复拉取和处理相同笔记带来的成本损耗，并同时修复了早期开发版本里本地笔记文件夹比对不准确导致重复下载的问题。
