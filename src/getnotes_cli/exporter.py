"""导出模块 — 将本地 Markdown 笔记转换为 HTML / PDF 格式"""

import html
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# =========================================================================
# Markdown → HTML
# =========================================================================

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
        text = re.sub(
            r"!\[([^\]]*)\]\(([^)]*)\)",
            lambda m: f'<img src="{m.group(2)}" alt="{html.escape(m.group(1))}" style="max-width:100%">',
            text,
        )
        text = re.sub(
            r"\[([^\]]*)\]\(([^)]*)\)",
            lambda m: f'<a href="{m.group(2)}">{html.escape(m.group(1))}</a>',
            text,
        )
        text = re.sub(r"`([^`]+)`", lambda m: f"<code>{html.escape(m.group(1))}</code>", text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
        return text

    while i < len(lines):
        line = lines[i]

        if not line.strip():
            flush_table(); flush_blockquote(); flush_list()
            output.append("")
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            flush_table(); flush_blockquote(); flush_list()
            level = len(m.group(1))
            text = inline(html.escape(m.group(2)))
            output.append(f"<h{level}>{text}</h{level}>")
            i += 1
            continue

        if re.match(r"^[-*_]{3,}$", line.strip()):
            flush_table(); flush_blockquote(); flush_list()
            output.append("<hr>")
            i += 1
            continue

        if "|" in line:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(re.match(r"^:?-+:?$", c) for c in cells if c):
                if not in_table:
                    if output and output[-1].startswith("<tr>"):
                        header_row = output.pop()
                        output.append("<table><thead>" + header_row + "</thead><tbody>")
                        in_table = True
                i += 1
                continue
            else:
                row_html = "<tr>" + "".join(f"<td>{inline(html.escape(c))}</td>" for c in cells) + "</tr>"
                output.append(row_html)
                i += 1
                continue

        if line.startswith(">"):
            flush_table(); flush_list()
            text = inline(html.escape(line[1:].strip()))
            if not in_blockquote:
                output.append("<blockquote>")
                in_blockquote = True
            output.append(f"<p>{text}</p>")
            i += 1
            continue
        else:
            flush_blockquote()

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

        flush_table()
        text = inline(html.escape(line))
        output.append(f"<p>{text}</p>")
        i += 1

    flush_table(); flush_blockquote(); flush_list()
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
    """将单个 Markdown 笔记文件转换为 HTML 文件。"""
    content = md_path.read_text(encoding="utf-8")
    title = "笔记"
    for line in content.splitlines():
        m = re.match(r"^#\s+(.*)", line)
        if m:
            title = m.group(1).strip()
            break
    body = _md_to_html(content)
    html_content = _HTML_TEMPLATE.format(title=html.escape(title), body=body)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html_content, encoding="utf-8")


def export_notes_to_html(notes_dir: Path, output_dir: Path, force: bool = False) -> dict:
    """批量将 notes/ 目录下所有笔记导出为 HTML。"""
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


# =========================================================================
# PDF Export（基于 reportlab）
# =========================================================================

# 已注册的 CJK 字体名称（模块级单例）
_PDF_FONT_NAME: str = "Helvetica"
_PDF_FONT_REGISTERED: bool = False


def _find_cjk_font_path() -> str | None:
    """在常见系统路径中查找支持中文的 TTF/TTC 字体。"""
    import platform
    system = platform.system()
    candidates: list[str] = []
    if system == "Darwin":
        candidates = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/Supplemental/Songti.ttc",
            "/Library/Fonts/Arial Unicode MS.ttf",
            "/System/Library/Fonts/STHeiti Light.ttc",
        ]
    elif system == "Linux":
        candidates = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansSC-Regular.otf",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc",
        ]
    elif system == "Windows":
        candidates = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simsun.ttc",
            "C:/Windows/Fonts/simhei.ttf",
        ]
    for path in candidates:
        if Path(path).exists():
            return path
    return None


def _ensure_pdf_font() -> str:
    """注册 CJK 字体并返回字体名。失败时回退到 Helvetica（中文可能无法显示）。"""
    global _PDF_FONT_NAME, _PDF_FONT_REGISTERED
    if _PDF_FONT_REGISTERED:
        return _PDF_FONT_NAME

    font_path = _find_cjk_font_path()
    if font_path:
        try:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            alias = "GetNotesCJK"
            kwargs: dict = {"subfontIndex": 0} if font_path.endswith(".ttc") else {}
            pdfmetrics.registerFont(TTFont(alias, font_path, **kwargs))
            _PDF_FONT_NAME = alias
            _PDF_FONT_REGISTERED = True
            logger.debug("已注册中文字体: %s → %s", alias, font_path)
            return alias
        except Exception as exc:
            logger.warning("注册中文字体失败（%s），中文可能无法在 PDF 中显示: %s", font_path, exc)
    else:
        logger.warning("未找到系统中文字体，PDF 中文字符可能无法正常显示")

    _PDF_FONT_REGISTERED = True   # 避免重复尝试
    return "Helvetica"


def _make_pdf_styles(font: str) -> dict:
    """根据字体名创建 reportlab 段落样式表。"""
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle

    def s(name: str, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, fontName=font, **kw)

    return {
        "h1": s("GN_H1", fontSize=20, leading=28, spaceBefore=16, spaceAfter=10,
                textColor=colors.HexColor("#111111")),
        "h2": s("GN_H2", fontSize=15, leading=22, spaceBefore=14, spaceAfter=7,
                textColor=colors.HexColor("#333333")),
        "h3": s("GN_H3", fontSize=12, leading=17, spaceBefore=10, spaceAfter=5,
                textColor=colors.HexColor("#444444")),
        "h4": s("GN_H4", fontSize=11, leading=16, spaceBefore=8, spaceAfter=4,
                textColor=colors.HexColor("#555555")),
        "body": s("GN_Body", fontSize=10.5, leading=16, spaceAfter=5),
        "quote": s("GN_Quote", fontSize=10, leading=15, leftIndent=16,
                   spaceAfter=6, textColor=colors.HexColor("#555555")),
        "list": s("GN_List", fontSize=10.5, leading=16, leftIndent=18,
                  spaceAfter=3, bulletIndent=8),
        "code": ParagraphStyle("GN_Code", fontName=font, fontSize=8.5,
                                leading=14, leftIndent=12, spaceAfter=5,
                                backColor=colors.HexColor("#f4f4f4"),
                                textColor=colors.HexColor("#d73a49")),
        "table_cell": s("GN_TC", fontSize=9.5, leading=14),
        "table_head": s("GN_TH", fontSize=9.5, leading=14,
                        textColor=colors.HexColor("#333333")),
    }


def _pdf_inline(raw: str, font: str) -> str:
    """将 Markdown 行内语法转换为 reportlab Paragraph XML 标记。

    顺序：先转义 XML 特殊字符，再匹配 Markdown 语法（不含 < > &）。
    """
    import xml.sax.saxutils as sax

    text = sax.escape(raw)   # & → &amp;  < → &lt;  > → &gt;

    # 图片（内联）→ 跳过（独立行图片在 _build_story 中单独处理）
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "[图片]", text)

    # 链接 [text](url)
    text = re.sub(
        r"\[([^\]]*)\]\(([^)]*)\)",
        r'<font color="#0366d6">\1</font>',
        text,
    )

    # 行内代码 `code` (去除Courier以支持中文)
    text = re.sub(
        r"`([^`]+)`",
        r'<font backColor="#f0f0f0"> \1 </font>',
        text,
    )

    # **bold** (使用颜色替代黑框危险的 <b>)
    text = re.sub(r"\*\*(.+?)\*\*", r'<font color="#b30000">\1</font>', text)

    # *italic* (使用颜色替代 <i>)
    text = re.sub(r"\*(.+?)\*", r'<font color="#555555">\1</font>', text)

    return text


def _build_story(content: str, note_dir: Path, styles: dict, font: str) -> list:
    """将 Markdown 文本解析为 reportlab Platypus flowable 列表。"""
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        HRFlowable,
        Image as RLImage,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )

    story: list = []
    lines = content.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # ── 空行 ──────────────────────────────────────────────────────────
        if not stripped:
            story.append(Spacer(1, 5))
            i += 1
            continue

        # ── 标题 ──────────────────────────────────────────────────────────
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            level = min(len(m.group(1)), 4)
            text = _pdf_inline(m.group(2), font)
            story.append(Paragraph(text, styles[f"h{level}"]))
            i += 1
            continue

        # ── 分隔线 ────────────────────────────────────────────────────────
        if re.match(r"^[-*_]{3,}$", stripped):
            story.append(HRFlowable(width="100%", thickness=0.5,
                                    color=colors.HexColor("#dddddd"),
                                    spaceAfter=6, spaceBefore=6))
            i += 1
            continue

        # ── 表格（连续多行含 |） ───────────────────────────────────────────
        if "|" in line and stripped.startswith("|"):
            table_lines: list[str] = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            flowable = _build_pdf_table(table_lines, styles, font)
            if flowable:
                story.append(flowable)
                story.append(Spacer(1, 6))
            continue

        # ── 引用块（连续 > 行） ────────────────────────────────────────────
        if line.startswith(">"):
            quote_parts: list[str] = []
            while i < len(lines) and lines[i].startswith(">"):
                quote_parts.append(lines[i][1:].strip())
                i += 1
            text = _pdf_inline(" ".join(quote_parts), font)
            # 用带左边框的 Table 模拟 blockquote
            inner = Paragraph(text, styles["quote"])
            tbl = Table([[inner]], colWidths=["100%"])
            tbl.setStyle(TableStyle([
                ("LEFTPADDING",  (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING",   (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
                ("LINEBEFORE",   (0, 0), (0, -1), 3, colors.HexColor("#cccccc")),
                ("BACKGROUND",   (0, 0), (-1, -1), colors.HexColor("#f9f9f9")),
            ]))
            story.append(tbl)
            story.append(Spacer(1, 4))
            continue

        # ── 独立图片行 ![alt](path) ────────────────────────────────────────
        m_img = re.match(r"^!\[([^\]]*)\]\(([^)]*)\)$", stripped)
        if m_img:
            img_rel = m_img.group(2)
            img_path = (note_dir / img_rel).resolve()
            if img_path.exists():
                try:
                    max_w = 14 * cm
                    img_obj = RLImage(str(img_path))
                    if img_obj.drawWidth > max_w:
                        ratio = img_obj.drawHeight / img_obj.drawWidth
                        img_obj.drawWidth = max_w
                        img_obj.drawHeight = max_w * ratio
                    story.append(img_obj)
                    story.append(Spacer(1, 6))
                except Exception as exc:
                    logger.warning("无法嵌入图片 %s: %s", img_path, exc)
            i += 1
            continue

        # ── 无序列表 ──────────────────────────────────────────────────────
        m = re.match(r"^[-*]\s+(.*)", line)
        if m:
            text = _pdf_inline(m.group(1), font)
            story.append(Paragraph(f"• {text}", styles["list"]))
            i += 1
            continue

        # ── 普通段落 ──────────────────────────────────────────────────────
        text = _pdf_inline(line, font)
        story.append(Paragraph(text, styles["body"]))
        i += 1

    return story


def _build_pdf_table(table_lines: list[str], styles: dict, font: str):
    """将 Markdown 表格行列表转换为 reportlab Table flowable。"""
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Table, TableStyle

    data: list[list] = []
    is_first_row = True
    has_header = False

    for line in table_lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        # 跳过分隔行（全是 --- 的行）
        if all(re.match(r"^:?-+:?$", c) for c in cells if c):
            has_header = True
            continue
        style = styles["table_head"] if (is_first_row and has_header) else styles["table_cell"]
        row = [Paragraph(_pdf_inline(c, font), style) for c in cells]
        data.append(row)
        is_first_row = False

    if not data:
        return None

    col_count = max(len(row) for row in data)
    # 补齐短行
    for row in data:
        while len(row) < col_count:
            row.append(Paragraph("", styles["table_cell"]))

    tbl = Table(data, hAlign="LEFT", repeatRows=1 if has_header else 0)
    tbl.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (-1, -1), font),
        ("FONTSIZE",      (0, 0), (-1, -1), 9.5),
        ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#f5f5f5")),
        ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    return tbl


# ── 页眉页脚 ──────────────────────────────────────────────────────────────

def _make_header_footer(title: str, font: str):
    """返回 onFirstPage / onLaterPages 回调，用于绘制页眉页脚。"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfgen.canvas import Canvas

    W, H = A4

    def draw(canvas: "Canvas", doc) -> None:  # type: ignore[name-defined]
        canvas.saveState()
        # 页眉
        canvas.setFont(font, 8)
        canvas.setFillColor(colors.HexColor("#999999"))
        canvas.drawString(2.5 * cm, H - 1.8 * cm, title[:80])
        canvas.setStrokeColor(colors.HexColor("#eeeeee"))
        canvas.line(2.5 * cm, H - 2.0 * cm, W - 2.5 * cm, H - 2.0 * cm)
        # 页脚
        canvas.setFont(font, 8)
        canvas.drawCentredString(W / 2, 1.5 * cm, f"— {doc.page} —")
        canvas.restoreState()

    return draw, draw   # onFirstPage, onLaterPages


# ── 公开 API ──────────────────────────────────────────────────────────────

def convert_md_to_pdf(md_path: Path, pdf_path: Path) -> None:
    """将单个 Markdown 笔记文件转换为 PDF。

    Args:
        md_path: 源 Markdown 文件路径
        pdf_path: 目标 PDF 文件路径

    Raises:
        ImportError: 若 reportlab 未安装
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Spacer
    except ImportError as exc:
        raise ImportError(
            "PDF 导出需要安装 reportlab：\n  pip install reportlab\n  或  uv add reportlab"
        ) from exc

    font = _ensure_pdf_font()
    styles = _make_pdf_styles(font)

    content = md_path.read_text(encoding="utf-8")

    # 提取标题用于元数据
    title = md_path.parent.name
    for line in content.splitlines():
        m = re.match(r"^#\s+(.*)", line)
        if m:
            title = m.group(1).strip()
            break

    story = _build_story(content, md_path.parent, styles, font)

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    on_first, on_later = _make_header_footer(title, font)

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
        topMargin=3.0 * cm,
        bottomMargin=2.5 * cm,
        title=title,
        author="getnotes-cli",
        subject="Get笔记导出",
    )
    doc.build(story, onFirstPage=on_first, onLaterPages=on_later)


def export_notes_to_pdf(notes_dir: Path, output_dir: Path, force: bool = False) -> dict:
    """批量将 notes/ 目录下所有笔记导出为 PDF。

    Args:
        notes_dir: 笔记源目录（包含按文件夹组织的笔记）
        output_dir: PDF 输出根目录
        force: 是否覆盖已存在的 PDF 文件

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

        pdf_file = output_dir / f"{folder.name}.pdf"

        if pdf_file.exists() and not force:
            logger.info("  ⏭ 已存在: %s.pdf", folder.name[:55])
            stats["skipped"] += 1
            continue

        try:
            convert_md_to_pdf(md_file, pdf_file)
            logger.info("  ✅ 已转换: %s.pdf", folder.name[:55])
            stats["converted"] += 1
        except ImportError as exc:
            raise   # 让调用方处理缺少依赖的情况
        except Exception as exc:
            logger.error("  ❌ 转换失败: %s — %s", folder.name, exc)
            stats["errors"] += 1

    return stats
