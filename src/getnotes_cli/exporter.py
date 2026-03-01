"""导出模块 — 将本地 Markdown 笔记转换为 HTML 格式"""

import html
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------------
# Minimal Markdown → HTML 转换（处理笔记中实际使用的语法）
# -------------------------------------------------------------------------

def _md_to_html(md: str) -> str:
    """将 Markdown 文本转换为 HTML 片段（处理笔记常见语法）。"""
    lines = md.split("\n")
    output: list[str] = []
    in_table = False
    in_blockquote = False
    in_list = False
    i = 0

    def flush_table():
        nonlocal in_table
        if in_table:
            output.append("</tbody></table>")
            in_table = False

    def flush_blockquote():
        nonlocal in_blockquote
        if in_blockquote:
            output.append("</blockquote>")
            in_blockquote = False

    def flush_list():
        nonlocal in_list
        if in_list:
            output.append("</ul>")
            in_list = False

    def inline(text: str) -> str:
        """处理行内语法：bold, code, link, image"""
        # 图片 ![alt](src)
        text = re.sub(
            r"!\[([^\]]*)\]\(([^)]*)\)",
            lambda m: f'<img src="{m.group(2)}" alt="{html.escape(m.group(1))}" style="max-width:100%">',
            text,
        )
        # 链接 [text](url)
        text = re.sub(
            r"\[([^\]]*)\]\(([^)]*)\)",
            lambda m: f'<a href="{m.group(2)}">{html.escape(m.group(1))}</a>',
            text,
        )
        # 行内代码 `code`
        text = re.sub(r"`([^`]+)`", lambda m: f"<code>{html.escape(m.group(1))}</code>", text)
        # **bold**
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        # *italic*
        text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
        return text

    while i < len(lines):
        line = lines[i]

        # --- 空行 ---
        if not line.strip():
            flush_table()
            flush_blockquote()
            flush_list()
            output.append("")
            i += 1
            continue

        # --- 标题 ---
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            flush_table()
            flush_blockquote()
            flush_list()
            level = len(m.group(1))
            text = inline(html.escape(m.group(2)))
            output.append(f"<h{level}>{text}</h{level}>")
            i += 1
            continue

        # --- 分隔线 ---
        if re.match(r"^[-*_]{3,}$", line.strip()):
            flush_table()
            flush_blockquote()
            flush_list()
            output.append("<hr>")
            i += 1
            continue

        # --- 表格 ---
        if "|" in line:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            # 检测是否为分隔行（全是 --- 的行）
            if all(re.match(r"^:?-+:?$", c) for c in cells if c):
                # 分隔行：第一行是表头，当前行是分隔，切换为 tbody
                if not in_table:
                    # 上一行应该是表头，把 output[-1] 改为 thead
                    if output and output[-1].startswith("<tr>"):
                        header_row = output.pop()
                        output.append("<table><thead>" + header_row + "</thead><tbody>")
                        in_table = True
                i += 1
                continue
            else:
                row_html = "<tr>" + "".join(f"<td>{inline(html.escape(c))}</td>" for c in cells) + "</tr>"
                if not in_table:
                    output.append(row_html)
                else:
                    output.append(row_html)
                i += 1
                continue

        # --- 引用 ---
        if line.startswith(">"):
            flush_table()
            flush_list()
            text = inline(html.escape(line[1:].strip()))
            if not in_blockquote:
                output.append("<blockquote>")
                in_blockquote = True
            output.append(f"<p>{text}</p>")
            i += 1
            continue
        else:
            flush_blockquote()

        # --- 无序列表 ---
        m = re.match(r"^[-*]\s+(.*)", line)
        if m:
            flush_table()
            if not in_list:
                output.append("<ul>")
                in_list = True
            text = inline(html.escape(m.group(1)))
            output.append(f"<li>{text}</li>")
            i += 1
            continue
        else:
            flush_list()

        # --- 普通段落 ---
        flush_table()
        text = inline(html.escape(line))
        output.append(f"<p>{text}</p>")
        i += 1

    flush_table()
    flush_blockquote()
    flush_list()

    return "\n".join(output)


_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         max-width: 820px; margin: 40px auto; padding: 0 20px;
         color: #333; line-height: 1.7; }}
  h1 {{ font-size: 1.8em; border-bottom: 2px solid #eee; padding-bottom: .3em; }}
  h2 {{ font-size: 1.3em; color: #555; margin-top: 2em; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
  th, td {{ border: 1px solid #ddd; padding: 6px 12px; text-align: left; }}
  thead {{ background: #f5f5f5; }}
  blockquote {{ border-left: 4px solid #ddd; margin: 1em 0; padding: .5em 1em;
                color: #555; background: #fafafa; }}
  code {{ background: #f0f0f0; padding: 2px 5px; border-radius: 3px;
          font-family: "SFMono-Regular", Consolas, monospace; font-size: .9em; }}
  img {{ max-width: 100%; border-radius: 4px; }}
  a {{ color: #0366d6; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  ul {{ padding-left: 1.5em; }}
  hr {{ border: none; border-top: 1px solid #eee; margin: 2em 0; }}
  .meta {{ font-size: .85em; color: #888; margin-bottom: 2em; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def convert_md_to_html(md_path: Path, html_path: Path) -> None:
    """将单个 Markdown 笔记文件转换为 HTML 文件。

    Args:
        md_path: 源 Markdown 文件路径
        html_path: 目标 HTML 文件路径
    """
    content = md_path.read_text(encoding="utf-8")

    # 提取标题（第一行 # 标题）
    title = "笔记"
    for line in content.splitlines():
        m = re.match(r"^#\s+(.*)", line)
        if m:
            title = m.group(1).strip()
            break

    body = _md_to_html(content)
    html_content = _HTML_TEMPLATE.format(
        title=html.escape(title),
        body=body,
    )
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html_content, encoding="utf-8")


def export_notes_to_html(notes_dir: Path, output_dir: Path, force: bool = False) -> dict:
    """批量将 notes/ 目录下所有笔记导出为 HTML。

    Args:
        notes_dir: 笔记源目录（包含按文件夹组织的笔记）
        output_dir: HTML 输出根目录
        force: 是否覆盖已存在的 HTML 文件

    Returns:
        {"converted": int, "skipped": int, "errors": int}
    """
    stats = {"converted": 0, "skipped": 0, "errors": 0}

    if not notes_dir.exists():
        logger.warning("笔记目录不存在: %s", notes_dir)
        return stats

    output_dir.mkdir(parents=True, exist_ok=True)

    for folder in sorted(notes_dir.iterdir()):
        if not folder.is_dir():
            continue
        md_file = folder / "note.md"
        if not md_file.exists():
            continue

        html_file = output_dir / folder.name / "note.html"

        if html_file.exists() and not force:
            logger.info("  ⏭ 已存在: %s", folder.name)
            stats["skipped"] += 1
            continue

        try:
            convert_md_to_html(md_file, html_file)
            # 复制附件目录（如有）
            att_src = folder / "attachments"
            if att_src.exists():
                import shutil
                att_dst = output_dir / folder.name / "attachments"
                if att_dst.exists() and force:
                    shutil.rmtree(att_dst)
                if not att_dst.exists():
                    shutil.copytree(att_src, att_dst)

            logger.info("  ✅ 已转换: %s", folder.name[:60])
            stats["converted"] += 1
        except Exception as e:
            logger.error("  ❌ 转换失败: %s — %s", folder.name, e)
            stats["errors"] += 1

    # 生成 HTML 索引页
    _generate_html_index(output_dir, stats)
    return stats


def _generate_html_index(output_dir: Path, stats: dict) -> None:
    """在导出目录生成 HTML 索引页。"""
    from datetime import datetime

    items: list[tuple[str, str]] = []
    for folder in sorted(output_dir.iterdir()):
        if not folder.is_dir():
            continue
        html_file = folder / "note.html"
        if not html_file.exists():
            continue
        # 尝试提取标题
        try:
            content = html_file.read_text(encoding="utf-8")
            m = re.search(r"<title>(.*?)</title>", content)
            title = m.group(1) if m else folder.name
        except Exception:
            title = folder.name
        items.append((title, f"{folder.name}/note.html"))

    rows = "\n".join(
        f'<tr><td>{i}</td><td><a href="{path}">{html.escape(t)}</a></td></tr>'
        for i, (t, path) in enumerate(items, 1)
    )

    index_html = f"""\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Get笔记 HTML 导出</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif;
         max-width: 860px; margin: 40px auto; padding: 0 20px; color: #333; }}
  h1 {{ border-bottom: 2px solid #eee; padding-bottom: .3em; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ddd; padding: 8px 14px; text-align: left; }}
  thead {{ background: #f5f5f5; }}
  a {{ color: #0366d6; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .meta {{ color: #888; font-size: .9em; margin-bottom: 2em; }}
</style>
</head>
<body>
<h1>📚 Get笔记 HTML 导出</h1>
<p class="meta">导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp;
已转换: {stats['converted']} 篇 &nbsp;|&nbsp; 跳过: {stats['skipped']} 篇</p>
<table>
<thead><tr><th>#</th><th>笔记标题</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
</body>
</html>
"""
    (output_dir / "index.html").write_text(index_html, encoding="utf-8")
