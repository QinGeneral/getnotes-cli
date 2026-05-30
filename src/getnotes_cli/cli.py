"""CLI 入口 — 使用 typer + rich 构建命令行界面"""

import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from getnotes_cli import __version__
from getnotes_cli.config import DEFAULT_LIMIT, DEFAULT_OUTPUT_DIR, PAGE_SIZE, REQUEST_DELAY
from getnotes_cli.settings import resolve_delay, resolve_output, resolve_page_size

# Configure logging to stderr so CLI users see progress from downloader modules
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    stream=sys.stderr,
)

console = Console()
app = typer.Typer(
    name="getnotes",
    help="🗂️ GetNotes CLI — 得到笔记批量下载工具",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# ========================================================================
# login 命令
# ========================================================================


@app.command()
def login(
    api_key: Optional[str] = typer.Option(
        None, "--api-key", "-k",
        help="Get 笔记 OpenAPI API Key（gk_live_xxx）",
    ),
    client_id: Optional[str] = typer.Option(
        None, "--client-id", "-c",
        help="Get 笔记 OpenAPI Client ID（cli_xxx）",
    ),
    legacy_token: Optional[str] = typer.Option(
        None, "--legacy-token",
        help="保存 legacy Bearer token，仅用于 download-tree 等 legacy-only 命令",
    ),
) -> None:
    """🔐 配置 Get 笔记 OpenAPI 凭证"""
    from getnotes_cli.auth import login_with_api_key, login_with_token

    if legacy_token:
        auth = login_with_token(legacy_token)
        console.print("\n[green]✓[/green] Legacy token 已保存！")
        console.print(f"  Authorization: {auth.authorization[:50]}...")
        console.print("  仅用于 `download-tree` 等官方 OpenAPI 未覆盖的能力。")
        return

    if not api_key:
        api_key = typer.prompt("OpenAPI API Key")
    if not client_id:
        client_id = typer.prompt("OpenAPI Client ID")

    auth = login_with_api_key(api_key, client_id)
    console.print("\n[green]✓[/green] OpenAPI 凭证已保存！")
    console.print(f"  API Key: {auth.api_key[:12]}...")
    console.print(f"  Client ID: {auth.client_id}")
    console.print("  凭证已缓存到: ~/.getnotes-cli/auth.json")


# ========================================================================
# create 命令
# ========================================================================


@app.command()
def create(
    file: Path = typer.Option(
        ..., "--file", "-f",
        exists=True, dir_okay=False, readable=True, resolve_path=True,
        help="要创建为得到笔记的 Markdown 文件或文本文件",
    ),
    images: Optional[list[Path]] = typer.Option(
        None, "--image", "-i",
        exists=True, dir_okay=False, readable=True, resolve_path=True,
        help="要上传并插入的图片文件（可多次指定），将追加到文本末尾",
    ),
    token: Optional[str] = typer.Option(
        None, "--api-key", "--token", "-t",
        help="直接传入 OpenAPI API Key（Client ID 仍从配置或环境读取）",
    ),
) -> None:
    """📝 创建笔记 — 从本地文件与图片发布得到笔记"""
    from getnotes_cli.creator import NoteCreator

    auth = _get_auth(token)

    text = file.read_text(encoding="utf-8")
    creator = NoteCreator(auth)

    console.print(f"[bold]📝 正在创建笔记: {file.name}[/bold]")
    if images:
        console.print(f"[dim]包含 {len(images)} 张图片待上传...[/dim]")

    try:
        data = creator.create_note(text, images)
        console.print(f"\n[green]✓[/green] 创建笔记成功！")
        console.print(f"  ID: {data.get('note_id', '')}")
        console.print(f"  时间: {data.get('created_at', '')}")
    except Exception as e:
        console.print(f"\n[red]✗[/red] 创建失败: {e}")
        raise typer.Exit(1)


@app.command("create-link")
def create_link(
    url: str = typer.Argument(
        ...,
        help="要生成笔记的链接地址"
    ),
    token: Optional[str] = typer.Option(
        None, "--api-key", "--token", "-t",
        help="直接传入 OpenAPI API Key（Client ID 仍从配置或环境读取）",
    ),
) -> None:
    """🔗 通过链接创建笔记 — 使用 AI 分析链接内容并生成深度笔记"""
    from getnotes_cli.creator import NoteCreator

    auth = _get_auth(token)

    creator = NoteCreator(auth)

    console.print(f"[bold]🔗 正在通过链接生成笔记...[/bold]")
    console.print(f"[dim]链接: {url}[/dim]\n")

    try:
        data = creator.create_note_from_link(url)
        note_id = data.get("note_id")
        console.print(f"\n[green]✓[/green] 笔记创建成功！")
        if note_id:
            console.print(f"  ID: {note_id}")
        elif data.get("tasks"):
            console.print(f"  任务: {data['tasks'][0].get('task_id', '')}")
    except Exception as e:
        console.print(f"\n[red]✗[/red] 创建失败: {e}")
        raise typer.Exit(1)


# ========================================================================
# search 命令
# ========================================================================


@app.command()
def search(
    query: str = typer.Argument(
        ...,
        help="搜索关键词",
    ),
    page: int = typer.Option(
        1, "--page", "-p",
        help="页码（从 1 开始）",
    ),
    page_size: int = typer.Option(
        10, "--page-size", "-s",
        help="每页数量（默认 10）",
    ),
    token: Optional[str] = typer.Option(
        None, "--api-key", "--token", "-t",
        help="直接传入 OpenAPI API Key",
    ),
) -> None:
    """🔍 搜索笔记 — 根据关键词搜索相关笔记"""
    from getnotes_cli.searcher import NoteSearcher

    auth = _get_auth(token)

    console.print(f"\n[bold]🔍 正在搜索: {query}[/bold]\n")

    try:
        searcher = NoteSearcher(auth)
        result = searcher.search(query, page=page, page_size=page_size)
    except Exception as e:
        console.print(f"[red]✗[/red] 搜索失败: {e}")
        raise typer.Exit(1)

    items = result["items"]
    total = result["total"]
    has_more = result["has_more"]

    if not items:
        console.print("[dim]未找到相关笔记。[/dim]")
        return

    table = Table(title=f"搜索结果 — '{query}' （共 {total} 条，第 {page} 页）")
    table.add_column("#", style="dim", width=4)
    table.add_column("标题 / 摘要", style="cyan", max_width=50)
    table.add_column("类型", style="yellow", width=8)
    table.add_column("标签", style="green", max_width=20)
    table.add_column("创建时间", style="dim", width=12)

    for i, item in enumerate(items, (page - 1) * page_size + 1):
        title = NoteSearcher.strip_highlight(item.get("title", "").strip())
        note_type = item.get("note_type", "")

        # 获取高亮摘要
        highlight = item.get("highlight_info", {})
        snippet = ""
        for key in ("title", "content", "ref_content"):
            parts = highlight.get(key, [])
            text = next((p for p in parts if p.strip()), "")
            if text:
                snippet = NoteSearcher.extract_highlight(text)
                break

        display = title if title else (snippet[:40] + "..." if len(snippet) > 40 else snippet)
        if not display:
            display = f"(ID: {item.get('note_id', '?')[-8:]})"

        tags = ", ".join(
            NoteSearcher.strip_highlight(t.get("name", "")) for t in item.get("tags", [])
            if t.get("type") != "system"
        )
        if len(tags) > 20:
            tags = tags[:18] + "…"

        created = item.get("created_at", "")[:10]

        table.add_row(str(i), display, note_type, tags, created)

    console.print(table)

    if has_more:
        next_page = page + 1
        console.print(f"\n[dim]还有更多结果，使用 `getnotes search \"{query}\" --page {next_page}` 查看下一页[/dim]")
    console.print(f"[dim]共 {total} 条匹配结果[/dim]")



# ========================================================================
# download 命令
# ========================================================================


@app.command()
def download(
    all_notes: bool = typer.Option(
        False, "--all",
        help="下载全部笔记",
    ),
    limit: int = typer.Option(
        DEFAULT_LIMIT, "--limit", "-l",
        help=f"下载笔记数量限制（默认 {DEFAULT_LIMIT}，--all 时忽略）",
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o",
        help="输出目录（可通过 config set 持久化）",
    ),
    delay: Optional[float] = typer.Option(
        None, "--delay", "-d",
        help="请求间隔秒数（可通过 config set 持久化）",
    ),
    page_size: Optional[int] = typer.Option(
        None, "--page-size",
        help="每页拉取数量（可通过 config set 持久化）",
    ),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="强制重新下载，忽略缓存",
    ),
    save_json: bool = typer.Option(
        False, "--save-json", "-j",
        help="保存原始 JSON 数据等技术文件（默认仅保存 Markdown 和附件）",
    ),
    token: Optional[str] = typer.Option(
        None, "--api-key", "--token", "-t",
        help="直接传入 OpenAPI API Key（Client ID 仍从配置或环境读取）",
    ),
) -> None:
    """📥 下载笔记 — 批量下载得到笔记并保存为 Markdown"""
    from getnotes_cli.downloader import NoteDownloader

    auth = _get_auth(token)

    max_notes = None if all_notes else limit
    output_dir = Path(resolve_output(output, str(DEFAULT_OUTPUT_DIR)))
    final_delay = resolve_delay(delay, REQUEST_DELAY)
    final_page_size = resolve_page_size(page_size, PAGE_SIZE)

    downloader = NoteDownloader(
        token=auth,
        output_dir=output_dir,
        limit=max_notes,
        page_size=final_page_size,
        delay=final_delay,
        force=force,
        save_json=save_json,
    )
    downloader.run()


# ========================================================================
# cache 命令组
# ========================================================================

cache_app = typer.Typer(
    help="💾 缓存管理",
    no_args_is_help=True,
)


@cache_app.command("check")
def cache_check() -> None:
    """📊 查看缓存状态"""
    from getnotes_cli.cache import CacheManager

    cm = CacheManager(Path(resolve_output(None, str(DEFAULT_OUTPUT_DIR))))
    info = cm.check()

    if not info["exists"]:
        console.print("[dim]暂无缓存数据。[/dim]")
        console.print(f"缓存路径: {info['path']}")
        return

    console.print(f"[bold]💾 缓存统计[/bold]")
    console.print(f"  📁 路径: {info['path']}")
    console.print(f"  📝 已缓存笔记: [cyan]{info['count']}[/cyan] 条\n")

    if info["count"] > 0 and info["count"] <= 20:
        table = Table(title="缓存条目")
        table.add_column("标题", style="cyan", max_width=50)
        table.add_column("创建时间", style="dim")
        for nid, note in info["notes"].items():
            table.add_row(note["title"], note["created_at"])
        console.print(table)


@cache_app.command("clear")
def cache_clear(
    confirm: bool = typer.Option(
        False, "--confirm", "-y",
        help="跳过确认提示",
    ),
) -> None:
    """🗑️ 清除缓存"""
    from getnotes_cli.cache import CacheManager

    cm = CacheManager(Path(resolve_output(None, str(DEFAULT_OUTPUT_DIR))))
    info = cm.check()

    if not info["exists"]:
        console.print("[dim]暂无缓存数据。[/dim]")
        return

    if not confirm:
        typer.confirm(f"确认清除 {info['count']} 条缓存记录？", abort=True)

    count = cm.clear()
    console.print(f"[green]✓[/green] 已清除 {count} 条缓存记录。")


app.add_typer(cache_app, name="cache")


# ========================================================================
# notebook 命令组
# ========================================================================

notebook_app = typer.Typer(
    help="📚 知识库管理 — 查看与下载知识库笔记",
    no_args_is_help=True,
)


def _get_auth(token: str | None) -> "AuthToken":
    """获取官方 OpenAPI 凭证的通用逻辑"""
    from getnotes_cli.auth import AuthToken, get_or_refresh_token, login_with_api_key, load_cached_token

    if token:
        cached = load_cached_token()
        if not cached or not cached.is_openapi:
            try:
                cached = get_or_refresh_token()
            except RuntimeError as e:
                console.print(f"\n[red]✗[/red] {e}")
                console.print("[dim]直接传 API Key 时仍需要已配置 Client ID 或设置 GETNOTE_CLIENT_ID。[/dim]")
                raise typer.Exit(1)
        return AuthToken(api_key=token, client_id=cached.client_id)
    try:
        return get_or_refresh_token()
    except RuntimeError as e:
        console.print(f"\n[red]✗[/red] {e}")
        console.print("[dim]请先运行 `getnotes login --api-key <key> --client-id <id>`。[/dim]")
        raise typer.Exit(1)


def _get_legacy_auth() -> "AuthToken":
    """获取 legacy-only 命令需要的 Bearer token。"""
    from getnotes_cli.auth import get_or_refresh_legacy_token

    try:
        return get_or_refresh_legacy_token()
    except RuntimeError as e:
        console.print(f"\n[red]✗[/red] {e}")
        console.print("[dim]可运行 `getnotes login --legacy-token <Bearer token>`，或让命令自动打开浏览器捕获 token。[/dim]")
        raise typer.Exit(1)


def _match_notebook(
    notebooks: list[dict],
    *,
    name: str | None,
    nb_id: str | None,
    label: str,
) -> dict:
    """按 ID 或名称匹配知识库，失败时直接退出 CLI。"""
    if nb_id:
        target = next(
            (
                nb for nb in notebooks
                if str(nb.get("id_alias") or nb.get("topic_id") or nb.get("id")) == nb_id
            ),
            None,
        )
        if not target:
            console.print(f"[red]✗[/red] 未找到 ID 为 '{nb_id}' 的{label}")
            raise typer.Exit(1)
        return target

    matches = [nb for nb in notebooks if name and name.lower() in nb.get("name", "").lower()]
    if not matches:
        console.print(f"[red]✗[/red] 未找到名称包含 '{name}' 的{label}")
        raise typer.Exit(1)
    if len(matches) > 1:
        console.print(f"[yellow]⚠[/yellow] 找到 {len(matches)} 个匹配:")
        for nb in matches:
            console.print(f"  - {nb.get('name', '')} (ID: {nb.get('id_alias', nb.get('topic_id', ''))})")
        console.print("[dim]请使用 --id 精确指定[/dim]")
        raise typer.Exit(1)
    return matches[0]


@notebook_app.command("list")
def notebook_list(
    token: Optional[str] = typer.Option(
        None, "--api-key", "--token", "-t",
        help="直接传入 OpenAPI API Key",
    ),
) -> None:
    """📋 列出所有知识库"""
    from getnotes_cli.notebook import fetch_notebooks

    auth = _get_auth(token)
    console.print("\n[bold]📚 正在获取知识库列表...[/bold]\n")

    try:
        notebooks = fetch_notebooks(auth)
    except Exception as e:
        console.print(f"[red]✗[/red] 获取失败: {e}")
        raise typer.Exit(1)

    if not notebooks:
        console.print("[dim]暂无知识库。[/dim]")
        return

    table = Table(title=f"我的知识库 （共 {len(notebooks)} 个）")
    table.add_column("#", style="dim", width=4)
    table.add_column("知识库名称", style="cyan", max_width=30)
    table.add_column("内容数", justify="right", style="green")
    table.add_column("更新时间", style="dim")
    table.add_column("ID", style="dim", max_width=12)

    for i, nb in enumerate(notebooks, 1):
        name = nb.get("name", "(未命名)")
        count = nb.get("extend_data", {}).get("all_resource_count", 0)
        update_desc = nb.get("last_update_time_desc", "")
        id_alias = nb.get("id_alias", "")
        table.add_row(str(i), name, str(count), update_desc, id_alias)

    console.print(table)
    console.print("\n[dim]使用 `getnotes notebook download --name <名称>` 下载指定知识库[/dim]")
    console.print("[dim]使用 `getnotes notebook download-all` 下载全部知识库[/dim]")


@notebook_app.command("download")
def notebook_download(
    name: Optional[str] = typer.Option(
        None, "--name", "-n",
        help="知识库名称（模糊匹配）",
    ),
    nb_id: Optional[str] = typer.Option(
        None, "--id",
        help="知识库 ID (id_alias)",
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o",
        help="输出目录（可通过 config set 持久化）",
    ),
    delay: Optional[float] = typer.Option(
        None, "--delay", "-d",
        help="请求间隔秒数（可通过 config set 持久化）",
    ),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="强制重新下载，忽略已有文件",
    ),
    save_json: bool = typer.Option(
        False, "--save-json", "-j",
        help="保存原始 JSON 数据等技术文件（默认仅保存 Markdown 和附件）",
    ),
    token: Optional[str] = typer.Option(
        None, "--api-key", "--token", "-t",
        help="直接传入 OpenAPI API Key",
    ),
) -> None:
    """📥 下载指定知识库的笔记"""
    from getnotes_cli.notebook import fetch_notebooks
    from getnotes_cli.openapi_notebook_downloader import OpenAPINotebookDownloader

    if not name and not nb_id:
        console.print("[red]✗[/red] 请指定 --name 或 --id")
        console.print("[dim]使用 `getnotes notebook list` 查看可用知识库[/dim]")
        raise typer.Exit(1)

    auth = _get_auth(token)

    # 获取知识库列表并匹配
    console.print("\n[bold]📚 正在获取知识库列表...[/bold]")
    notebooks = fetch_notebooks(auth)

    target = None
    if nb_id:
        target = next((nb for nb in notebooks if nb.get("id_alias") == nb_id), None)
        if not target:
            console.print(f"[red]✗[/red] 未找到 ID 为 '{nb_id}' 的知识库")
            raise typer.Exit(1)
    elif name:
        # 模糊匹配
        matches = [nb for nb in notebooks if name.lower() in nb.get("name", "").lower()]
        if not matches:
            console.print(f"[red]✗[/red] 未找到名称包含 '{name}' 的知识库")
            console.print("[dim]可用知识库:[/dim]")
            for nb in notebooks:
                console.print(f"  - {nb.get('name', '')}")
            raise typer.Exit(1)
        if len(matches) > 1:
            console.print(f"[yellow]⚠[/yellow] 找到 {len(matches)} 个匹配:")
            for nb in matches:
                console.print(f"  - {nb.get('name', '')} (ID: {nb.get('id_alias', '')})")
            console.print("[dim]请使用 --id 精确指定[/dim]")
            raise typer.Exit(1)
        target = matches[0]

    console.print(f"[green]✓[/green] 目标知识库: {target.get('name', '')}")

    downloader = OpenAPINotebookDownloader(
        token=auth,
        output_dir=Path(resolve_output(output, str(DEFAULT_OUTPUT_DIR))),
        delay=resolve_delay(delay, REQUEST_DELAY),
        force=force,
        save_json=save_json,
    )
    downloader.download_notebook(target)


@notebook_app.command("download-all")
def notebook_download_all(
    output: Optional[str] = typer.Option(
        None, "--output", "-o",
        help="输出目录（可通过 config set 持久化）",
    ),
    delay: Optional[float] = typer.Option(
        None, "--delay", "-d",
        help="请求间隔秒数（可通过 config set 持久化）",
    ),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="强制重新下载",
    ),
    save_json: bool = typer.Option(
        False, "--save-json", "-j",
        help="保存原始 JSON 数据等技术文件（默认仅保存 Markdown 和附件）",
    ),
    token: Optional[str] = typer.Option(
        None, "--api-key", "--token", "-t",
        help="直接传入 OpenAPI API Key",
    ),
) -> None:
    """📥 下载所有知识库的笔记"""
    from getnotes_cli.notebook import fetch_notebooks
    from getnotes_cli.openapi_notebook_downloader import OpenAPINotebookDownloader

    auth = _get_auth(token)

    console.print("\n[bold]📚 正在获取知识库列表...[/bold]")
    notebooks = fetch_notebooks(auth)

    if not notebooks:
        console.print("[dim]暂无知识库。[/dim]")
        return

    console.print(f"[green]✓[/green] 共找到 {len(notebooks)} 个知识库:\n")
    for i, nb in enumerate(notebooks, 1):
        name = nb.get("name", "(未命名)")
        count = nb.get("extend_data", {}).get("all_resource_count", 0)
        console.print(f"  {i}. {name} ({count} 个内容)")

    if not typer.confirm(f"\n确认下载全部 {len(notebooks)} 个知识库？"):
        raise typer.Exit()

    downloader = OpenAPINotebookDownloader(
        token=auth,
        output_dir=Path(resolve_output(output, str(DEFAULT_OUTPUT_DIR))),
        delay=resolve_delay(delay, REQUEST_DELAY),
        force=force,
        save_json=save_json,
    )
    downloader.download_all(notebooks)



@notebook_app.command("add-note")
def notebook_add_note(
    note_id: str = typer.Option(
        ..., "--note-id", "-n",
        help="要加入知识库的笔记 ID",
    ),
    name: Optional[str] = typer.Option(
        None, "--name",
        help="知识库名称（模糊匹配）",
    ),
    nb_id: Optional[str] = typer.Option(
        None, "--id",
        help="知识库 ID (id_alias)",
    ),
    token: Optional[str] = typer.Option(
        None, "--api-key", "--token", "-t",
        help="直接传入 OpenAPI API Key",
    ),
) -> None:
    """➕ 将笔记加入知识库"""
    from getnotes_cli.notebook import add_note_to_notebook, fetch_notebooks

    if not name and not nb_id:
        console.print("[red]✗[/red] 请指定 --name 或 --id")
        console.print("[dim]使用 `getnotes notebook list` 查看可用知识库[/dim]")
        raise typer.Exit(1)

    auth = _get_auth(token)

    console.print("\n[bold]📚 正在获取知识库列表...[/bold]")
    notebooks = fetch_notebooks(auth)

    target = None
    if nb_id:
        target = next((nb for nb in notebooks if nb.get("id_alias") == nb_id), None)
        if not target:
            console.print(f"[red]✗[/red] 未找到 ID 为 \'{nb_id}\' 的知识库")
            raise typer.Exit(1)
    elif name:
        matches = [nb for nb in notebooks if name.lower() in nb.get("name", "").lower()]
        if not matches:
            console.print(f"[red]✗[/red] 未找到名称包含 \'{name}\' 的知识库")
            raise typer.Exit(1)
        if len(matches) > 1:
            console.print(f"[yellow]⚠[/yellow] 找到 {len(matches)} 个匹配:")
            for nb in matches:
                nb_name_m = nb.get("name", "")
                nb_id_m = nb.get("id_alias", "")
                console.print(f"  - {nb_name_m} (ID: {nb_id_m})")
            console.print("[dim]请使用 --id 精确指定[/dim]")
            raise typer.Exit(1)
        target = matches[0]

    topic_id = target.get("topic_id") or target.get("id") or target.get("id_alias")
    if not topic_id:
        console.print("[red]✗[/red] 无法获取知识库 topic_id")
        raise typer.Exit(1)

    nb_name = target.get("name", "")
    console.print(f"[bold]➕ 正在将笔记加入知识库: {nb_name}[/bold]")

    try:
        add_note_to_notebook(auth, note_id, topic_id)
        console.print(f"\n[green]✓[/green] 笔记 `{note_id}` 已成功加入知识库 [{nb_name}]！")
    except Exception as e:
        console.print(f"\n[red]✗[/red] 操作失败: {e}")
        raise typer.Exit(1)


@notebook_app.command("remove-note")
def notebook_remove_note(
    note_id: str = typer.Option(
        ..., "--note-id", "-n",
        help="要移出知识库的笔记 ID",
    ),
    name: Optional[str] = typer.Option(
        None, "--name",
        help="知识库名称（模糊匹配）",
    ),
    nb_id: Optional[str] = typer.Option(
        None, "--id",
        help="知识库 ID",
    ),
    token: Optional[str] = typer.Option(
        None, "--api-key", "--token", "-t",
        help="直接传入 OpenAPI API Key",
    ),
) -> None:
    """➖ 将笔记从知识库移除"""
    from getnotes_cli.notebook import fetch_notebooks, remove_note_from_notebook

    if not name and not nb_id:
        console.print("[red]✗[/red] 请指定 --name 或 --id")
        raise typer.Exit(1)

    auth = _get_auth(token)
    notebooks = fetch_notebooks(auth)
    target = _match_notebook(notebooks, name=name, nb_id=nb_id, label="知识库")
    topic_id = target.get("topic_id") or target.get("id") or target.get("id_alias")
    if not topic_id:
        console.print("[red]✗[/red] 无法获取知识库 topic_id")
        raise typer.Exit(1)

    try:
        remove_note_from_notebook(auth, note_id, topic_id)
        console.print(f"[green]✓[/green] 笔记 `{note_id}` 已从知识库 [{target.get('name', '')}] 移除。")
    except Exception as e:
        console.print(f"\n[red]✗[/red] 操作失败: {e}")
        raise typer.Exit(1)


@notebook_app.command("create")
def notebook_create(
    name: str = typer.Argument(..., help="知识库名称"),
    description: str = typer.Option("", "--description", "-d", help="知识库描述"),
    token: Optional[str] = typer.Option(
        None, "--api-key", "--token", "-t",
        help="直接传入 OpenAPI API Key",
    ),
) -> None:
    """📚 创建知识库"""
    from getnotes_cli.notebook import create_notebook

    auth = _get_auth(token)
    try:
        notebook = create_notebook(auth, name, description)
    except Exception as e:
        console.print(f"\n[red]✗[/red] 创建失败: {e}")
        raise typer.Exit(1)
    console.print(f"[green]✓[/green] 已创建知识库: {notebook.get('name', name)}")
    if notebook.get("topic_id"):
        console.print(f"  ID: {notebook['topic_id']}")


@notebook_app.command("download-tree")
def notebook_download_tree(
    name: Optional[str] = typer.Option(
        None, "--name", "-n",
        help="知识库名称（模糊匹配）",
    ),
    nb_id: Optional[str] = typer.Option(
        None, "--id",
        help="知识库 ID (id_alias)",
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o",
        help="输出目录（可通过 config set 持久化）",
    ),
    delay: Optional[float] = typer.Option(
        None, "--delay", "-d",
        help="请求间隔秒数（可通过 config set 持久化）",
    ),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="强制重新下载，忽略已有文件",
    ),
    save_json: bool = typer.Option(
        False, "--save-json", "-j",
        help="保存原始 JSON 数据等技术文件",
    ),
) -> None:
    """🌲 Legacy 下载知识库目录树和文件资源"""
    from getnotes_cli.notebook import fetch_legacy_notebooks
    from getnotes_cli.notebook_downloader import NotebookDownloader

    if not name and not nb_id:
        console.print("[red]✗[/red] 请指定 --name 或 --id")
        raise typer.Exit(1)

    auth = _get_legacy_auth()
    notebooks = fetch_legacy_notebooks(auth)
    target = _match_notebook(notebooks, name=name, nb_id=nb_id, label="legacy 知识库")
    console.print(f"[green]✓[/green] 目标 legacy 知识库: {target.get('name', '')}")

    downloader = NotebookDownloader(
        token=auth,
        output_dir=Path(resolve_output(output, str(DEFAULT_OUTPUT_DIR))),
        delay=resolve_delay(delay, REQUEST_DELAY),
        force=force,
        save_json=save_json,
    )
    downloader.download_notebook(target)

app.add_typer(notebook_app, name="notebook")


# ========================================================================
# subscribe 命令组
# ========================================================================

subscribe_app = typer.Typer(
    help="📬 订阅知识库管理 — 查看与下载订阅的知识库笔记",
    no_args_is_help=True,
)


@subscribe_app.command("list")
def subscribe_list(
    token: Optional[str] = typer.Option(
        None, "--api-key", "--token", "-t",
        help="直接传入 OpenAPI API Key",
    ),
) -> None:
    """📋 列出所有已订阅的知识库"""
    from getnotes_cli.notebook import fetch_subscribed_notebooks

    auth = _get_auth(token)
    console.print("\n[bold]📬 正在获取订阅知识库列表...[/bold]\n")

    try:
        notebooks = fetch_subscribed_notebooks(auth)
    except Exception as e:
        console.print(f"[red]✗[/red] 获取失败: {e}")
        raise typer.Exit(1)

    if not notebooks:
        console.print("[dim]暂无订阅知识库。[/dim]")
        return

    table = Table(title=f"已订阅知识库 （共 {len(notebooks)} 个）")
    table.add_column("#", style="dim", width=4)
    table.add_column("知识库名称", style="cyan", max_width=30)
    table.add_column("创建者", style="yellow", max_width=12)
    table.add_column("内容数", justify="right", style="green")
    table.add_column("订阅数", justify="right", style="magenta")
    table.add_column("更新时间", style="dim")
    table.add_column("ID", style="dim", max_width=12)

    for i, nb in enumerate(notebooks, 1):
        name = nb.get("name", "(未命名)")
        creator = nb.get("creator", "")
        extend = nb.get("extend_data", {})
        count = extend.get("all_resource_count", 0)
        sub_count = extend.get("subscribe_count", 0)
        update_desc = nb.get("last_update_time_desc", "")
        id_alias = nb.get("id_alias", "")
        table.add_row(str(i), name, creator, str(count), str(sub_count), update_desc, id_alias)

    console.print(table)
    console.print("\n[dim]使用 `getnotes subscribe download --name <名称>` 下载指定订阅知识库[/dim]")
    console.print("[dim]使用 `getnotes subscribe download-all` 下载全部订阅知识库[/dim]")


@subscribe_app.command("download")
def subscribe_download(
    name: Optional[str] = typer.Option(
        None, "--name", "-n",
        help="知识库名称（模糊匹配）",
    ),
    nb_id: Optional[str] = typer.Option(
        None, "--id",
        help="知识库 ID (id_alias)",
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o",
        help="输出目录（可通过 config set 持久化）",
    ),
    delay: Optional[float] = typer.Option(
        None, "--delay", "-d",
        help="请求间隔秒数（可通过 config set 持久化）",
    ),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="强制重新下载，忽略已有文件",
    ),
    save_json: bool = typer.Option(
        False, "--save-json", "-j",
        help="保存原始 JSON 数据等技术文件（默认仅保存 Markdown 和附件）",
    ),
    token: Optional[str] = typer.Option(
        None, "--api-key", "--token", "-t",
        help="直接传入 OpenAPI API Key",
    ),
) -> None:
    """📥 下载指定订阅知识库的笔记"""
    from getnotes_cli.notebook import fetch_subscribed_notebooks
    from getnotes_cli.openapi_notebook_downloader import OpenAPINotebookDownloader

    if not name and not nb_id:
        console.print("[red]✗[/red] 请指定 --name 或 --id")
        console.print("[dim]使用 `getnotes subscribe list` 查看已订阅知识库[/dim]")
        raise typer.Exit(1)

    auth = _get_auth(token)

    console.print("\n[bold]📬 正在获取订阅知识库列表...[/bold]")
    notebooks = fetch_subscribed_notebooks(auth)

    target = _match_notebook(notebooks, name=name, nb_id=nb_id, label="订阅知识库")

    console.print(f"[green]✓[/green] 目标订阅知识库: {target.get('name', '')} (by {target.get('creator', '')})")

    downloader = OpenAPINotebookDownloader(
        token=auth,
        output_dir=Path(resolve_output(output, str(DEFAULT_OUTPUT_DIR))),
        delay=resolve_delay(delay, REQUEST_DELAY),
        force=force,
        save_json=save_json,
    )
    downloader.download_notebook(target)


@subscribe_app.command("download-all")
def subscribe_download_all(
    output: Optional[str] = typer.Option(
        None, "--output", "-o",
        help="输出目录（可通过 config set 持久化）",
    ),
    delay: Optional[float] = typer.Option(
        None, "--delay", "-d",
        help="请求间隔秒数（可通过 config set 持久化）",
    ),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="强制重新下载",
    ),
    save_json: bool = typer.Option(
        False, "--save-json", "-j",
        help="保存原始 JSON 数据等技术文件（默认仅保存 Markdown 和附件）",
    ),
    token: Optional[str] = typer.Option(
        None, "--api-key", "--token", "-t",
        help="直接传入 OpenAPI API Key",
    ),
) -> None:
    """📥 下载所有订阅知识库的笔记"""
    from getnotes_cli.notebook import fetch_subscribed_notebooks
    from getnotes_cli.openapi_notebook_downloader import OpenAPINotebookDownloader

    auth = _get_auth(token)

    console.print("\n[bold]📬 正在获取订阅知识库列表...[/bold]")
    notebooks = fetch_subscribed_notebooks(auth)

    if not notebooks:
        console.print("[dim]暂无订阅知识库。[/dim]")
        return

    console.print(f"[green]✓[/green] 共找到 {len(notebooks)} 个订阅知识库:\n")
    for i, nb in enumerate(notebooks, 1):
        name = nb.get("name", "(未命名)")
        creator = nb.get("creator", "")
        count = nb.get("extend_data", {}).get("all_resource_count", 0)
        console.print(f"  {i}. {name} by {creator} ({count} 个内容)")

    if not typer.confirm(f"\n确认下载全部 {len(notebooks)} 个订阅知识库？"):
        raise typer.Exit()

    downloader = OpenAPINotebookDownloader(
        token=auth,
        output_dir=Path(resolve_output(output, str(DEFAULT_OUTPUT_DIR))),
        delay=resolve_delay(delay, REQUEST_DELAY),
        force=force,
        save_json=save_json,
    )
    downloader.download_all(notebooks)


@subscribe_app.command("download-tree")
def subscribe_download_tree(
    name: Optional[str] = typer.Option(
        None, "--name", "-n",
        help="订阅知识库名称（模糊匹配）",
    ),
    nb_id: Optional[str] = typer.Option(
        None, "--id",
        help="订阅知识库 ID (id_alias)",
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o",
        help="输出目录（可通过 config set 持久化）",
    ),
    delay: Optional[float] = typer.Option(
        None, "--delay", "-d",
        help="请求间隔秒数（可通过 config set 持久化）",
    ),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="强制重新下载，忽略已有文件",
    ),
    save_json: bool = typer.Option(
        False, "--save-json", "-j",
        help="保存原始 JSON 数据等技术文件",
    ),
) -> None:
    """🌲 Legacy 下载订阅知识库目录树和文件资源"""
    from getnotes_cli.notebook import fetch_legacy_subscribed_notebooks
    from getnotes_cli.notebook_downloader import NotebookDownloader

    if not name and not nb_id:
        console.print("[red]✗[/red] 请指定 --name 或 --id")
        raise typer.Exit(1)

    auth = _get_legacy_auth()
    notebooks = fetch_legacy_subscribed_notebooks(auth)
    target = _match_notebook(notebooks, name=name, nb_id=nb_id, label="legacy 订阅知识库")
    console.print(f"[green]✓[/green] 目标 legacy 订阅知识库: {target.get('name', '')}")

    downloader = NotebookDownloader(
        token=auth,
        output_dir=Path(resolve_output(output, str(DEFAULT_OUTPUT_DIR))),
        delay=resolve_delay(delay, REQUEST_DELAY),
        force=force,
        save_json=save_json,
    )
    downloader.download_notebook(target)


app.add_typer(subscribe_app, name="subscribe")


# ========================================================================
# config 命令组
# ========================================================================

config_app = typer.Typer(
    help="⚙️ 配置管理 — 持久化 output、delay、page-size 等参数",
    no_args_is_help=True,
)


@config_app.command("set")
def config_set(
    key: str = typer.Argument(
        ...,
        help="配置项名称（output / delay / page-size）",
    ),
    value: str = typer.Argument(
        ...,
        help="配置值",
    ),
) -> None:
    """✏️ 设置配置项"""
    from getnotes_cli.settings import UserSettings

    settings = UserSettings()
    try:
        converted = settings.set(key, value)
        console.print(f"[green]✓[/green] 已保存: {key} = {converted}")
    except KeyError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(1)
    except ValueError:
        console.print(f"[red]✗[/red] 值 '{value}' 无法转换为 {key} 所需的类型")
        raise typer.Exit(1)


@config_app.command("get")
def config_get(
    key: Optional[str] = typer.Argument(
        None,
        help="配置项名称（留空显示全部）",
    ),
) -> None:
    """📋 查看配置"""
    from getnotes_cli.settings import UserSettings, CONFIG_FILE

    settings = UserSettings()

    if key:
        from getnotes_cli.settings import CLI_KEY_MAP
        canon_key = CLI_KEY_MAP.get(key, key)
        val = settings.get(canon_key)
        if val is None:
            console.print(f"[dim]{key} 未设置（使用默认值）[/dim]")
        else:
            console.print(f"{key} = [cyan]{val}[/cyan]")
        return

    all_cfg = settings.all()
    if not all_cfg:
        console.print("[dim]暂无自定义配置，所有参数使用默认值。[/dim]")
        console.print(f"[dim]配置文件路径: {CONFIG_FILE}[/dim]")
        return

    console.print("[bold]⚙️ 当前配置[/bold]\n")
    table = Table()
    table.add_column("配置项", style="cyan")
    table.add_column("值", style="green")
    for k, v in all_cfg.items():
        table.add_row(k, str(v))
    console.print(table)
    console.print(f"\n[dim]配置文件: {CONFIG_FILE}[/dim]")


@config_app.command("reset")
def config_reset(
    confirm: bool = typer.Option(
        False, "--confirm", "-y",
        help="跳过确认提示",
    ),
) -> None:
    """🗑️ 清除所有配置"""
    from getnotes_cli.settings import UserSettings

    settings = UserSettings()
    all_cfg = settings.all()

    if not all_cfg:
        console.print("[dim]暂无自定义配置。[/dim]")
        return

    if not confirm:
        console.print("当前配置:")
        for k, v in all_cfg.items():
            console.print(f"  {k} = {v}")
        typer.confirm("确认清除所有配置？", abort=True)

    count = settings.clear()
    console.print(f"[green]✓[/green] 已清除 {count} 项配置。")


app.add_typer(config_app, name="config")




@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-v",
        help="显示版本号",
    ),
) -> None:
    if version:
        console.print(f"getnotes-cli v{__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())

# ========================================================================
# export 命令
# ========================================================================

@app.command()
def export(
    output: Optional[str] = typer.Option(
        None, "--output", "-o",
        help="输出目录（默认在笔记根目录下的 html_export/ 或 pdf_export/）",
    ),
    source: Optional[str] = typer.Option(
        None, "--source", "-s",
        help=(
            "来源路径，支持三种形式：\n"
            "  1) 单个 .md 文件 → 只转换该文件\n"
            "  2) notes/ 目录 → 批量转换目录内所有笔记\n"
            "  3) 根导出目录（含 notes/ 子目录）→ 自动定位并批量转换\n"
            "  （默认使用配置的 output 根目录）"
        ),
    ),
    fmt: str = typer.Option(
        "html", "--format", "-F",
        help="导出格式：html（默认）或 pdf",
    ),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="强制重新转换，忽略已有输出文件",
    ),
) -> None:
    """🌐 导出笔记 — 将本地 Markdown 笔记批量转换为 HTML 或 PDF 格式"""
    fmt_lower = fmt.lower()
    if fmt_lower not in ("html", "pdf"):
        console.print(f"[red]✗[/red] 不支持的格式: {fmt}，请使用 html 或 pdf")
        raise typer.Exit(1)

    is_pdf = fmt_lower == "pdf"
    fmt_label = "PDF" if is_pdf else "HTML"
    default_subdir = "pdf_export" if is_pdf else "html_export"
    icon = "📄" if is_pdf else "🌐"

    if is_pdf:
        from getnotes_cli.exporter import convert_md_to_pdf, export_notes_to_pdf
    else:
        from getnotes_cli.exporter import convert_md_to_html, export_notes_to_html

    console.print(f"\n[bold]{icon} 正在导出 Markdown 笔记为 {fmt_label}...[/bold]")

    # ── 解析 source 路径 ──────────────────────────────────────────────────
    if source:
        source_path = Path(source).expanduser().resolve()
    else:
        source_path = Path(resolve_output(None, str(DEFAULT_OUTPUT_DIR))).resolve()

    # 情形 1：source 是单个 .md 文件
    if source_path.is_file() and source_path.suffix == ".md":
        if is_pdf:
            suffix = ".pdf"
            _convert = convert_md_to_pdf
        else:
            suffix = ".html"
            _convert = convert_md_to_html

        if output:
            out_file = Path(output).expanduser().resolve()
            if out_file.is_dir():
                out_file = out_file / source_path.with_suffix(suffix).name
        else:
            out_file = source_path.with_suffix(suffix)

        console.print(f"  源文件: {source_path}")
        console.print(f"  输出文件: {out_file}\n")

        try:
            _convert(source_path, out_file)
            console.print(f"[green]✓[/green] 已转换: {out_file.resolve()}")
        except ImportError as e:
            console.print(f"[red]✗[/red] 缺少依赖: {e}")
            console.print("[dim]请运行: pip install reportlab[/dim]")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]✗[/red] 转换失败: {e}")
            raise typer.Exit(1)
        return

    # 情形 2 & 3：source 是目录
    if not source_path.exists():
        console.print(f"[red]✗[/red] 路径不存在: {source_path}")
        raise typer.Exit(1)

    # 如果目录内直接包含 note.md（即本身就是 notes/ 层级），直接用
    # 否则尝试 source_path/notes/ 子目录
    notes_subdir = source_path / "notes"
    if notes_subdir.is_dir():
        notes_dir = notes_subdir
        default_out_root = source_path
    else:
        notes_dir = source_path
        default_out_root = source_path.parent

    if output:
        output_dir = Path(output).expanduser().resolve()
    else:
        output_dir = default_out_root / default_subdir

    console.print(f"  源目录: {notes_dir}")
    console.print(f"  输出目录: {output_dir}\n")

    if not notes_dir.exists():
        console.print(f"[red]✗[/red] 笔记目录不存在: {notes_dir}")
        console.print("[dim]请先运行 `getnotes download` 下载笔记，或用 -s 指定正确路径。[/dim]")
        raise typer.Exit(1)

    try:
        if is_pdf:
            stats = export_notes_to_pdf(notes_dir, output_dir, force=force)
        else:
            stats = export_notes_to_html(notes_dir, output_dir, force=force)
    except ImportError as e:
        console.print(f"[red]✗[/red] 缺少依赖: {e}")
        console.print("[dim]请运行: pip install reportlab[/dim]")
        raise typer.Exit(1)

    console.print(f"\n[bold]📊 导出完成[/bold]")
    console.print(f"  ✅ 已转换: [cyan]{stats['converted']}[/cyan] 篇")
    console.print(f"  ⏭  已跳过: [dim]{stats['skipped']}[/dim] 篇")
    if stats["errors"]:
        console.print(f"  ❌ 失败: [red]{stats['errors']}[/red] 篇")
    console.print(f"\n  📁 输出目录: {output_dir.resolve()}")
    if is_pdf:
        console.print(f"  📄 已在 {output_dir.resolve()} 生成 PDF 文件")
    elif (output_dir / "index.html").exists() or stats["converted"] > 0:
        console.print(f"  🔗 索引页: {output_dir.resolve() / 'index.html'}")


# ========================================================================
# sync-check 命令
# ========================================================================

@app.command("sync-check")
def sync_check(
    token: Optional[str] = typer.Option(
        None, "--api-key", "--token", "-t",
        help="直接传入 OpenAPI API Key",
    ),
) -> None:
    """🔄 同步检测 — 对比本地缓存与服务端，查看有多少新笔记待下载"""
    from getnotes_cli.cache import CacheManager
    from getnotes_cli.openapi_client import OpenAPIClient

    auth = _get_auth(token)

    console.print("\n[bold]🔄 正在检测同步状态...[/bold]\n")

    try:
        server_ids: set[str] = set()
        cursor = ""
        with OpenAPIClient(auth, min_interval=1.0) as client:
            while True:
                data = client.list_notes(cursor)
                for note in data.get("notes", []) or []:
                    note_id = str(note.get("note_id") or note.get("id") or "")
                    if note_id:
                        server_ids.add(note_id)
                if not data.get("has_more"):
                    break
                cursor = data.get("cursor", "")
                if not cursor:
                    break
    except Exception as e:
        console.print(f"[red]✗[/red] 无法获取服务端数据: {e}")
        raise typer.Exit(1)

    # 查询本地缓存数
    output_dir = Path(resolve_output(None, str(DEFAULT_OUTPUT_DIR)))
    cache = CacheManager(output_dir)
    cache_info = cache.check()
    local_count = cache_info["count"]
    cached_ids = set(cache_info.get("notes", {}).keys())
    missing_ids = server_ids - cached_ids

    console.print("[bold]📊 同步状态[/bold]\n")
    console.print(f"  ☁️  服务端笔记总数: [cyan]{len(server_ids)}[/cyan]")
    console.print(f"  💾 本地已缓存笔记: [cyan]{local_count}[/cyan]")

    if missing_ids:
        console.print(f"\n  [yellow]⚠️  有 {len(missing_ids)} 条新笔记待下载！[/yellow]")
        console.print("  [dim]运行 `getnotes download --all` 同步全部笔记[/dim]")
    elif local_count == len(server_ids):
        console.print("\n  [green]✓ 本地笔记已是最新，无需同步。[/green]")
    elif local_count > len(server_ids):
        console.print(f"\n  [dim]本地缓存比服务端多 {local_count - len(server_ids)} 条（可能有笔记已在服务端删除）[/dim]")



def main():
    """CLI 主入口"""
    app()


if __name__ == "__main__":
    main()
