# CLAUDE.md — AI Assistant Guide for getnotes-cli

## Project Overview

`getnotes-cli` is a Python CLI tool for downloading, managing, and exporting notes from the Get Notes (获取笔记) service (luojilab/trytalks platform). It supports batch download, Markdown export, HTML/PDF generation, notebook management, and a Model Context Protocol (MCP) server for Claude Desktop integration.

- **Current version**: 0.2.2
- **Python requirement**: >=3.10
- **Package manager**: [uv](https://docs.astral.sh/uv/) (lock file: `uv.lock`)
- **Build system**: hatchling

---

## Repository Structure

```
getnotes-cli/
├── src/getnotes_cli/          # Main source package
│   ├── __init__.py            # Package version (0.2.0 declared here)
│   ├── cli.py                 # Typer CLI entry point (~1,208 lines)
│   ├── auth.py                # Token management & caching
│   ├── config.py              # API URLs, paths, and request defaults
│   ├── settings.py            # Persistent user configuration
│   ├── cache.py               # Manifest-based note caching
│   ├── cdp.py                 # Chrome DevTools Protocol (auto-login)
│   ├── downloader.py          # Note downloading with pagination
│   ├── creator.py             # Note creation & image upload
│   ├── searcher.py            # Note search
│   ├── notebook.py            # Notebook API client functions
│   ├── notebook_downloader.py # Notebook content downloader
│   ├── markdown.py            # Markdown formatting & filename sanitization
│   ├── exporter.py            # HTML/PDF export (~692 lines)
│   └── mcp/                   # MCP server integration
│       ├── server.py          # fastmcp server (entry: getnotes-mcp)
│       └── tools/
│           ├── notes.py       # MCP note tools
│           └── notebooks.py   # MCP notebook tools
├── tests/                     # pytest test suite
│   ├── test_auth.py
│   ├── test_cache.py
│   ├── test_markdown.py
│   ├── test_searcher.py
│   └── test_settings.py
├── .agent/workflows/          # Agent workflow documentation
├── .github/workflows/         # CI/CD (publish.yml)
├── pyproject.toml             # Project config & dependencies
├── uv.lock                    # Locked dependency versions
├── README.md                  # User documentation (Chinese)
└── CHANGELOG.md               # Version history
```

---

## Development Setup

```bash
# Install dependencies (recommended)
uv sync

# Or with pip in editable mode
pip install -e .

# Run the CLI locally
uv run getnotes --help

# Run the MCP server
uv run getnotes-mcp
```

---

## Running Tests

```bash
# Run all tests
uv run pytest

# Run a specific test file
uv run pytest tests/test_auth.py

# Verbose output
uv run pytest -v
```

Tests live in `tests/` and are configured in `pyproject.toml` under `[tool.pytest.ini_options]`. There is no test coverage requirement enforced by CI, but tests should pass before committing.

---

## CLI Entry Points

| Script | Module | Purpose |
|--------|--------|---------|
| `getnotes` | `getnotes_cli.cli:main` | Main CLI (Typer app) |
| `getnotes-mcp` | `getnotes_cli.mcp.server:main` | MCP server for Claude Desktop |

### Key CLI Command Groups

- **`getnotes login`** — Browser-based (CDP) or token-based auth
- **`getnotes download`** — Batch download notes as Markdown
- **`getnotes create`** — Create notes from local files
- **`getnotes create-link`** — Create notes from URLs via AI
- **`getnotes search`** — Search notes by keyword
- **`getnotes notebook`** — Notebook management (list, download, download-all, add-note)
- **`getnotes subscribe`** — Subscribed notebook management
- **`getnotes config`** — Persistent user settings (set/get/reset)
- **`getnotes cache`** — Cache inspection/clearing
- **`getnotes export`** — Convert Markdown files to HTML or PDF
- **`getnotes sync-check`** — Compare server vs local note counts

---

## Architecture & Key Modules

### Authentication (`auth.py`)
- `AuthToken` dataclass holds token, expiry, user info
- Tokens cached at `~/.getnotes-cli/auth.json`
- Auto-refresh via CDP (Chrome DevTools Protocol) if token expired
- Bearer token used in all API request headers

### Cache (`cache.py`)
- Manifest-based: `cache_manifest.json` in each output folder tracks note metadata
- Incremental downloads — only fetches notes not in cache
- Cache can be rebuilt from disk if manifest missing

### Configuration (`config.py`)
- All API base URLs defined as constants (do not hardcode elsewhere)
- Key paths:
  - Config dir: `~/.getnotes-cli/`
  - Auth: `~/.getnotes-cli/auth.json`
  - Settings: `~/.getnotes-cli/config.json`
  - Chrome profile: `~/.getnotes-cli/chrome-profile/`
  - Default output: `~/Downloads/getnotes_export/`
- Defaults: `PAGE_SIZE=20`, `REQUEST_DELAY=0.5s`, `DEFAULT_LIMIT=100`

### Settings (`settings.py`)
- `UserSettings` class manages `~/.getnotes-cli/config.json`
- Hierarchy: CLI args > config file > defaults

### MCP Server (`mcp/`)
- Uses `fastmcp` library
- Transport: stdio (compatible with Claude Desktop)
- Logging goes to `stderr` only (not stdout) — critical for MCP stdio protocol
- Tools: `get_notes`, `get_recent_notes`, `read_note`, `get_notebooks`, `get_notebook_notes`

### Exporter (`exporter.py`)
- Converts Markdown to styled HTML or PDF
- PDF uses `reportlab` with CJK font support (Chinese character rendering)
- HTML output includes indexed navigation

---

## Code Conventions

### Naming
- `snake_case` for functions and variables
- `PascalCase` for classes (`AuthToken`, `NoteDownloader`, `CacheManager`)
- `UPPER_SNAKE_CASE` for constants in `config.py`

### Commit Messages
Follow semantic commit format:
```
feat: <description>
fix: <description>
chore: <description>
docs: <description>
```

### Error Handling
- Raise `RuntimeError` for authentication failures in core modules
- Use `typer.Exit(1)` for CLI-level failures with user-facing messages
- Use `try/except` with meaningful Rich-formatted error messages to the terminal

### Logging
- Always use `logging` module, never `print()` in core modules
- Root logger configured in `cli.py` at INFO level: `format="%(message)s"`, `stream=sys.stderr`
- This is mandatory for MCP server compatibility (stdout must be clean JSON)

### HTTP Requests
- Use `httpx` for new code (async-capable); `requests` exists in some older paths
- Always include `Authorization: Bearer <token>` header
- Set timeouts: 30–60 seconds
- API responses follow: `{"data": {...}}` or `{"data": {"list": [...], "total": N}}`

### File Encoding
- All files: UTF-8
- User-facing strings may be in Chinese; internal logic and variable names in English

---

## API Reference (config.py)

| Constant | URL |
|----------|-----|
| `NOTES_API_URL` | `https://get-notes.luojilab.com/voicenotes/web/notes` |
| `SEARCH_API_URL` | `https://get-notes.luojilab.com/voicenotes/web/notes/search` |
| `NOTEBOOKS_API_URL` | `https://knowledge-api.trytalks.com/v1/web/topic/mine/list` |
| `SUBSCRIBE_NOTEBOOKS_API_URL` | `https://knowledge-api.trytalks.com/v1/web/subscribe/topic/list` |
| `KNOWLEDGE_API_URL` | `https://knowledge-api.trytalks.com/v1/web/topic/resource/list/mix` |
| `ADD_TO_NOTEBOOK_API_URL` | `https://get-notes.luojilab.com/voicenotes/web/topics/import/notes` |
| `IMAGE_TOKEN_API_URL` | `https://get-notes.luojilab.com/voicenotes/web/token/image` |

Pagination uses `limit` + `since_id` (cursor-based) or `page` parameters depending on endpoint.

---

## Release Workflow

See `.agent/workflows/release.md` for the full release process. Summary:
1. Update version in `src/getnotes_cli/__init__.py` and `pyproject.toml`
2. Update `CHANGELOG.md`
3. Commit with `chore: release vX.Y.Z`
4. Tag and push; CI (`publish.yml`) publishes to PyPI

---

## Important Notes for AI Assistants

1. **Do not use `print()` in any module** — use `logging` or Rich console to stderr.
2. **MCP server stdout must remain clean** — any stdout pollution breaks the Claude Desktop integration.
3. **The README is in Chinese** — this is intentional for the target user base.
4. **Version is declared in two places**: `src/getnotes_cli/__init__.py` (`__version__`) and `pyproject.toml` (`version`). Keep them in sync.
5. **uv.lock must be committed** when dependencies change — run `uv lock` after updating `pyproject.toml`.
6. **Cache manifest format** — when modifying `cache.py`, preserve the existing manifest schema to avoid invalidating user caches.
7. **CDP (Chrome DevTools Protocol)** in `cdp.py` is used for automated browser login — treat it carefully as it interacts with a running Chrome instance.
8. **Chinese character support in PDFs** — `exporter.py` registers CJK fonts via reportlab; test PDF export when modifying this module.
9. **Test isolation** — tests use mocking; do not add tests that make real HTTP requests or write to `~/.getnotes-cli/`.
