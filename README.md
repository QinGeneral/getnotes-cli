# getnotes-cli 🗂️

[中文](README.md) | [English](README_EN.md)

Get笔记 Cli 下载工具和 MCP 集成，基于官方 OpenAPI 支持批量下载、知识库管理、语义搜索、Markdown 导出、录音图片等附件下载。

> **初衷与设计理念：**
> - 🤖 **Agent 工作流**：提供标准化的 CLI 和 MCP 接入，便于无缝嵌入到各类大模型 Agent 或自动化流程中，充当高质量的个人知识上下文。
> - 📦 **数据自有化**：将你在平台积攒的笔记、知识库等数字资产完整下载到本地，实现数据的真正自有化与安全备份。

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## ✨ 功能

- 🔐 **官方 OpenAPI 鉴权** — 使用 API Key + Client ID，适合本地、服务器和 Agent 工作流
- 📥 **批量下载** — 分页拉取全部笔记，支持指定数量
- 📤 **新建笔记** — 支持通过本地 Markdown 或文本文件创建笔记，并支持自动上传内嵌图片
- 🗑️ **删除笔记** — 按笔记 ID 删除云端笔记，支持交互确认与自动化调用
- 🔍 **语义搜索** — 使用官方 OpenAPI recall 接口召回相关笔记
- 📚 **知识库管理** — 查看、下载我的知识库与订阅知识库
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
- `search_notes(query)`: 使用官方语义搜索返回相关笔记。
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
# 配置官方 OpenAPI 凭证（推荐）
getnotes login --api-key "gk_live_xxx" --client-id "cli_xxx"

# 或使用环境变量
export GETNOTE_API_KEY="gk_live_xxx"
export GETNOTE_CLIENT_ID="cli_xxx"

# legacy token 仅用于 download-tree 等官方 OpenAPI 未覆盖的能力
getnotes login --legacy-token "Bearer eyJhbGci..."
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

### 删除笔记

```bash
# 按笔记 ID 删除云端笔记（执行前提示确认）
getnotes delete <笔记ID>

# 跳过确认，适用于脚本或 Agent 调用
getnotes delete <笔记ID> --confirm
getnotes delete <笔记ID> -y

# 直接传入 API Key（Client ID 仍从配置或环境读取）
getnotes delete <笔记ID> --api-key "gk_live_xxx" -y
```

此命令删除云端笔记，保留本地已下载的文件与缓存。

### 搜索笔记

```bash
# 使用官方语义搜索笔记
getnotes search "AI 提效"

# 自定义召回数量（官方最大 10）
getnotes search "AI 提效" --page-size 10
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

# 直接传 API Key 下载（Client ID 仍从配置或环境读取）
getnotes download --api-key "gk_live_xxx" --limit 20
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

# 创建知识库
getnotes notebook create "读书笔记" --description "读书摘录和想法"

# 下载官方 OpenAPI 未覆盖的目录树与文件资源（legacy）
getnotes notebook download-tree --name "读书笔记"

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

# 下载订阅知识库目录树与文件资源（legacy）
getnotes subscribe download-tree --name "某知识库"

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

# 从知识库移除笔记
getnotes notebook remove-note --note-id <笔记ID> --id abc123
```

## 🧭 能力边界

| 能力 | 后端 |
|------|------|
| 文本/链接/图片笔记创建 | 官方 OpenAPI |
| 笔记列表、详情、更新、删除、分享 | 官方 OpenAPI |
| 搜索 | 官方 OpenAPI 语义搜索 |
| 我的知识库/订阅知识库列表、创建、笔记列表、加/移笔记 | 官方 OpenAPI |
| Markdown、附件落盘、缓存、索引、HTML/PDF 导出 | 本地逻辑 |
| 知识库目录树递归下载、知识库文件资源下载 | legacy 专用命令 `download-tree` |
| 创建本地音频/视频笔记 | 暂不支持 |

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

## 🔐 凭证管理

- OpenAPI API Key / Client ID 缓存在 `~/.getnotes-cli/auth.json`
- 也支持 `GETNOTE_API_KEY` / `GETNOTE_CLIENT_ID` 环境变量
- Legacy Bearer token 只用于 `download-tree`，缓存在 `~/.getnotes-cli/legacy_auth.json`
- 官方 API 支持的能力不会自动 fallback 到 legacy API

## ⚙️ 配置文件

用户配置保存在 `~/.getnotes-cli/config.json`，支持以下配置项：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `output` | string | `~/Downloads/getnotes_export` | 默认输出目录 |
| `delay` | float | `0.5` | 请求间隔（秒） |
| `page-size` | int | `20` | 每页拉取数量 |

*注：缓存清单文件 `cache_manifest.json` 也会统一保存在此目录。*

## ⚠️ 注意事项

- 首次使用请先运行 `getnotes login --api-key <key> --client-id <id>` 配置官方凭证
- 附件 URL 中的签名有过期时间，建议一次性下载完成
- 已下载的附件不会重复下载（自动跳过）
- 默认下载前 100 条用于调试，确认无误后使用 `--all` 下载全部
- 知识库下载按知识库名称创建子目录，统一保存在 `notebooks/` 下

## 🙏 致谢

- 部分登录逻辑及设计参考自 [notebooklm-mcp-cli](https://github.com/jacob-bd/notebooklm-mcp-cli)。
