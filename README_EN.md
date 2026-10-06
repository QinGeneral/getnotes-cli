# getnotes-cli 🗂️

[中文](README.md) | [English](README_EN.md)

CLI tool and MCP integration for [Get Notes (获取笔记)](https://luojilab.com), supporting auto-login, batch download, notebook management, note search, Markdown export, and attachment (audio/image) downloading.

> **Design goals:**
> - 🤖 **Agent workflows** — Standardized CLI and MCP interfaces for seamless integration into LLM agents and automation pipelines, serving as a high-quality personal knowledge context.
> - 📦 **Data ownership** — Download your notes and knowledge bases locally for true ownership and safe backup.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## ✨ Features

- 🔐 **Auto-login** — Captures Bearer token via Chrome DevTools Protocol; no manual packet sniffing required
- 📥 **Batch download** — Paginated fetch of all notes with configurable limits
- 📤 **Create notes** — Create notes from local Markdown/text files with automatic image upload
- 🗑️ **Delete notes** — Delete a cloud note by ID, with confirmation or a flag for automation
- 🔍 **Search** — Keyword search with paginated results
- 📚 **Notebook management** — List and download personal and subscribed notebooks
- 📝 **Markdown export** — Each note saved as Markdown with metadata, tags, body, and quoted content
- 🔊 **Attachment download** — Automatically downloads audio and image attachments with inline links
- 💾 **Cache management** — Skips already-downloaded, unchanged notes; supports incremental updates
- 📁 **Markdown-only mode** — Saves only Markdown and attachments by default; raw JSON files opt-in via `--save-json`
- ⚙️ **Persistent config** — Save common parameters via the `config` command
- ⏱️ **Configurable delay** — Custom request intervals to avoid rate limiting
- 📊 **Auto index** — Automatically generates `INDEX.md`

## 🤖 MCP Server

`getnotes-cli` ships a native [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server, allowing AI clients like [Claude Desktop](https://claude.ai/download) to manage your notes and notebooks directly.

### Configure Claude Desktop

Edit `claude_desktop_config.json` (typically at `~/Library/Application Support/Claude/`):

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

> `--refresh` ensures the latest PyPI version is pulled on each startup, so no manual `uv tool upgrade` is needed.

> **Note**: Run `getnotes login` in your terminal at least once before using the MCP server.

### Available MCP Tools

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

## 📦 Installation

### Using uv (recommended)

```bash
uv tool install getnotes-cli
```

### Using pip

```bash
pip install getnotes-cli
```

### From source (local development)

```bash
cd getnotes-cli
pip install -e .
```

After installation, the `getnotes` command is available globally.

## 🚀 Usage

### Login

```bash
# Auto browser login (recommended)
# Opens Chrome, navigates to the Get Notes page, and captures the token after login
getnotes login

# Manual token input (skip browser)
getnotes login --token "Bearer eyJhbGci..."
```

### Create Notes

```bash
# Create a note from a local Markdown or text file
getnotes create --file my_note.md

# Create a note with a single image (auto-uploaded and appended to body)
getnotes create -f my_note.md --image cover.jpg

# Create a note with multiple images
getnotes create -f my_note.md -i img1.png -i img2.jpg

# Create a note from a URL (AI analyzes and generates a deep note)
getnotes create-link <url>
```

### Delete Notes

```bash
# Delete a cloud note by ID (prompts for confirmation)
getnotes delete <note_id>

# Skip confirmation for scripts or agents
getnotes delete <note_id> --confirm
getnotes delete <note_id> -y

# Pass an OpenAPI API Key (Client ID comes from configuration or environment)
getnotes delete <note_id> --api-key "gk_live_xxx" -y
```

This command deletes the cloud note and retains downloaded local files and cache entries.

### Search Notes

```bash
# Search by keyword
getnotes search "AI productivity"

# View page 2
getnotes search "AI productivity" --page 2

# Custom page size
getnotes search "AI productivity" --page-size 20
```

### Download Notes

```bash
# Download first 100 notes (default)
getnotes download

# Download all notes
getnotes download --all

# Custom limit
getnotes download --limit 50

# Save raw JSON files
getnotes download --save-json

# Specify output directory
getnotes download --output ~/Desktop/my_notes

# Adjust request interval (seconds)
getnotes download --delay 1.0

# Custom page size
getnotes download --page-size 50

# Force re-download, ignore cache
getnotes download --force

# Combined options
getnotes download --all --save-json --delay 1.0

# Pass token directly (skip login cache)
getnotes download --token "Bearer eyJhbGci..." --limit 20
```

### Notebook Management

```bash
# List all notebooks
getnotes notebook list

# Download a notebook by name (fuzzy match)
getnotes notebook download --name "Reading Notes"

# Download a notebook by ID
getnotes notebook download --id abc123

# Download all notebooks
getnotes notebook download-all

# With options
getnotes notebook download --name "Reading" --save-json --delay 1.0
getnotes notebook download-all --force --output ~/Desktop/notebooks
```

### Subscribed Notebooks

```bash
# List all subscribed notebooks
getnotes subscribe list

# Download a subscribed notebook by name
getnotes subscribe download --name "Some Notebook"

# Download by ID
getnotes subscribe download --id xyz789

# Download all subscribed notebooks
getnotes subscribe download-all

# With options
getnotes subscribe download --name "Some Notebook" --save-json --force
getnotes subscribe download-all --delay 1.0 --output ~/Desktop/subscribed
```

### Add Note to Notebook

```bash
# Add a note to a notebook by name (fuzzy match)
getnotes notebook add-note --note-id <note-id> --name "Reading Notes"

# Add by notebook ID
getnotes notebook add-note --note-id <note-id> --id abc123
```

### Export to HTML

```bash
# Export all downloaded notes to HTML (default: html_export/ subdirectory)
getnotes export

# Specify output directory
getnotes export --output ~/Desktop/notes_html

# Force re-convert all files
getnotes export --force
```

### Sync Check

```bash
# Check how many new notes are on the server
getnotes sync-check
```

### Cache Management

```bash
# View cache status
getnotes cache check

# Clear cache
getnotes cache clear

# Skip confirmation prompt
getnotes cache clear --confirm
```

### Configuration

Persist common parameters to avoid re-typing. Priority: **CLI args > config file > defaults**.

```bash
# Set default output directory
getnotes config set output ~/Desktop/my_notes

# Set default request interval
getnotes config set delay 1.0

# Set page size
getnotes config set page-size 50

# View all config
getnotes config get

# View a specific key
getnotes config get output

# Reset all config to defaults
getnotes config reset

# Skip confirmation prompt
getnotes config reset --confirm
```

### Other

```bash
# Show version
getnotes --version

# Show help
getnotes --help
getnotes create --help
getnotes download --help
getnotes search --help
getnotes notebook --help
getnotes subscribe --help
getnotes config --help
```

## 📁 Output Directory Structure

Default output: `~/Downloads/getnotes_export/`

```
getnotes_export/
├── INDEX.md                          # Note index
├── api_responses/                    # Raw API JSON (only with --save-json)
│   ├── page_0001.json
│   └── ...
├── notes/                            # Personal notes
│   ├── 20260226_224958_title/
│   │   ├── note.md                   # Markdown note
│   │   ├── note.json                 # Raw JSON (only with --save-json)
│   │   └── attachments/              # Attachments (created as needed)
│   │       ├── attachment_1.mp3
│   │       └── image_1.jpg
│   └── ...
└── notebooks/                        # Notebooks (personal + subscribed)
    ├── Reading Notes/                 # Subdirectory per notebook name
    │   ├── INDEX.md
    │   ├── 20260226_note-title/
    │   │   └── note.md
    │   └── ...
    └── Some Subscribed Notebook/
        ├── INDEX.md
        └── ...
```

> `api_responses/` and `note.json` are not created by default. Use `--save-json` to save these raw files.

## 🔐 Token Management

- Token is captured automatically via CDP (Chrome DevTools Protocol)
- Cached at `~/.getnotes-cli/auth.json`
- Valid for ~30 minutes; prompts re-login when expired
- Can also be supplied manually via `--token`

## ⚙️ Configuration File

Settings are stored at `~/.getnotes-cli/config.json`:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `output` | string | `~/Downloads/getnotes_export` | Default output directory |
| `delay` | float | `0.5` | Request interval in seconds |
| `page-size` | int | `20` | Notes fetched per page |

*Note: The cache manifest `cache_manifest.json` is also stored in this directory.*

## ⚠️ Notes

- Run `getnotes login` before first use
- Attachment URLs contain expiring signatures — complete downloads in one session
- Already-downloaded attachments are not re-downloaded
- Default limit is 100 notes; use `--all` for a full download
- Notebooks are organized into subdirectories under `notebooks/` by name

## 🙏 Credits

- Login logic and design partially inspired by [notebooklm-mcp-cli](https://github.com/jacob-bd/notebooklm-mcp-cli).
