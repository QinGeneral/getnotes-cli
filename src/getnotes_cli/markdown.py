"""Markdown 转换模块 — 将笔记数据转为 Markdown 格式"""

import os
import re
import urllib.parse
from pathlib import Path


def sanitize_filename(name: str, max_length: int = 80) -> str:
    """清理文件名，移除非法字符"""
    name = re.sub(r'[<>:"/\\|?*\n\r\t]', '_', name)
    name = name.strip(' .')
    if len(name) > max_length:
        name = name[:max_length].rstrip(' .')
    return name or "untitled"


def get_file_extension(url: str, default_ext: str = "") -> str:
    """从 URL 中提取文件扩展名"""
    parsed = urllib.parse.urlparse(url)
    path = urllib.parse.unquote(parsed.path)
    _, ext = os.path.splitext(path)
    return ext if ext else default_ext


def format_duration(ms: int) -> str:
    """将毫秒转换为可读的时长格式"""
    if ms <= 0:
        return ""
    seconds = ms // 1000
    minutes = seconds // 60
    hours = minutes // 60
    if hours > 0:
        return f"{hours}小时{minutes % 60}分{seconds % 60}秒"
    elif minutes > 0:
        return f"{minutes}分{seconds % 60}秒"
    else:
        return f"{seconds}秒"


def note_to_markdown(note: dict, attachments_dir: Path, note_dir: Path) -> str:
    """将单条笔记转换为 Markdown 格式"""
    lines = []

    title = note.get("title", "").strip()
    if title:
        lines.append(f"# {title}")
        lines.append("")

    # --- 元信息表格 ---
    lines.append("## 📋 笔记信息")
    lines.append("")
    lines.append("| 属性 | 值 |")
    lines.append("|------|-----|")
    lines.append(f"| ID | `{note.get('note_id', '')}` |")
    lines.append(f"| 来源 | {note.get('source', '')} |")
    lines.append(f"| 类型 | {note.get('note_type', '')} |")
    lines.append(f"| 录入方式 | {note.get('entry_type', '')} |")
    lines.append(f"| 创建时间 | {note.get('created_at', '')} |")
    lines.append(f"| 更新时间 | {note.get('updated_at', note.get('edit_time', ''))} |")
    lines.append(f"| AI 生成 | {'是' if note.get('is_ai_generated') else '否'} |")

    tags = note.get("tags", [])
    if tags:
        tag_names = ", ".join(f"`{t['name']}`" for t in tags if isinstance(t, dict))
        lines.append(f"| 标签 | {tag_names} |")

    lines.append("")

    # --- 正文内容 ---
    content = note.get("content", "").strip()
    if content:
        lines.append("## 📝 内容")
        lines.append("")
        lines.append(content)
        lines.append("")

    # --- 引用内容 ---
    ref_content = note.get("ref_content", "").strip()
    if ref_content:
        lines.append("## 📖 引用内容")
        lines.append("")
        lines.append("> " + ref_content.replace("\n", "\n> "))
        lines.append("")

    # --- 附件（音频/链接） ---
    attachments = note.get("attachments", [])
    if attachments:
        lines.append("## 🔊 附件")
        lines.append("")
        for i, att in enumerate(attachments):
            att_type = att.get("type", "unknown")
            att_url = att.get("url", "")
            att_title = att.get("title", "")
            duration = att.get("duration", 0)

            if att_type == "link":
                # 链接类型附件
                if att_title and att_url:
                    lines.append(f"- 🔗 [{att_title}]({att_url})")
                elif att_url:
                    lines.append(f"- 🔗 [{att_url}]({att_url})")
            elif att_url:
                ext = get_file_extension(att_url, f".{att_type}")
                att_filename = f"attachment_{i + 1}{ext}"
                att_path = attachments_dir / att_filename
                rel_path = os.path.relpath(att_path, note_dir)

                duration_str = format_duration(duration)
                dur_info = f"（时长: {duration_str}）" if duration_str else ""
                lines.append(f"- **{att_type.upper()}** {dur_info}: [{att_filename}]({rel_path})")
            else:
                lines.append(f"- **{att_type.upper()}**: (无链接)")
        lines.append("")

    # --- 图片 ---
    original_images = note.get("original_images", [])
    small_images = note.get("small_images", [])
    body_images = note.get("body_images", [])
    images = original_images or small_images or body_images

    if images:
        lines.append("## 🖼️ 图片")
        lines.append("")
        for i, img in enumerate(images):
            img_url = img if isinstance(img, str) else img.get("url", "") if isinstance(img, dict) else ""
            if img_url:
                ext = get_file_extension(img_url, ".jpg")
                img_filename = f"image_{i + 1}{ext}"
                img_path = attachments_dir / img_filename
                rel_path = os.path.relpath(img_path, note_dir)
                lines.append(f"![图片 {i + 1}]({rel_path})")
                lines.append("")

    # --- 资源引用信息 ---
    res_info = note.get("res_info", {})
    if isinstance(res_info, dict):
        res_title = res_info.get("title", "").strip()
        res_url = res_info.get("url", "").strip()
        if res_title or res_url:
            lines.append("## 🔗 引用来源")
            lines.append("")
            if res_title and res_url:
                lines.append(f"[{res_title}]({res_url})")
            elif res_title:
                lines.append(res_title)
            elif res_url:
                lines.append(f"[链接]({res_url})")
            lines.append("")

    # --- 所属知识库 ---
    topics = note.get("topics", [])
    if topics:
        lines.append("## 📚 所属知识库")
        lines.append("")
        for t in topics:
            if isinstance(t, dict):
                lines.append(f"- {t.get('topic_name', '(未知)')}")
        lines.append("")

    return "\n".join(lines)
