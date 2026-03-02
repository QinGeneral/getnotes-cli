# getnotes-cli 🗂️

[中文](#getnotes-cli-) | [English](#english)

Get笔记 Cli 下载工具和 MCP 集成，支持自动登录、批量下载、知识库管理、笔记搜索、Markdown 导出、录音图片等附件下载。

> **初衷与设计理念：**
> - 🤖 **Agent 工作流**：提供标准化的 CLI 和 MCP 接入，便于无缝嵌入到各类大模型 Agent 或自动化流程中，充当高质量的个人知识上下文。
> - 📦 **数据自有化**：将你在平台积攒的笔记、知识库等数字资产完整下载到本地，实现数据的真正自有化与安全备份。

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## ✨ 功能

- 🔐 **自动登录** — 通过 Chrome DevTools Protocol 自动获取 Bearer token，无需手动抓包
- 📥 **批量下载** — 分页拉取全部笔记，支持指定数量
- 📤 **新建笔记** — 支持通过本地 Markdown 或文本文件创建笔记，并支持自动上传内嵌图片
- � **笔记搜索** — 根据关键词搜索笔记，支持分页浏览
- �📚 **知识库管理** — 查看、下载我的知识库与订阅知识库
- 📝 **Markdown 导出** — 每条笔记保存为 Markdown，包含元信息、标签、正文、引用内容
- 🔊 **附件下载** — 自动下载音频、图片附件，并在 Markdown 中内嵌链接
- 💾 **缓存管理** — 自动跳过已下载且未变化的笔记，支持增量更新
- 📁 **Markdown-only 模式** — 默认值保存 Markdown 和附件，不保存技术文件，可以通过选项开启
- ⚙️ **持久化配置** — 通过 `config` 命令保存常用参数，无需每次重复输入
- ⏱️ **可配置间隔** — 自定义请求间隔，避免频率限制
- 📊 **自动索引** — 自动生成笔记索引文件 `INDEX.md`

## 🤖 MCP 服务器

Get笔记 CLI 提供原生的 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) 服务器支持，允许集成 [Claude Desktop](https://claude.ai/download) 等 AI 客户端直接为你管理笔记和知识库。

### 配置 Claude Desktop

编辑 Claude Desktop 配置文件 `claude_desktop_config.json`（通常在 `~/Library/Application Support/Claude/`）：

```json
{
  "mcpServers": {
    "getnotes": {
      "command": "uvx",
      "args": [
        "--refresh",
        "--from",
        "getnotes-cli",
        "getnotes-mcp"
      ]
    }
  }
}
```

> `--refresh` 参数确保每次启动时自动拉取 PyPI 上的最新版本，无需手动执行 `uv tool upgrade`。

> **注意**：在使用 MCP 服务器前，确保你在终端执行过 `getnotes login` 获取了 Token。

### 可用 MCP Tools

- `download_notes(limit=10)`: 下载近期笔记为 Markdown 文件。
- `create_note(content)`: 直接提交文本建立新笔记。
- `create_link_note(url)`: 通过 AI 解析链接创建深度笔记。
- `search_notes(query)`: 根据关键词搜索笔记并返回匹配结果（含全文内容）。
- `read_note(note_id)`: 通过笔记 ID 读取笔记全文 Markdown 内容。
- `list_notebooks()`: 获取你创建的知识库列表及对应 ID。
- `download_notebook(notebook_id)`: 下载指定的知识库内容。
- `list_subscribed_notebooks()`: 获取订阅知识库列表。
- `download_subscribed_notebook(notebook_id)`: 下载指定的订阅知识库。
- `add_note_to_notebook(note_id, notebook_id)`: 将指定笔记加入知识库。

## 📦 Cli 安装

### 使用 uv 安装（推荐）

```bash
uv tool install getnotes-cli
```

### 使用 pip 安装

```bash
pip install getnotes-cli
```

### 源码安装（本地开发）

```bash
cd getnotes-cli
pip install -e .
```

安装后即可全局使用 `getnotes` 命令。

## 🚀 使用方法

### 登录

```bash
# 自动浏览器登录（推荐）
# 会打开 Chrome，导航到得到笔记页面，登录后自动捕获 token
getnotes login

# 手动输入 token（跳过浏览器）
getnotes login --token "Bearer eyJhbGci..."
```

### 新建笔记

```bash
# 从本地 Markdown 或文本文件创建得到笔记
getnotes create --file my_note.md

# 创建笔记并附带一张图片（图片将自动上传并追加到正文末尾）
getnotes create -f my_note.md --image cover.jpg

# 创建笔记并附带多张图片（多次指定 -i 或 --image 选项）
getnotes create -f my_note.md -i img1.png -i img2.jpg

# 通过链接创建笔记（AI 自动分析并生成深度笔记）
getnotes create-link <url>
```

### 搜索笔记

```bash
# 根据关键词搜索笔记
getnotes search "AI 提效"

# 查看第 2 页结果
getnotes search "AI 提效" --page 2

# 自定义每页数量
getnotes search "AI 提效" --page-size 20
```

### 下载笔记

```bash
# 下载前 100 条笔记（默认）
getnotes download

# 下载全部笔记
getnotes download --all

# 自定义下载数量
getnotes download --limit 50

# 保存技术文件（默认不包含 JSON 等原始数据）
getnotes download --save-json

# 指定输出目录
getnotes download --output ~/Desktop/my_notes

# 调整请求间隔（秒）
getnotes download --delay 1.0

# 自定义每页拉取数量
getnotes download --page-size 50

# 强制重新下载，忽略缓存
getnotes download --force

# 组合使用
getnotes download --all --save-json --delay 1.0

# 直接传 token 下载（一步到位，跳过登录缓存）
getnotes download --token "Bearer eyJhbGci..." --limit 20
```

### 知识库管理

```bash
# 查看所有知识库
getnotes notebook list

# 按名称下载指定知识库（模糊匹配）
getnotes notebook download --name "读书笔记"

# 按 ID 下载指定知识库
getnotes notebook download --id abc123

# 下载全部知识库
getnotes notebook download-all

# 带选项下载
getnotes notebook download --name "读书" --save-json --delay 1.0
getnotes notebook download-all --force --output ~/Desktop/notebooks
```

### 订阅知识库

```bash
# 查看所有已订阅的知识库
getnotes subscribe list

# 按名称下载指定订阅知识库
getnotes subscribe download --name "某知识库"

# 按 ID 下载
getnotes subscribe download --id xyz789

# 下载全部订阅知识库
getnotes subscribe download-all

# 带选项下载
getnotes subscribe download --name "某知识库" --save-json --force
getnotes subscribe download-all --delay 1.0 --output ~/Desktop/subscribed
```

### 笔记加入知识库

```bash
# 将笔记加入指定知识库（按名称模糊匹配）
getnotes notebook add-note --note-id <笔记ID> --name "读书笔记"

# 按知识库 ID 精确指定
getnotes notebook add-note --note-id <笔记ID> --id abc123
```

### 导出为 HTML

```bash
# 将所有已下载的笔记导出为 HTML（默认输出到 html_export/ 子目录）
getnotes export

# 指定输出目录
getnotes export --output ~/Desktop/notes_html

# 强制重新转换所有文件
getnotes export --force
```

### 同步检测

```bash
# 检查服务端有多少新笔记待下载
getnotes sync-check
```

### 缓存管理

```bash
# 查看缓存状态
getnotes cache check

# 清除缓存
getnotes cache clear

# 跳过确认提示
getnotes cache clear --confirm
```

### 配置管理

持久化常用参数，避免每次输入。参数优先级：**命令行参数 > 配置文件 > 默认值**。

```bash
# 设置默认输出目录
getnotes config set output ~/Desktop/my_notes

# 设置默认请求间隔
getnotes config set delay 1.0

# 设置每页拉取数量
getnotes config set page-size 50

# 查看所有配置
getnotes config get

# 查看某项配置
getnotes config get output

# 清除所有配置（恢复默认值）
getnotes config reset

# 跳过确认提示
getnotes config reset --confirm
```

### 其他

```bash
# 查看版本
getnotes --version

# 查看帮助
getnotes --help
getnotes create --help
getnotes download --help
getnotes search --help
getnotes notebook --help
getnotes subscribe --help
getnotes config --help
```

## 📁 输出目录结构

默认输出到 `~/Downloads/getnotes_export/`：

```
getnotes_export/
├── INDEX.md                          # 笔记索引
├── api_responses/                    # 原始 API 响应 JSON
│   ├── page_0001.json
│   └── ...
├── notes/                            # 个人笔记
│   ├── 20260226_224958_发芽报告/
│   │   ├── note.md                   # Markdown 笔记
│   │   ├── note.json                 # 原始 JSON 数据
│   │   └── attachments/              # 附件（按需创建）
│   │       ├── attachment_1.mp3
│   │       └── image_1.jpg
│   └── ...
└── notebooks/                        # 知识库笔记（包含我的知识库和订阅知识库）
    ├── 读书笔记/                      # 按知识库名称分目录
    │   ├── INDEX.md
    │   ├── 20260226_笔记标题/
    │   │   └── note.md
    │   └── ...
    └── 某订阅知识库/
        ├── INDEX.md
        └── ...
```

> 默认不会创建 `api_responses/` 目录和 `note.json` 文件。使用 `--save-json` 选项时才会保存这些技术文件。

## 🔐 Token 管理

- Token 通过 CDP（Chrome DevTools Protocol）自动获取
- 缓存在 `~/.getnotes-cli/auth.json`
- 得到 Token 约 30 分钟有效，过期后自动提示重新登录
- 也支持 `--token` 参数手动传入

## ⚙️ 配置文件

用户配置保存在 `~/.getnotes-cli/config.json`，支持以下配置项：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `output` | string | `~/Downloads/getnotes_export` | 默认输出目录 |
| `delay` | float | `0.5` | 请求间隔（秒） |
| `page-size` | int | `20` | 每页拉取数量 |

*注：缓存清单文件 `cache_manifest.json` 也会统一保存在此目录。*

## ⚠️ 注意事项

- 首次使用请先运行 `getnotes login` 登录
- 附件 URL 中的签名有过期时间，建议一次性下载完成
- 已下载的附件不会重复下载（自动跳过）
- 默认下载前 100 条用于调试，确认无误后使用 `--all` 下载全部
- 知识库下载按知识库名称创建子目录，统一保存在 `notebooks/` 下

## 🙏 致谢

- 部分登录逻辑及设计参考自 [notebooklm-mcp-cli](https://github.com/jacob-bd/notebooklm-mcp-cli)。

---

## English

> **Note**: Chinese is the primary language of this project. The section below is a translated reference.

### What is getnotes-cli?

`getnotes-cli` is a CLI tool and MCP integration for [Get Notes (获取笔记)](https://luojilab.com), supporting auto-login, batch download, notebook management, note search, Markdown export, and attachment (audio/image) downloading.

**Design goals:**
- 🤖 **Agent workflows** — Standardized CLI and MCP interfaces for seamless integration into LLM agents and automation pipelines, serving as a high-quality personal knowledge context.
- 📦 **Data ownership** — Download your notes and knowledge bases locally for true ownership and safe backup.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

### ✨ Features

- 🔐 **Auto-login** — Captures Bearer token via Chrome DevTools Protocol; no manual packet sniffing required
- 📥 **Batch download** — Paginated fetch of all notes with configurable limits
- 📤 **Create notes** — Create notes from local Markdown/text files with automatic image upload
- 🔍 **Search** — Keyword search with paginated results
- 📚 **Notebook management** — List and download personal and subscribed notebooks
- 📝 **Markdown export** — Each note saved as Markdown with metadata, tags, body, and quoted content
- 🔊 **Attachment download** — Automatically downloads audio and image attachments with inline links
- 💾 **Cache management** — Skips already-downloaded, unchanged notes; supports incremental updates
- ⚙️ **Persistent config** — Save common parameters via the `config` command
- ⏱️ **Configurable delay** — Custom request intervals to avoid rate limiting
- 📊 **Auto index** — Automatically generates `INDEX.md`

### 🤖 MCP Server

`getnotes-cli` ships a native [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server, allowing AI clients like [Claude Desktop](https://claude.ai/download) to manage your notes and notebooks directly.

**Configure Claude Desktop** — edit `claude_desktop_config.json` (typically at `~/Library/Application Support/Claude/`):

```json
{
  "mcpServers": {
    "getnotes": {
      "command": "uvx",
      "args": [
        "--refresh",
        "--from",
        "getnotes-cli",
        "getnotes-mcp"
      ]
    }
  }
}
```

> `--refresh` ensures the latest PyPI version is pulled on each startup.
> Run `getnotes login` in your terminal at least once before using the MCP server.

**Available MCP Tools:**

| Tool | Description |
|------|-------------|
| `download_notes(limit=10)` | Download recent notes as Markdown files |
| `create_note(content)` | Create a new note from text |
| `create_link_note(url)` | Create a deep note from a URL via AI analysis |
| `search_notes(query)` | Search notes by keyword and return full content |
| `read_note(note_id)` | Read a note's full Markdown by ID |
| `list_notebooks()` | List your notebooks and their IDs |
| `download_notebook(notebook_id)` | Download a specific notebook |
| `list_subscribed_notebooks()` | List subscribed notebooks |
| `download_subscribed_notebook(notebook_id)` | Download a subscribed notebook |
| `add_note_to_notebook(note_id, notebook_id)` | Add a note to a notebook |

### 📦 Installation

```bash
# Recommended
uv tool install getnotes-cli

# pip
pip install getnotes-cli

# Local development
pip install -e .
```

### 🚀 Usage

```bash
# Login (auto browser)
getnotes login

# Login with manual token
getnotes login --token "Bearer eyJhbGci..."

# Download notes (default: 100)
getnotes download

# Download all notes
getnotes download --all

# Download with options
getnotes download --limit 50 --output ~/Desktop/notes --delay 1.0 --save-json

# Create a note from file
getnotes create --file my_note.md

# Create a note with images
getnotes create -f my_note.md -i img1.png -i img2.jpg

# Create a note from a URL
getnotes create-link <url>

# Search notes
getnotes search "keyword" --page 1 --page-size 20

# List notebooks
getnotes notebook list

# Download a notebook by name (fuzzy match)
getnotes notebook download --name "Reading Notes"

# Download all notebooks
getnotes notebook download-all

# Add a note to a notebook
getnotes notebook add-note --note-id <id> --name "Reading Notes"

# List subscribed notebooks
getnotes subscribe list

# Download a subscribed notebook
getnotes subscribe download --name "Some Notebook"

# Export notes to HTML
getnotes export
getnotes export --output ~/Desktop/notes_html --force

# Check sync status (server vs local)
getnotes sync-check

# Cache management
getnotes cache check
getnotes cache clear

# Persistent config
getnotes config set output ~/Desktop/my_notes
getnotes config set delay 1.0
getnotes config get
getnotes config reset
```

### 📁 Output Directory Structure

Default output: `~/Downloads/getnotes_export/`

```
getnotes_export/
├── INDEX.md                          # Note index
├── api_responses/                    # Raw API JSON (only with --save-json)
├── notes/                            # Personal notes
│   ├── 20260226_224958_title/
│   │   ├── note.md                   # Markdown note
│   │   ├── note.json                 # Raw JSON (only with --save-json)
│   │   └── attachments/
│   │       ├── attachment_1.mp3
│   │       └── image_1.jpg
│   └── ...
└── notebooks/                        # Notebooks (personal + subscribed)
    ├── Reading Notes/
    │   ├── INDEX.md
    │   └── ...
    └── ...
```

### 🔐 Token Management

- Token is captured automatically via CDP (Chrome DevTools Protocol)
- Cached at `~/.getnotes-cli/auth.json`
- Valid for ~30 minutes; prompts re-login when expired
- Can also be supplied manually via `--token`

### ⚙️ Configuration File

Settings are stored at `~/.getnotes-cli/config.json`:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `output` | string | `~/Downloads/getnotes_export` | Default output directory |
| `delay` | float | `0.5` | Request interval in seconds |
| `page-size` | int | `20` | Notes per page |

### ⚠️ Notes

- Run `getnotes login` before first use
- Attachment URLs contain expiring signatures — download in one session
- Already-downloaded attachments are not re-downloaded
- Default limit is 100 notes for safety; use `--all` for a full download
- Notebooks are organized into subdirectories under `notebooks/` by name

### 🙏 Credits

- Login logic and design partially inspired by [notebooklm-mcp-cli](https://github.com/jacob-bd/notebooklm-mcp-cli).
