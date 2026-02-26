"""CLI 入口 — 使用 typer + rich 构建命令行界面"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from getnotes_cli import __version__
from getnotes_cli.config import DEFAULT_LIMIT, DEFAULT_OUTPUT_DIR, PAGE_SIZE, REQUEST_DELAY
from getnotes_cli.settings import resolve_delay, resolve_output, resolve_page_size

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
    token: Optional[str] = typer.Option(
        None, "--token", "-t",
        help="手动输入 Bearer token（跳过浏览器登录）",
    ),
) -> None:
    """🔐 登录得到笔记 — 通过浏览器自动获取 token"""
    from getnotes_cli.auth import get_or_refresh_token, login_with_token

    if token:
        # 手动输入 token
        auth = login_with_token(token)
        console.print(f"\n[green]✓[/green] Token 已保存！")
        console.print(f"  Authorization: {auth.authorization[:50]}...")
        return

    # 自动浏览器登录
    console.print("[bold]🌐 启动浏览器登录...[/bold]")
    console.print("[dim]将打开 Chrome 并导航到得到笔记页面。[/dim]")
    console.print("[dim]请在浏览器中登录，登录后浏览笔记时 token 将自动捕获。[/dim]\n")

    try:
        auth = get_or_refresh_token(force_login=True)
        console.print(f"\n[green]✓[/green] 登录成功！")
        console.print(f"  Authorization: {auth.authorization[:50]}...")
        if auth.csrf_token:
            console.print(f"  CSRF Token: {auth.csrf_token[:20]}...")
        console.print(f"  Token 已缓存到: ~/.getnotes-cli/auth.json")
    except RuntimeError as e:
        console.print(f"\n[red]✗[/red] {e}")
        raise typer.Exit(1)


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
        None, "--token", "-t",
        help="直接传入 Bearer token（跳过缓存检查）",
    ),
) -> None:
    """📝 创建笔记 — 从本地文件与图片发布得到笔记"""
    from getnotes_cli.auth import get_or_refresh_token, login_with_token
    from getnotes_cli.creator import NoteCreator

    # 获取 token
    if token:
        auth = login_with_token(token)
    else:
        try:
            auth = get_or_refresh_token()
        except RuntimeError as e:
            console.print(f"\n[red]✗[/red] {e}")
            console.print("[dim]请先运行 `getnotes login` 登录。[/dim]")
            raise typer.Exit(1)

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
        None, "--token", "-t",
        help="直接传入 Bearer token（跳过缓存检查）",
    ),
) -> None:
    """📥 下载笔记 — 批量下载得到笔记并保存为 Markdown"""
    from getnotes_cli.auth import AuthToken, get_or_refresh_token, login_with_token
    from getnotes_cli.downloader import NoteDownloader

    # 获取 token
    if token:
        auth = login_with_token(token)
    else:
        try:
            auth = get_or_refresh_token()
        except RuntimeError as e:
            console.print(f"\n[red]✗[/red] {e}")
            console.print("[dim]请先运行 `getnotes login` 登录。[/dim]")
            raise typer.Exit(1)

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
    """获取认证 token 的通用逻辑"""
    from getnotes_cli.auth import AuthToken, get_or_refresh_token, login_with_token

    if token:
        return login_with_token(token)
    try:
        return get_or_refresh_token()
    except RuntimeError as e:
        console.print(f"\n[red]✗[/red] {e}")
        console.print("[dim]请先运行 `getnotes login` 登录。[/dim]")
        raise typer.Exit(1)


@notebook_app.command("list")
def notebook_list(
    token: Optional[str] = typer.Option(
        None, "--token", "-t",
        help="直接传入 Bearer token",
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
        None, "--token", "-t",
        help="直接传入 Bearer token",
    ),
) -> None:
    """📥 下载指定知识库的笔记"""
    from getnotes_cli.notebook import fetch_notebooks
    from getnotes_cli.notebook_downloader import NotebookDownloader

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

    downloader = NotebookDownloader(
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
        None, "--token", "-t",
        help="直接传入 Bearer token",
    ),
) -> None:
    """📥 下载所有知识库的笔记"""
    from getnotes_cli.notebook import fetch_notebooks
    from getnotes_cli.notebook_downloader import NotebookDownloader

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

    downloader = NotebookDownloader(
        token=auth,
        output_dir=Path(resolve_output(output, str(DEFAULT_OUTPUT_DIR))),
        delay=resolve_delay(delay, REQUEST_DELAY),
        force=force,
        save_json=save_json,
    )
    downloader.download_all(notebooks)


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
        None, "--token", "-t",
        help="直接传入 Bearer token",
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
        None, "--token", "-t",
        help="直接传入 Bearer token",
    ),
) -> None:
    """📥 下载指定订阅知识库的笔记"""
    from getnotes_cli.notebook import fetch_subscribed_notebooks
    from getnotes_cli.notebook_downloader import NotebookDownloader

    if not name and not nb_id:
        console.print("[red]✗[/red] 请指定 --name 或 --id")
        console.print("[dim]使用 `getnotes subscribe list` 查看已订阅知识库[/dim]")
        raise typer.Exit(1)

    auth = _get_auth(token)

    console.print("\n[bold]📬 正在获取订阅知识库列表...[/bold]")
    notebooks = fetch_subscribed_notebooks(auth)

    target = None
    if nb_id:
        target = next((nb for nb in notebooks if nb.get("id_alias") == nb_id), None)
        if not target:
            console.print(f"[red]✗[/red] 未找到 ID 为 '{nb_id}' 的订阅知识库")
            raise typer.Exit(1)
    elif name:
        matches = [nb for nb in notebooks if name.lower() in nb.get("name", "").lower()]
        if not matches:
            console.print(f"[red]✗[/red] 未找到名称包含 '{name}' 的订阅知识库")
            console.print("[dim]已订阅知识库:[/dim]")
            for nb in notebooks:
                console.print(f"  - {nb.get('name', '')} (by {nb.get('creator', '')})")
            raise typer.Exit(1)
        if len(matches) > 1:
            console.print(f"[yellow]⚠[/yellow] 找到 {len(matches)} 个匹配:")
            for nb in matches:
                console.print(f"  - {nb.get('name', '')} (ID: {nb.get('id_alias', '')})")
            console.print("[dim]请使用 --id 精确指定[/dim]")
            raise typer.Exit(1)
        target = matches[0]

    console.print(f"[green]✓[/green] 目标订阅知识库: {target.get('name', '')} (by {target.get('creator', '')})")

    downloader = NotebookDownloader(
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
        None, "--token", "-t",
        help="直接传入 Bearer token",
    ),
) -> None:
    """📥 下载所有订阅知识库的笔记"""
    from getnotes_cli.notebook import fetch_subscribed_notebooks
    from getnotes_cli.notebook_downloader import NotebookDownloader

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

    downloader = NotebookDownloader(
        token=auth,
        output_dir=Path(resolve_output(output, str(DEFAULT_OUTPUT_DIR))),
        delay=resolve_delay(delay, REQUEST_DELAY),
        force=force,
        save_json=save_json,
    )
    downloader.download_all(notebooks)


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


def main():
    """CLI 主入口"""
    app()


if __name__ == "__main__":
    main()
